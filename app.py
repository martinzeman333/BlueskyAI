from flask import Flask, render_template, request, jsonify, session
import os
# Pro budoucí integraci s Bluesky API byste zde nainstalovali a importovali příslušnou knihovnu, např.:
# from atproto import Client, models
# Z bezpečnostních důvodů a pro ukázku zde simulujeme Bluesky klienta.
class MockBlueskyClient:
    """Simulovaný Bluesky klient pro účely demonstrace."""
    def __init__(self):
        self.is_logged_in = False
        self.handle = None

    def login(self, handle, password):
        """Simuluje přihlášení a vrací True/False."""
        print(f"Simulace přihlášení na Bluesky pro uživatele: {handle}")
        # Zde byste normálně volali skutečné přihlašovací API Bluesky
        # client = Client(f"https://bsky.social")
        # client.login(handle, password)
        # self.is_logged_in = client.me is not None
        # if self.is_logged_in:
        #     self.handle = handle
        # return self.is_logged_in
        
        # Pro demonstraci: úspěšné přihlášení pro jakékoliv neprázdné údaje
        if handle and password:
            self.is_logged_in = True
            self.handle = handle
            return True
        self.is_logged_in = False
        self.handle = None
        return False

    def get_my_stats(self):
        """Simuluje získání statistik uživatele."""
        if not self.is_logged_in:
            return None
        # Zde byste normálně volali skutečné API pro získání statistik
        return {
            'ai_posts': 1234,
            'auto_likes': 5678,
            'comments': 890,
            'new_follows': 456
        }

    def post(self, text_content):
        """Simuluje vytvoření příspěvku."""
        if not self.is_logged_in:
            return {"status": "error", "message": "Nejste přihlášeni k Bluesky."}
        print(f"Simulace AI Postu: {text_content}")
        # client.post(text_content)
        return {"status": "success", "message": "Příspěvek úspěšně vytvořen (simulováno)!"}

    def like(self, post_uri):
        """Simuluje lajknutí příspěvku."""
        if not self.is_logged_in:
            return {"status": "error", "message": "Nejste přihlášeni k Bluesky."}
        print(f"Simulace AI Like pro URI: {post_uri}")
        # client.like(post_uri)
        return {"status": "success", "message": "Příspěvek úspěšně lajknut (simulováno)!"}

    def comment(self, post_uri, comment_text):
        """Simuluje komentování příspěvku."""
        if not self.is_logged_in:
            return {"status": "error", "message": "Nejste přihlášeni k Bluesky."}
        print(f"Simulace AI Komentáře pro URI: {post_uri} s textem: {comment_text}")
        # client.comment(post_uri, comment_text)
        return {"status": "success", "message": "Komentář úspěšně přidán (simulováno)!"}

    def follow(self, target_handle):
        """Simuluje sledování uživatele."""
        if not self.is_logged_in:
            return {"status": "error", "message": "Nejste přihlášeni k Bluesky."}
        print(f"Simulace AI Follow pro uživatele: {target_handle}")
        # client.follow(target_handle)
        return {"status": "success", "message": f"Uživatel {target_handle} úspěšně sledován (simulováno)!"}

    def unfollow(self, target_handle):
        """Simuluje zrušení sledování uživatele."""
        if not self.is_logged_in:
            return {"status": "error", "message": "Nejste přihlášeni k Bluesky."}
        print(f"Simulace AI Unfollow pro uživatele: {target_handle}")
        # client.unfollow(target_handle)
        return {"status": "success", "message": f"Uživatel {target_handle} úspěšně přestal být sledován (simulováno)!"}


app = Flask(__name__, static_folder='static', static_url_path='/static')
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'your_super_secret_key') # Důležité pro session!

# Globální instance simulovaného klienta
bluesky_client = MockBlueskyClient()

@app.route('/')
def index():
    return render_template('index.html', is_logged_in=bluesky_client.is_logged_in, user_handle=bluesky_client.handle)

@app.route('/health')
def health():
    return jsonify({'status': 'ok'})

@app.route('/api/bluesky-login', methods=['POST'])
def bluesky_login():
    data = request.get_json()
    handle = data.get('handle')
    password = data.get('password')

    if bluesky_client.login(handle, password):
        return jsonify({"status": "success", "message": f"Úspěšně přihlášen jako {bluesky_client.handle}!", "handle": bluesky_client.handle})
    else:
        return jsonify({"status": "error", "message": "Nepodařilo se přihlásit. Zkontrolujte prosím své údaje."})

@app.route('/api/bluesky-logout', methods=['POST'])
def bluesky_logout():
    bluesky_client.is_logged_in = False
    bluesky_client.handle = None
    return jsonify({"status": "success", "message": "Odhlášeno."})


@app.route('/api/get-stats', methods=['GET'])
def get_stats():
    stats = bluesky_client.get_my_stats()
    if stats:
        return jsonify({"status": "success", "stats": stats})
    else:
        return jsonify({"status": "error", "message": "Nelze načíst statistiky. Možná nejste přihlášeni."})

@app.route('/api/ai-post', methods=['POST'])
def ai_post():
    if not bluesky_client.is_logged_in:
        return jsonify({"status": "error", "message": "Pro AI Post je nutné být přihlášen."})
    data = request.get_json()
    post_content = data.get('content', 'Automaticky generovaný příspěvek od Bluesky AI Manager.')
    # Zde by AI vygenerovala skutečný obsah
    result = bluesky_client.post(post_content)
    return jsonify(result)

@app.route('/api/ai-like', methods=['POST'])
def ai_like():
    if not bluesky_client.is_logged_in:
        return jsonify({"status": "error", "message": "Pro AI Like je nutné být přihlášen."})
    data = request.get_json()
    post_uri = data.get('uri', 'at://example.com/post/abc123') # Příklad URI
    # Zde by AI vybrala příspěvek k lajknutí
    result = bluesky_client.like(post_uri)
    return jsonify(result)

@app.route('/api/ai-comment', methods=['POST'])
def ai_comment():
    if not bluesky_client.is_logged_in:
        return jsonify({"status": "error", "message": "Pro AI Comment je nutné být přihlášen."})
    data = request.get_json()
    post_uri = data.get('uri', 'at://example.com/post/def456') # Příklad URI
    comment_text = data.get('comment', 'Skvělý příspěvek! (Automatický komentář)')
    # Zde by AI vybrala příspěvek a generovala komentář
    result = bluesky_client.comment(post_uri, comment_text)
    return jsonify(result)

@app.route('/api/ai-follow', methods=['POST'])
def ai_follow():
    if not bluesky_client.is_logged_in:
        return jsonify({"status": "error", "message": "Pro AI Follow je nutné být přihlášen."})
    data = request.get_json()
    target_handle = data.get('handle', 'example.bsky.social') # Příklad handle
    # Zde by AI vybrala účet ke sledování
    result = bluesky_client.follow(target_handle)
    return jsonify(result)

@app.route('/api/ai-unfollow', methods=['POST'])
def ai_unfollow():
    if not bluesky_client.is_logged_in:
        return jsonify({"status": "error", "message": "Pro AI Unfollow je nutné být přihlášen."})
    data = request.get_json()
    target_handle = data.get('handle', 'olduser.bsky.social') # Příklad handle
    # Zde by AI vybrala účet k unfollow
    result = bluesky_client.unfollow(target_handle)
    return jsonify(result)

if __name__ == '__main__':
    # Pro development
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
else:
    # Pro production s gunicorn
    application = app
