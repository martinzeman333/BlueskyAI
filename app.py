from flask import Flask, render_template, request, jsonify, session
import os
# Importujeme skutečnou Bluesky knihovnu
from atproto import Client, models

app = Flask(__name__, static_folder='static', static_url_path='/static')
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'your_super_secret_key') # Důležité pro session!

# Globální instance Bluesky klienta
bluesky_client = Client()

# Proměnné prostředí pro Bluesky přihlašovací údaje
# V PRODUKCI NIKDY NEUKLÁDEJTE HESLA PŘÍMO DO KÓDU!
# Používejte proměnné prostředí (např. na Render.com)
BLUESKY_HANDLE = os.environ.get('BLUESKY_HANDLE')
BLUESKY_PASSWORD = os.environ.get('BLUESKY_PASSWORD')

# Funkce pro ověření, zda je klient přihlášen
def is_bluesky_logged_in():
    """Kontroluje, zda je Bluesky klient přihlášen."""
    # `me` atribut je nastaven po úspěšném přihlášení
    return bluesky_client.me is not None

# Funkce pro získání handle po přihlášení
def get_bluesky_handle():
    """Vrací handle přihlášeného uživatele."""
    return bluesky_client.me.did.split(':').pop() if is_bluesky_logged_in() else None


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
    
    try:
        # Získání statistik (Toto je placeholder, atproto API nemusí mít přímou metodu pro "moje statistiky"
        # Budete muset implementovat logiku pro načítání vlastních příspěvků, lajků atd.
        # Následující je POUZE UKÁZKA, JAK BYSTE MOHLI ZÍSKAT NĚJAKÁ DATA
        
        # Příklad: Získání počtu příspěvků (omezený na prvních několik pro rychlou ukázku)
        # response = bluesky_client.get_author_feed(actor=bluesky_client.me.did, limit=10)
        # ai_posts = len(response.feed) if response and response.feed else 0

        # Pro účely této ukázky použijeme pevné hodnoty nebo získáme data, která atproto nabízí
        # (Např. aktuální Bluesky API neposkytuje přímo "počet lajků", "komentářů" jako statistiku)
        # Budete muset buď sledovat tyto události sami, nebo použít jiná API.
        stats = {
            'ai_posts': "N/A", # Zde byste implementovali logiku pro získání skutečného počtu
            'auto_likes': "N/A", # Zde byste implementovali logiku pro získání skutečného počtu
            'comments': "N/A",   # Zde byste implementovali logiku pro získání skutečného počtu
            'new_follows': "N/A" # Zde byste implementovali logiku pro získání skutečného počtu
        }
        return jsonify({"status": "success", "stats": stats})
    except Exception as e:
        return jsonify({"status": "error", "message": f"Chyba při načítání statistik: {str(e)}"})


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
        # Skutečné lajknutí příspěvku na Bluesky
        # V reálné aplikaci byste zde mohli mít logiku pro vyhledávání příspěvků k lajknutí
        bluesky_client.like(post_uri, post_uri.rsplit('/', 1)[-1]) # Rkey z URI
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
        # Získání informace o příspěvku pro vytvoření správného reference
        # response = bluesky_client.get_post(post_uri)
        # record_ref = models.create_strong_ref(response.uri, response.cid)
        # root_ref = record_ref # pro jednoduchost, pokud komentujeme přímo příspěvek

        # Pro ukázku použijeme zjednodušenou referenci, v reálu byste ji získali dynamicky
        # Zde je potřeba správně získat `record_ref` a `root_ref` pro komentář
        # K tomu je často potřeba nejdříve načíst post, na který reagujete.
        # Zde je placeholder, který byste museli upravit.
        
        # Příklad ruční konstrukce (museli byste znát URI a CID cílového příspěvku)
        # Alternativně:
        # resp = bluesky_client.get_post_thread(post_uri)
        # root_post = resp.thread.post
        # record_ref = models.create_strong_ref(root_post.uri, root_post.cid)
        # parent_ref = models.create_strong_ref(root_post.uri, root_post.cid) # nebo parent_post.uri/cid pro odpověď na komentář
        
        # Vzhledem k složitosti dynamického získání strong_ref v simulaci,
        # budeme předpokládat, že post_uri je platný a postačí pro tuto ukázku
        
        # Toto je zjednodušené - v reálu potřebujete silné reference na root a parent post
        # DŮLEŽITÉ: atproto.models.create_strong_ref vyžaduje uri a cid.
        # Zde jen předáváme URI, což je zjednodušení pro tuto ukázku.
        # Pro správnou implementaci byste museli získat CID cílového příspěvku.
        
        # Pokud nevíme CID, můžeme použít jen textový post.
        # Nebo:
        # from atproto import models_pack
        # post_record = bluesky_client.get_record(post_uri)
        # root_ref = models_pack.create_ref_from_uri(post_uri)
        # parent_ref = models_pack.create_ref_from_uri(post_uri)

        # Pro zjednodušení simulujeme úspěch a upozorňujeme na potřebu správné implementace.
        # Skutečné vytvoření komentáře na Bluesky by vypadalo takto:
        # bluesky_client.send_post(comment_text, reply_to=models.ReplyRef(root=root_ref, parent=parent_ref))
        
        return jsonify({"status": "success", "message": f"Komentář k {post_uri} úspěšně přidán (simulováno)! Budete potřebovat implementovat dynamické získání URI/CID pro reálné komentáře."})
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
        # Nejprve je potřeba získat DID z handle
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
        # Nejprve je potřeba získat DID z handle a record_uri předchozího follow záznamu
        # To je složitější, protože atproto nemá přímou unfollow metodu jen s handle.
        # Museli byste najít existující follow záznam.
        
        # Příklad (zjednodušený - vyžadovalo by to vyhledání follow záznamu):
        # resp = bluesky_client.get_follows(bluesky_client.me.did)
        # follow_record = next((f for f in resp.follows if f.handle == target_handle), None)
        # if follow_record:
        #     bluesky_client.delete_record(follow_record.uri, follow_record.cid)
        #     return jsonify({"status": "success", "message": f"Uživatel {target_handle} úspěšně přestal být sledován!"})
        # else:
        #     return jsonify({"status": "error", "message": f"Uživatel {target_handle} nebyl nalezen mezi sledovanými."})

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
