from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

class Page(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    url = db.Column(db.String(1024), unique=True, nullable=False)
    title = db.Column(db.String(256))
    last_modified = db.Column(db.String(128))
    size = db.Column(db.Integer)
    keywords = db.Column(db.JSON)
    title_stems = db.Column(db.JSON)  # Stores stemmed title terms with positions
    body_stems = db.Column(db.JSON)   # Stores stemmed body terms with positions
    parent_id = db.Column(db.Integer, db.ForeignKey('page.id'), nullable=True)
    children = db.relationship('Page', backref=db.backref('parent', remote_side=[id]), lazy=True)

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