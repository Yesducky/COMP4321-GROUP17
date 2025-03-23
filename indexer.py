import re
from nltk.stem import PorterStemmer
from model import db, BodyInvertedIndex, TitleInvertedIndex

STOP_WORDS = set()
with open('stopwords.txt', 'r') as f:
    STOP_WORDS = {line.strip().lower() for line in f if line.strip()}
stemmer = PorterStemmer()

def process_terms(terms):
    stems = []
    positions = {}
    for pos, term in enumerate(terms):
        if term.lower() in STOP_WORDS:
            continue
        stem = stemmer.stem(term)
        stems.append(stem)
        if stem not in positions:
            positions[stem] = []
        positions[stem].append(pos)
    return stems, positions

def update_inverted_index(stem_map, page_id, index_class, session=None):
    # Use provided session or default to db.session
    session = session or db.session
    for stem, positions in stem_map.items():
        # Use session.query instead of class.query
        index_entry = session.query(index_class).filter_by(stem=stem, page_id=page_id).first()
        if not index_entry:
            index_entry = index_class(stem=stem, page_id=page_id, positions=[], frequency=0)
            session.add(index_entry)
        index_entry.positions.extend(positions)
        index_entry.frequency += len(positions)
