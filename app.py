from flask import Flask, render_template, request, redirect, url_for
from flask_socketio import SocketIO, emit
from model import db, Page, BodyInvertedIndex, TitleInvertedIndex, DocumentStats
from spider import crawl
from threading import Thread
import time
from sqlalchemy.pool import NullPool
from phase1 import output_records_to_txt
from search import search
import os
import requests
from flask import jsonify

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
            try:
                crawl(URL, socketio)
            except Exception as e:
                print(f"error: {e}")
            finally:
                print("finished")
                time.sleep(5)
                is_crawling = False
                socketio.emit('update', {'data': 'Crawling completed'})
    Thread(target=crawl_and_notify).start()
    return redirect(url_for('spider'))

@app.route('/clear_database', methods=['POST'])
def clear_database():
    db.session.query(Page).delete()
    db.session.query(BodyInvertedIndex).delete()
    db.session.query(TitleInvertedIndex).delete()
    db.session.query(DocumentStats).delete()
    db.session.commit()
    socketio.emit('update', {'data': 'Database cleared'})
    return redirect(url_for('spider'))

@app.route('/phase1', methods=['POST'])
def phase1():
    output_records_to_txt()
    return redirect(url_for('spider'))
    

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


@app.route('/chat', methods=['GET', 'POST'])
def chat():
    if request.method == 'GET':
        return render_template('chat.html')

    data = request.get_json()
    user_message = data.get('message', '')

    # Step 1: Use AI to extract search keywords from the question
    DEEPSEEK_API_KEY = os.environ.get('DEEPSEEK_API_KEY', 'sk-9a1925a117ba4039b90328dd065a06bc')
    api_url = 'https://api.deepseek.com/v1/chat/completions'
    headers = {
        'Authorization': f'Bearer {DEEPSEEK_API_KEY}',
        'Content-Type': 'application/json'
    }

    keyword_system_prompt = """You are a keyword extraction assistant. 
    Extract 3-5 most important search keywords from the user's question. 
    Return ONLY the keywords separated by spaces, no other text or explanation."""

    payload = {
        'model': 'deepseek-chat',
        'messages': [
            {'role': 'system', 'content': keyword_system_prompt},
            {'role': 'user', 'content': user_message}
        ]
    }

    try:
        resp = requests.post(api_url, headers=headers, json=payload, timeout=10)
        resp.raise_for_status()
        keywords = resp.json()['choices'][0]['message']['content'].strip()
        print(f"Extracted keywords: {keywords}")
    except Exception as e:
        print(f"Error extracting keywords: {e}")
        # Fallback to using the entire query
        keywords = user_message

    # Step 2: Search the database with the AI-extracted keywords
    results = search(keywords)
    print(f"Search results for '{keywords}': {len(results)} results found")

    # Step 3: Build context from search results
    if results:
        context = "The following information is from our database:\n\n"

        # Get full content from top 3 results
        for i, (page, score) in enumerate(results[:3], 1):
            context += f"Document {i}: {page.title}\n"
            context += f"URL: {page.url}\n"

            # Try to fetch the actual page content
            try:
                if page.url.startswith(('http://', 'https://')):
                    response = requests.get(page.url, timeout=5)
                    if response.status_code == 200:
                        from bs4 import BeautifulSoup
                        soup = BeautifulSoup(response.text, 'html.parser')

                        # Remove script and style elements
                        for script in soup(["script", "style"]):
                            script.extract()

                        # Get text
                        page_text = soup.get_text(separator='\n', strip=True)
                        context += f"Page Content:\n{page_text}\n"
                    else:
                        context += f"Content could not be retrieved (HTTP {response.status_code})\n"
                else:
                    context += "URL not accessible (invalid URL format)\n"
            except Exception as e:
                # Fall back to keywords if we can't get the content
                if page.keywords:
                    if isinstance(page.keywords[0], list):
                        keywords_list = [f"{k[0]} ({k[1]})" for k in sorted(page.keywords, key=lambda x: -x[1])[:15]]
                    else:
                        keywords_list = [f"{k.get('stem', '')} ({k.get('frequency', 0)})" for k in
                                        sorted(page.keywords, key=lambda x: -x.get('frequency', 0))[:15]]
                    context += f"Keywords: {', '.join(keywords_list)}\n"
                context += f"Note: Full page content unavailable. Error: {str(e)[:100]}\n"

            # Add separator between documents
            context += "\n" + "-" * 40 + "\n\n"
    else:
        context = "No relevant information found in our database."

    # Step 4: Use AI to analyze the pages and respond to the question
    analysis_system_prompt = """You are a helpful assistant that provides information based on the database context provided.
    Only use the information in the given context to answer the user's question.
    If the context doesn't contain relevant information to answer the question, state that you don't have that information.
    Do not make up information or use knowledge outside of the provided context.
    Be concise and relevant in your responses.
    Present the answer in a clear, coherent, and informative manner."""

    payload = {
        'model': 'deepseek-chat',
        'messages': [
            {'role': 'system', 'content': analysis_system_prompt},
            {'role': 'user', 'content': f"Context:\n{context}\n\nQuestion: {user_message}"}
        ]
    }

    try:
        resp = requests.post(api_url, headers=headers, json=payload, timeout=30)
        resp.raise_for_status()
        reply = resp.json()['choices'][0]['message']['content']
    except Exception as e:
        reply = f'Error: {str(e)}'

    return jsonify({'reply': reply})

if __name__ == '__main__':
    socketio.run(app, debug=True, allow_unsafe_werkzeug=True)
