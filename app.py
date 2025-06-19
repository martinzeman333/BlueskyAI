from flask import Flask, render_template, request, jsonify, session
import os
# Importujeme skutečnou Bluesky knihovnu
from atproto import Client, models

app = Flask(__name__, static_folder='static', static_url_path='/static')
# FLASK_SECRET_KEY je kritický pro zabezpečení session (např. ukládání stavu přihlášení).
# Nikdy neukládejte hesla nebo jiné citlivé údaje přímo do kódu.
# Vždy používejte proměnné prostředí.
# Pro produkci vygenerujte silný, náhodný klíč, např. os.urandom(24).hex()
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'your_super_secret_key_please_change_this!')

# Globální instance Bluesky klienta
bluesky_client = Client()

# Proměnné prostředí pro Bluesky přihlašovací údaje
# Tyto proměnné by měly být nastaveny ve vašem produkčním prostředí (např. na Render.com)
# BLUESKY_HANDLE = os.environ.get('BLUESKY_HANDLE')
# BLUESKY_PASSWORD = os.environ.get('BLUESKY_PASSWORD')

# Funkce pro ověření, zda je klient přihlášen
def is_bluesky_logged_in():
    """Kontroluje, zda je Bluesky klient přihlášen."""
    # `me` atribut je nastaven po úspěšném přihlášení
    return bluesky_client.me is not None

# Funkce pro získání handle po přihlášení
def get_bluesky_handle():
    """Vrací handle přihlášeného uživatele."""
    # DID (Decentralized Identifier) je unikátní identifikátor uživatele na Bluesky
    # Handle (např. 'example.bsky.social') je čitelnější jméno.
    return bluesky_client.me.handle if is_bluesky_logged_in() else None


@app.route('/')
def index():
    # Předáme stav přihlášení a handle do šablony
    return render_template('index.html', is_logged_in=is_bluesky_logged_in(), user_handle=get_bluesky_handle())

@app.route('/health')
def health():
    return jsonify({'status': 'ok'})

@app.route('/api/bluesky-login', methods=['POST'])
def bluesky_login():
    data = request.get_json()
    handle = data.get('handle')
    password = data.get('password')

    if not handle or not password:
        return jsonify({"status": "error", "message": "Prosím, zadejte Bluesky handle a heslo."})

    try:
        # Skutečné přihlášení k Bluesky
        bluesky_client.login(handle, password)
        if is_bluesky_logged_in():
            return jsonify({"status": "success", "message": f"Úspěšně přihlášen jako {get_bluesky_handle()}!", "handle": get_bluesky_handle()})
        else:
            return jsonify({"status": "error", "message": "Přihlášení se nezdařilo. Zkontrolujte prosím své údaje."})
    except Exception as e:
        # Zpracování chyb při přihlášení (např. špatné přihlašovací údaje, síťové problémy)
        return jsonify({"status": "error", "message": f"Chyba při přihlašování: {str(e)}"})

@app.route('/api/bluesky-logout', methods=['POST'])
def bluesky_logout():
    try:
        # Odhlášení klienta
        bluesky_client.logout()
        return jsonify({"status": "success", "message": "Odhlášeno z Bluesky."})
    except Exception as e:
        return jsonify({"status": "error", "message": f"Chyba při odhlašování: {str(e)}"})


