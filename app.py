from flask import Flask, render_template, request, redirect, url_for
from model import db, Page, ChildLink
from spider import crawl

URL = "https://www.cse.ust.hk/~kwtleung/COMP4321/testpage.htm"

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db.init_app(app)

@app.cli.command('init-db')
def initialize_database():
    db.create_all()

@app.route('/')
def index():
    pages = Page.query.all()
    page_parent_map = {}
    # for page in pages:
    #     all_parents = ChildLink.query.filter_by(child_url=page.url).all()
    #     parents = [Page.query.get(p.parent_id) for p in all_parents]
    #     page_parent_map[page.url] = parents
    return render_template('index.html', pages=pages, page_parent_map=page_parent_map)

@app.route('/start', methods=['POST'])
def start_crawl():
    # Thread(target=crawl, args=(url,)).start()
    crawl(URL)
    return redirect(url_for('index'))

@app.route('/clear_database', methods=['POST'])
def clear_database():
    db.session.query(ChildLink).delete()
    db.session.query(Page).delete()
    db.session.commit()
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(debug=True)
