from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

class Page(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    url = db.Column(db.String(1024), unique=True, nullable=False)
    title = db.Column(db.String(256))
    last_modified = db.Column(db.String(128))
    size = db.Column(db.Integer)
    keywords = db.Column(db.Text)
    title_stems = db.Column(db.JSON)  # Stores stemmed title terms with positions
    body_stems = db.Column(db.JSON)   # Stores stemmed body terms with positions

    children = db.relationship('ChildLink', backref='parent', lazy='dynamic')

class ChildLink(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    parent_id = db.Column(db.Integer, db.ForeignKey('page.id'))
    child_url = db.Column(db.String(1024))

class BodyInvertedIndex(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    stem = db.Column(db.String(100), index=True)
    page_id = db.Column(db.Integer, db.ForeignKey('page.id'))
    positions = db.Column(db.JSON)
    frequency = db.Column(db.Integer)

class TitleInvertedIndex(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    stem = db.Column(db.String(100), index=True)
    page_id = db.Column(db.Integer, db.ForeignKey('page.id'))
    positions = db.Column(db.JSON)
    frequency = db.Column(db.Integer)