@app.route('/api/get-stats', methods=['GET'])
def get_stats():
    if not is_bluesky_logged_in():
        return jsonify({"status": "error", "message": "Nelze načíst statistiky. Nejste přihlášeni."})
    
    followers_count = "N/A"
    follows_count = "N/A"

    try:
        # Získání počtu sledujících (followers)
        # Bluesky API vrací paginované výsledky, je potřeba je proiterovat
        followers_list = []
        cursor = None
        while True:
            response = bluesky_client.get_followers(actor=bluesky_client.me.did, limit=100, cursor=cursor)
            if response and response.followers:
                followers_list.extend(response.followers)
                cursor = response.cursor
            else:
                break
            if not cursor: # If there's no more cursor, we've fetched all pages
                break
        followers_count = len(followers_list)
    except Exception as e:
        print(f"Chyba při načítání počtu sledujících: {e}")
        followers_count = "Chyba"

    try:
        # Získání počtu sledovaných (follows)
        # Bluesky API vrací paginované výsledky, je potřeba je proiterovat
        follows_list = []
        cursor = None
        while True:
            response = bluesky_client.get_follows(actor=bluesky_client.me.did, limit=100, cursor=cursor)
            if response and response.follows:
                follows_list.extend(response.follows)
                cursor = response.cursor
            else:
                break
            if not cursor: # If there's no more cursor, we've fetched all pages
                break
        follows_count = len(follows_list)
    except Exception as e:
        print(f"Chyba při načítání počtu sledovaných: {e}")
        follows_count = "Chyba"

    stats = {
        'followers': followers_count,
        'following': follows_count
    }
    return jsonify({"status": "success", "stats": stats})

@app.route('/api/ai-post', methods=['POST'])
def ai_post():
    if not is_bluesky_logged_in():
        return jsonify({"status": "error", "message": "Pro AI Post je nutné být přihlášen."})
    data = request.get_json()
    post_content = data.get('content')

    if not post_content:
        # Zde by AI generovala obsah, pokud by byl prázdný
        # Např. pomocí volání Gemini API
        post_content = "Automaticky generovaný příspěvek od Bluesky AI Manager."

    try:
        # Skutečné vytvoření příspěvku na Bluesky
        post_ref = bluesky_client.post(post_content)
        return jsonify({"status": "success", "message": f"Příspěvek úspěšně vytvořen! URI: {post_ref.uri}"})
    except Exception as e:
        return jsonify({"status": "error", "message": f"Chyba při vytváření příspěvku: {str(e)}"})

@app.route('/api/ai-like', methods=['POST'])
def ai_like():
    if not is_bluesky_logged_in():
        return jsonify({"status": "error", "message": "Pro AI Like je nutné být přihlášen."})
    data = request.get_json()
    post_uri = data.get('uri')

    if not post_uri:
        return jsonify({"status": "error", "message": "Pro lajknutí je vyžadováno URI příspěvku."})

    try:
        # Skutečné lajknutí příspěvků na Bluesky
        # Získání rkey z URI je důležité pro metodu like
        rkey = post_uri.rsplit('/', 1)[-1]
        bluesky_client.like(post_uri, rkey)
        return jsonify({"status": "success", "message": f"Příspěvek {post_uri} úspěšně lajknut!"})
    except Exception as e:
        return jsonify({"status": "error", "message": f"Chyba při lajkování příspěvku: {str(e)}"})

@app.route('/api/ai-comment', methods=['POST'])
def ai_comment():
    if not is_bluesky_logged_in():
        return jsonify({"status": "error", "message": "Pro AI Comment je nutné být přihlášen."})
    data = request.get_json()
    post_uri = data.get('uri')
    comment_text = data.get('comment')

    if not post_uri or not comment_text:
        return jsonify({"status": "error", "message": "Pro komentář je vyžadováno URI a text komentáře."})

    try:
        # K vytvoření komentáře je potřeba získat "strong reference" na cílový příspěvek.
        # To znamená znalost URI a CID (Content ID) příspěvku.
        # Zde je to zjednodušené, ale pro reálnou aplikaci byste museli
        # nejprve načíst cílový příspěvek (např. pomocí get_post_thread nebo get_record)
        # a z něj získat potřebné URI a CID pro 'root' a 'parent' reference.

        # Příklad, jak byste získali reference:
        # thread = bluesky_client.get_post_thread(post_uri)
        # post = thread.thread.post if thread and thread.thread and thread.thread.post else None
        # if post:
        #     root_ref = models.create_strong_ref(post.uri, post.cid)
        #     parent_ref = models.create_strong_ref(post.uri, post.cid) # Pokud odpovídáte přímo na post
        #     bluesky_client.post(comment_text, reply_to=models.ReplyRef(root=root_ref, parent=parent_ref))
        #     return jsonify({"status": "success", "message": f"Komentář k {post_uri} úspěšně přidán!"})
        # else:
        #    return jsonify({"status": "error", "message": f"Příspěvek s URI {post_uri} nenalezen pro komentář."})

        # Zde je pro ukázku pouze simulace úspěchu s upozorněním.
        return jsonify({"status": "success", "message": f"Komentář k {post_uri} úspěšně přidán (simulováno)! Vyžaduje dynamické získání URI/CID pro reálné komentáře."})
    except Exception as e:
        return jsonify({"status": "error", "message": f"Chyba při vytváření komentáře: {str(e)}"})

