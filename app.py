from flask import Flask, render_template, request, redirect, url_for
from flask_socketio import SocketIO, emit
from model import db, Page, ChildLink
from spider import crawl
from threading import Thread

URL = "https://comp4321-hkust.github.io/testpages/ust_cse.htm"
is_crawling = False

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db.init_app(app)
socketio = SocketIO(app)

@app.cli.command('init-db')
def initialize_database():
    db.drop_all()
    db.create_all()

@app.route('/')
def index():
    # return render_template('index.html')
    return redirect(url_for('spider'))

@app.route('/spider')
def spider():
    pages = Page.query.all()
    return render_template('spider.html', pages=pages, crawling_url = URL, is_crawling = is_crawling)

@app.route('/start', methods=['POST'])
def start_crawl():
    def crawl_and_notify():
        global is_crawling
        with app.app_context():
            is_crawling = True
            print(is_crawling)
            crawl(URL, socketio)
            is_crawling = False
            print(is_crawling)

    Thread(target=crawl_and_notify).start()
    return redirect(url_for('index'))

@app.route('/clear_database', methods=['POST'])
def clear_database():
    db.session.query(ChildLink).delete()
    db.session.query(Page).delete()
    db.session.commit()
    socketio.emit('update', {'data': 'Database cleared'})
    return redirect(url_for('index'))

if __name__ == '__main__':
    socketio.run(app, debug=True)