from flask import Flask, render_template, request, redirect, url_for
from flask_socketio import SocketIO, emit
from model import db, Page, BodyInvertedIndex, TitleInvertedIndex
from spider import crawl
from threading import Thread
import time
from sqlalchemy.pool import NullPool
from phase1 import output_records_to_txt
from search import search

URL = "https://comp4321-hkust.github.io/testpages/testpage.htm"
is_crawling = False

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
    'poolclass': NullPool,
    'connect_args': {'timeout': 30}  # Increase timeout
}
db.init_app(app)
socketio = SocketIO(app, cors_allowed_origins="*")

@app.cli.command('init-db')
def initialize_database():
    db.drop_all()
    db.create_all()

@app.route('/')
def index():
    return render_template('index.html')
    # return redirect(url_for('spider'))

@app.route('/search')
def search_page():
    query = request.args.get('query', '')
    if not query:
        return render_template('search.html', results=None)

    results = search(query)
    return render_template('search.html', results=results, query=query)

@app.route('/spider')
def spider():
    pages = Page.query.all()
    length = db.session.query(Page).count()
    return render_template('spider.html', pages=pages, crawling_url = URL, is_crawling = is_crawling, length = length)

@app.route('/start', methods=['POST'])
def start_crawl():
    def crawl_and_notify():
        global is_crawling
        with app.app_context():
            is_crawling = True
            print(is_crawling)
            crawl(URL, socketio)
            is_crawling = False
            time.sleep(2)
            socketio.emit('update', {'data': 'Crawling completed'})
    Thread(target=crawl_and_notify).start()
    return redirect(url_for('spider'))

@app.route('/clear_database', methods=['POST'])
def clear_database():
    db.session.query(Page).delete()
    db.session.query(BodyInvertedIndex).delete()
    db.session.query(TitleInvertedIndex).delete()
    db.session.commit()
    socketio.emit('update', {'data': 'Database cleared'})
    return redirect(url_for('spider'))

@app.route('/phase1', methods=['POST'])
def phase1():
    output_records_to_txt()
    return redirect(url_for('spider'))
    
@app.route('/chat', methods=['GET', 'POST'])
def chat():
    import os
    import requests
    from flask import jsonify
    if request.method == 'GET':
        return render_template('chat.html')
    data = request.get_json()
    user_message = data.get('message', '')
    DEEPSEEK_API_KEY = os.environ.get('DEEPSEEK_API_KEY', 'sk-9a1925a117ba4039b90328dd065a06bc')
    api_url = 'https://api.deepseek.com/v1/chat/completions'
    headers = {
        'Authorization': f'Bearer {DEEPSEEK_API_KEY}',
        'Content-Type': 'application/json'
    }
    payload = {
        'model': 'deepseek-chat',
        'messages': [
            {'role': 'user', 'content': user_message}
        ]
    }
    try:
        resp = requests.post(api_url, headers=headers, json=payload, timeout=30)
        resp.raise_for_status()
        reply = resp.json()['choices'][0]['message']['content']
    except Exception as e:
        reply = 'Error: ' + str(e)
    return jsonify({'reply': reply})

@app.route('/get_similar', methods=['POST'])
def get_similar():
    from indexer import STOP_WORDS
    page_id = request.form.get('page_id')
    original_query = request.form.get('original_query', '')
    if not page_id:
        return redirect(url_for('search_page', query=original_query))
    page = Page.query.get(page_id)
    if not page or not page.keywords:
        return redirect(url_for('search_page', query=original_query))
    # Flatten and filter stopwords
    keywords = []
    for kw in page.keywords:
        if isinstance(kw, dict):
            stem = kw.get('stem')
            freq = kw.get('frequency', 0)
        else:
            stem = kw[0]
            freq = kw[1]
        if stem and stem.lower() not in STOP_WORDS:
            keywords.append((stem, freq))
    # Sort by frequency, take top 5
    keywords = sorted(keywords, key=lambda x: -x[1])
    top_keywords = [k[0] for k in keywords[:5]]
    if not top_keywords:
        return redirect(url_for('search_page', query=original_query))
    # Join keywords as new query
    revised_query = ' '.join(top_keywords)
    return redirect(url_for('search_page', query=revised_query))

if __name__ == '__main__':
    socketio.run(app, debug=True)