@app.route('/api/ai-follow', methods=['POST'])
def ai_follow():
    if not is_bluesky_logged_in():
        return jsonify({"status": "error", "message": "Pro AI Follow je nutné být přihlášen."})
    data = request.get_json()
    target_handle = data.get('handle')

    if not target_handle:
        return jsonify({"status": "error", "message": "Pro sledování je vyžadován handle uživatele."})

    try:
        # Skutečné sledování uživatele na Bluesky
        # Nejprve je potřeba získat DID (Decentralized Identifier) z handle
        profile = bluesky_client.get_profile(target_handle)
        if profile and profile.did:
            bluesky_client.follow(profile.did)
            return jsonify({"status": "success", "message": f"Uživatel {target_handle} úspěšně sledován!"})
        else:
            return jsonify({"status": "error", "message": f"Uživatel {target_handle} nenalezen."})
    except Exception as e:
        return jsonify({"status": "error", "message": f"Chyba při sledování uživatele: {str(e)}"})

@app.route('/api/ai-unfollow', methods=['POST'])
def ai_unfollow():
    if not is_bluesky_logged_in():
        return jsonify({"status": "error", "message": "Pro AI Unfollow je nutné být přihlášen."})
    data = request.get_json()
    target_handle = data.get('handle')

    if not target_handle:
        return jsonify({"status": "error", "message": "Pro zrušení sledování je vyžadován handle uživatele."})

    try:
        # Skutečné zrušení sledování uživatele na Bluesky
        # Zrušení sledování vyžaduje URI a CID existujícího "follow" záznamu.
        # atproto nemá přímou unfollow metodu pouze s handlem.
        # Museli byste najít existující "follow" záznam vytvořený přihlášeným uživatelem pro daného target_handle.
        # Příklad:
        # profile = bluesky_client.get_profile(target_handle)
        # if profile and profile.did:
        #     # Toto by bylo náročnější na implementaci, protože byste museli prohledat své vlastní follows
        #     # po záznamu, který odpovídá cílovému DID.
        #     # Níže je jen ukázka, co by se pak volalo:
        #     # bluesky_client.delete_record(uri='uri_nalezeného_follow_záznamu', cid='cid_nalezeného_follow_záznamu')
        #     return jsonify({"status": "success", "message": f"Uživatel {target_handle} úspěšně přestal být sledován (logika pro nalezení follow záznamu není plně implementována)!"})
        # else:
        #    return jsonify({"status": "error", "message": f"Uživatel {target_handle} nenalezen."})

        # Zde je pro ukázku pouze simulace úspěchu s upozorněním.
        return jsonify({"status": "success", "message": f"Zrušení sledování pro uživatele {target_handle} (simulováno). Reálná implementace vyžaduje nalezení follow záznamu."})
    except Exception as e:
        return jsonify({"status": "error", "message": f"Chyba při zrušení sledování: {str(e)}"})

if __name__ == '__main__':
    # Pro development
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True) # debug=True pro snadnější vývoj
else:
    # Pro production s gunicorn
    application = app
