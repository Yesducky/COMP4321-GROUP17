import re
from nltk.stem import PorterStemmer
from model import db, BodyInvertedIndex, TitleInvertedIndex, Page

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


def search(query_string, session=None):
    session = session or db.session

    # Tokenize and stem the query
    query_terms = re.findall(r'\w+', query_string.lower())
    query_stems = [stemmer.stem(term) for term in query_terms if term not in STOP_WORDS]

    # Calculate document scores using tf-idf approach
    doc_scores = {}

    # Get all documents that contain any query term
    title_matches = session.query(TitleInvertedIndex).filter(TitleInvertedIndex.stem.in_(query_stems)).all()
    body_matches = session.query(BodyInvertedIndex).filter(BodyInvertedIndex.stem.in_(query_stems)).all()

    # Calculate scores for title matches (with higher weight)
    for match in title_matches:
        if match.page_id not in doc_scores:
            doc_scores[match.page_id] = 0
        # Apply higher weight to title matches
        doc_scores[match.page_id] += match.frequency * 2

    # Calculate scores for body matches
    for match in body_matches:
        if match.page_id not in doc_scores:
            doc_scores[match.page_id] = 0
        doc_scores[match.page_id] += match.frequency

    # Get the top 10 matching pages
    top_page_ids = sorted(doc_scores.keys(), key=lambda pid: doc_scores[pid], reverse=True)[:10]

    if not top_page_ids:
        return []

    # Fetch the actual page details
    top_pages = session.query(Page).filter(Page.id.in_(top_page_ids)).all()

    # Sort the results by score
    result_pages = sorted(top_pages, key=lambda p: doc_scores[p.id], reverse=True)

    return [(page, doc_scores[page.id]) for page in result_pages]