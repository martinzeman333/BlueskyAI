from flask import Flask, render_template, request, jsonify, session
import os
from atproto import Client, models

app = Flask(__name__, static_folder='static', static_url_path='/static')
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'your_super_secret_key_please_change_this!')

bluesky_client = Client()

def is_bluesky_logged_in():
    return bluesky_client.me is not None

def get_bluesky_handle():
    return bluesky_client.me.handle if is_bluesky_logged_in() else None


@app.route('/')
def index():
    return render_template('index.html', is_logged_in=is_bluesky_logged_in(), user_handle=get_bluesky_handle())

@app.route('/health')
def health():
    return jsonify({'status': 'ok'})

@app.route('/api/bluesky-login', methods=['POST'])
def bluesky_login():
    data = request.get_json()
    handle = data.get('handle')
    password = data.get('password')

    # Odstranění ladicího výpisu pro handle a heslo
    # print(f"Přihlašovací pokus: Handle '{handle}', Délka hesla: {len(password) if password else 0}")

    if not handle or not password:
        return jsonify({"status": "error", "message": "Prosím, zadejte Bluesky handle a heslo."})

    try:
        bluesky_client.login(handle, password)
        if is_bluesky_logged_in():
            return jsonify({"status": "success", "message": f"Úspěšně přihlášen jako {get_bluesky_handle()}!", "handle": get_bluesky_handle()})
        else:
            return jsonify({"status": "error", "message": "Přihlášení se nezdařilo. Zkontrolujte prosím své údaje."})
    except Exception as e:
        return jsonify({"status": "error", "message": f"Chyba při přihlašování: {str(e)}"})

@app.route('/api/bluesky-logout', methods=['POST'])
def bluesky_logout():
    try:
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
        followers_list = []
        cursor = None
        while True:
            response = bluesky_client.get_followers(actor=bluesky_client.me.did, limit=100, cursor=cursor)
            if response and response.followers:
                followers_list.extend(response.followers)
                cursor = response.cursor
            else:
                break
            if not cursor:
                break
        followers_count = len(followers_list)
    except Exception as e:
        print(f"Chyba při načítání počtu sledujících: {e}")
        followers_count = "Chyba"

    try:
        follows_list = []
        cursor = None
        while True:
            response = bluesky_client.get_follows(actor=bluesky_client.me.did, limit=100, cursor=cursor)
            if response and response.follows:
                follows_list.extend(response.follows)
                cursor = response.cursor
            else:
                break
            if not cursor:
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
        post_content = "Automaticky generovaný příspěvek od Bluesky AI Manager."

    try:
        post_ref = bluesky_client.post(post_content)
        return jsonify({"status": "success", "message": f"Příspěvek úspěšně vytvořen! URI: {post_ref.uri}"})
    except Exception as e:
        return jsonify({"status": "error", "message": f"Chyba při vytváření příspěvků: {str(e)}"})

@app.route('/api/ai-like', methods=['POST'])
def ai_like():
    if not is_bluesky_logged_in():
        return jsonify({"status": "error", "message": "Pro AI Like je nutné být přihlášen."})
    data = request.get_json()
    post_uri = data.get('uri')

    if not post_uri:
        return jsonify({"status": "error", "message": "Pro lajknutí je vyžadováno URI příspěvku."})

    try:
        rkey = post_uri.rsplit('/', 1)[-1]
        bluesky_client.like(post_uri, rkey)
        return jsonify({"status": "success", "message": f"Příspěvek {post_uri} úspěšně lajknut!"})
    except Exception as e:
        return jsonify({"status": "error", "message": f"Chyba při lajkování příspěvků: {str(e)}"})

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
        thread_response = bluesky_client.get_post_thread(post_uri)
        
        if not (thread_response and thread_response.thread and hasattr(thread_response.thread, 'post')):
            return jsonify({"status": "error", "message": f"Příspěvek s URI {post_uri} nebyl nalezen nebo je neplatný."})

        target_post = thread_response.thread.post
        
        root_ref = models.create_strong_ref(target_post.uri, target_post.cid)
        parent_ref = models.create_strong_ref(target_post.uri, target_post.cid)

        bluesky_client.post(text=comment_text, reply_to=models.ReplyRef(root=root_ref, parent=parent_ref))
        
        return jsonify({"status": "success", "message": f"Komentář k {post_uri} úspěšně přidán!"})
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
        profile = bluesky_client.get_profile(target_handle)
        if not (profile and profile.did):
            return jsonify({"status": "error", "message": f"Uživatel {target_handle} nenalezen."})
        
        target_did = profile.did

        found_follow_uri = None
        found_follow_cid = None
        
        cursor = None
        while True:
            response = bluesky_client.get_follows(actor=bluesky_client.me.did, limit=100, cursor=cursor)
            if response and response.follows:
                for follow_item in response.follows:
                    if follow_item.did == target_did:
                        found_follow_uri = follow_item.uri
                        found_follow_cid = follow_item.cid
                        break
                if found_follow_uri:
                    break
                cursor = response.cursor
            else:
                break
            if not cursor:
                break

        if found_follow_uri and found_follow_cid:
            bluesky_client.delete_record(found_follow_uri, found_follow_cid)
            return jsonify({"status": "success", "message": f"Uživatel {target_handle} úspěšně přestal být sledován!"})
        else:
            return jsonify({"status": "error", "message": f"Uživatel {target_handle} nebyl nalezen mezi sledovanými účty nebo záznam o sledování je neplatný."})

    except Exception as e:
        return jsonify({"status": "error", "message": f"Chyba při zrušení sledování: {str(e)}"})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
else:
    application = app
