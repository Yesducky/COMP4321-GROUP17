from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

class Page(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    url = db.Column(db.String(1024), unique=True, nullable=False)
    title = db.Column(db.String(256))
    last_modified = db.Column(db.String(128))
    size = db.Column(db.Integer)
    keywords = db.Column(db.JSON)
    parent_id = db.Column(db.Integer, db.ForeignKey('page.id'), nullable=True)
    children = db.relationship('Page', backref=db.backref('parent', remote_side=[id]), lazy=True)
    max_tf_title = db.Column(db.Integer, default=0)
    max_tf_body = db.Column(db.Integer, default=0)

class BaseIndex(db.Model):
    __abstract__ = True
    stem = db.Column(db.String(100), primary_key=True)
    page_id = db.Column(db.Integer, db.ForeignKey('page.id'), primary_key=True)
    positions = db.Column(db.JSON)
    frequency = db.Column(db.Integer)

class BodyInvertedIndex(BaseIndex):
    __tablename__ = 'body_inverted_index'

class TitleInvertedIndex(BaseIndex):
    __tablename__ = 'title_inverted_index'

class DocumentStats(db.Model):
    stem = db.Column(db.String(100), primary_key=True)
    df_title = db.Column(db.Integer, default=0)  # Document frequency in titles
    df_body = db.Column(db.Integer, default=0)   # Document frequency in bodies
