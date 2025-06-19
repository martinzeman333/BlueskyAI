from flask import Flask, render_template
import os

app = Flask(__name__, static_folder='static', static_url_path='/static')

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/health')
def health():
    return {'status': 'ok'}

# API endpoint pro budoucí funkcionality
@app.route('/api/ai-post', methods=['POST'])
def ai_post():
    return {'message': 'AI Post functionality coming soon'}

@app.route('/api/ai-like', methods=['POST'])  
def ai_like():
    return {'message': 'AI Like functionality coming soon'}

@app.route('/api/ai-comment', methods=['POST'])
def ai_comment():
    return {'message': 'AI Comment functionality coming soon'}

@app.route('/api/ai-follow', methods=['POST'])
def ai_follow():
    return {'message': 'AI Follow functionality coming soon'}

@app.route('/api/ai-unfollow', methods=['POST'])
def ai_unfollow():
    return {'message': 'AI Unfollow functionality coming soon'}

if __name__ == '__main__':
    # Pro development
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
else:
    # Pro production s gunicorn
    application = app
