import re
import math
import shlex
from nltk.stem import PorterStemmer
from nltk.util import ngrams
from model import db, BodyInvertedIndex, TitleInvertedIndex, Page, DocumentStats
from collections import defaultdict
from indexer import parse_query

stemmer = PorterStemmer()


def get_phrase_score(phrase_terms, page_id, index_class, session):
    positions = {}
    for term in phrase_terms:
        stem = stemmer.stem(term)
        entry = session.query(index_class).filter_by(stem=stem, page_id=page_id).first()
        if not entry:
            return 0
        positions[stem] = entry.positions

    first_stem = stemmer.stem(phrase_terms[0])
    count = 0
    for pos in positions.get(first_stem, []):
        valid = True
        for i in range(1, len(phrase_terms)):
            expected_pos = pos + i
            stem = stemmer.stem(phrase_terms[i])
            if expected_pos not in positions.get(stem, []):
                valid = False
                break
        if valid:
            count += 1
    return count


def calculate_tfidf(page_id, terms, phrases, session):
    total_docs = session.query(Page).count()
    scores = {'title': 0, 'body': 0}
    page = session.query(Page).get(page_id)

    # Calculate TF-IDF for terms
    # Lecture note L03 p.14 Improved Term Weights
    for term in terms:
        stem = stemmer.stem(term)

        # Title score
        title_entry = session.query(TitleInvertedIndex).filter_by(stem=stem, page_id=page_id).first()
        if title_entry:
            tf_title = title_entry.frequency
            df_title = session.query(DocumentStats.df_title).filter_by(stem=stem).scalar()
            scores['title'] += (0.5 + 0.5 * (tf_title / page.max_tf_title)) * math.log(1 + (total_docs / df_title))

        # Body score
        body_entry = session.query(BodyInvertedIndex).filter_by(stem=stem, page_id=page_id).first()
        if body_entry:
            tf_body = body_entry.frequency
            df_body = session.query(DocumentStats.df_body).filter_by(stem=stem).scalar()
            scores['body'] += (0.5+ 0.5*(tf_body / page.max_tf_body)) *  math.log(1+(total_docs / df_body))


    # Calculate phrase scores
    for phrase in phrases:
        phrase_terms = re.findall(r'\w+', phrase)
        stemmed_phrase = [stemmer.stem(t) for t in phrase_terms]

        # Title phrase score
        title_count = get_phrase_score(phrase_terms, page_id, TitleInvertedIndex, session)
        if title_count > 0:
            df_phrase_title = session.query(DocumentStats.df_title).filter_by(stem=stemmed_phrase[0]).scalar() or 0
            scores['title'] += (0.5 + 0.5 * (title_count / page.max_tf_title)) * math.log(1 + (total_docs / df_phrase_title))

        # Body phrase score
        body_count = get_phrase_score(phrase_terms, page_id, BodyInvertedIndex, session)
        if body_count > 0:
            df_phrase_body = session.query(DocumentStats.df_body).filter_by(stem=stemmed_phrase[0]).scalar() or 0
            print(f"body_count: {body_count}, max_tf_body: {page.max_tf_body}, df_phrase_body: {df_phrase_body}")
            scores['body'] += (0.5 + 0.5 * (body_count / page.max_tf_body)) * math.log(1 + (total_docs / df_phrase_body))

    return scores['title'] + scores['body']


def search(query_string, session=None):
    session = session or db.session
    query_parts = parse_query(query_string)

    terms = []
    phrases = []
    for part_type, content in query_parts:
        if part_type == 'term':
            terms.extend(re.findall(r'\w+', content))
        else:
            phrases.append(content)

    print(query_parts)

    all_stems = {stemmer.stem(t) for t in terms}
    for phrase in phrases:
        all_stems.update(stemmer.stem(t) for t in re.findall(r'\w+', phrase))

    candidates = set()
    for stem in all_stems:
        title_matches = session.query(TitleInvertedIndex.page_id).filter_by(stem=stem).all()
        body_matches = session.query(BodyInvertedIndex.page_id).filter_by(stem=stem).all()
        candidates.update([m[0] for m in title_matches + body_matches])

    doc_scores = {}
    for page_id in candidates:
        score = calculate_tfidf(page_id, terms, phrases, session)
        doc_scores[page_id] = score

    sorted_ids = sorted(doc_scores.keys(), key=lambda x: doc_scores[x], reverse=True)[:50]
    pages = session.query(Page).filter(Page.id.in_(sorted_ids)).all()

    return [(page, doc_scores[page.id]) for page in sorted(pages, key=lambda p: doc_scores[p.id], reverse=True)]
