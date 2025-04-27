import re
import math
import shlex
from nltk.stem import PorterStemmer
from nltk.util import ngrams
from model import db, BodyInvertedIndex, TitleInvertedIndex, Page, DocumentStats
from collections import defaultdict
from indexer import parse_query

stemmer = PorterStemmer()


def get_phrase_count(phrase_terms, page_id, index_class, session):
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


def search(query_string):
    session = db.session
    query_parts = parse_query(query_string)

    terms = []
    phrases = []
    for part_type, content in query_parts:
        if part_type == 'term':
            terms.extend(re.findall(r'\w+', content))
        else:
            phrases.append(content)

    print(query_parts)

    # Initialize separate scores for title and body
    title_scores = defaultdict(float)
    body_scores = defaultdict(float)
    title_lengths = defaultdict(float)
    body_lengths = defaultdict(float)
    query_vector_length = 0
    total_docs = session.query(Page).count()

    # Process each term in the query
    for term in terms:
        stem = stemmer.stem(term)

        # Look up term in inverted index
        title_entries = session.query(TitleInvertedIndex).filter_by(stem=stem).all()
        body_entries = session.query(BodyInvertedIndex).filter_by(stem=stem).all()

        # Skip if term not found
        if not title_entries and not body_entries:
            continue

        # Get document frequencies
        df_title = session.query(DocumentStats.df_title).filter_by(stem=stem).scalar()
        df_body = session.query(DocumentStats.df_body).filter_by(stem=stem).scalar()

        # Calculate query weight (IDF)
        query_weight = math.log(1 + (total_docs / df_body))
        query_vector_length += query_weight ** 2

        # Process title postings
        for entry in title_entries:
            page = session.query(Page).get(entry.page_id)
            if not page or not page.max_tf_title:
                continue

            # Calculate TF-IDF
            tf_weight = 0.5 + 0.5 * (entry.frequency / page.max_tf_title)
            idf_weight = math.log(1 + (total_docs / df_title))
            weight = tf_weight * idf_weight

            # Add to title score
            title_scores[entry.page_id] += weight * query_weight
            title_lengths[entry.page_id] += weight ** 2

        # Process body postings
        for entry in body_entries:
            page = session.query(Page).get(entry.page_id)
            if not page or not page.max_tf_body:
                continue

            # Calculate TF-IDF
            tf_weight = 0.5 + 0.5 * (entry.frequency / page.max_tf_body)
            idf_weight = math.log(1 + (total_docs / df_body))
            weight = tf_weight * idf_weight

            # Add to body score
            body_scores[entry.page_id] += weight * query_weight
            body_lengths[entry.page_id] += weight ** 2

    # Process phrases similarly
    for phrase in phrases:
        phrase_terms = re.findall(r'\w+', phrase)
        if not phrase_terms:
            continue

        # Get documents containing first term as candidates
        first_stem = stemmer.stem(phrase_terms[0])
        candidate_docs = set()
        title_matches = session.query(TitleInvertedIndex.page_id).filter_by(stem=first_stem).all()
        body_matches = session.query(BodyInvertedIndex.page_id).filter_by(stem=first_stem).all()
        candidate_docs.update([m[0] for m in title_matches + body_matches])

        # Query weight for phrase
        df = session.query(DocumentStats.df_body).filter_by(stem=first_stem).scalar()
        phrase_query_weight = math.log(1 + (total_docs / df))
        query_vector_length += phrase_query_weight ** 2

        # Check phrase in each candidate document
        for page_id in candidate_docs:
            page = session.query(Page).get(page_id)
            if not page:
                continue

            # Get phrase counts
            title_count = get_phrase_count(phrase_terms, page_id, TitleInvertedIndex, session)
            body_count = get_phrase_count(phrase_terms, page_id, BodyInvertedIndex, session)

            # Add to scores if phrase found
            if title_count > 0 and page.max_tf_title:
                df_title = session.query(DocumentStats.df_title).filter_by(stem=first_stem).scalar()
                weight = (0.5 + 0.5 * (title_count / page.max_tf_title)) * math.log(1 + (total_docs / df_title))
                title_scores[page_id] += weight * phrase_query_weight
                title_lengths[page_id] += weight ** 2

            if body_count > 0 and page.max_tf_body:
                df_body = session.query(DocumentStats.df_body).filter_by(stem=first_stem).scalar()
                print(df_body, phrase, body_count, page.title)
                weight = (0.5 + 0.5 * (body_count / page.max_tf_body)) * math.log(1 + (total_docs / df_body))
                body_scores[page_id] += weight * phrase_query_weight
                body_lengths[page_id] += weight ** 2

    # Normalize scores separately
    query_vector_length = math.sqrt(query_vector_length)
    final_scores = {}

    # Combine normalized title and body scores (cosine similarity)
    all_doc_ids = set(title_scores.keys()) | set(body_scores.keys())
    for doc_id in all_doc_ids:
        # Calculate normalized title score
        title_score = 0
        if doc_id in title_scores and title_lengths[doc_id] > 0:
            title_score = title_scores[doc_id] / (math.sqrt(title_lengths[doc_id]) * query_vector_length)

        # Calculate normalized body score
        body_score = 0
        if doc_id in body_scores and body_lengths[doc_id] > 0:
            body_score = body_scores[doc_id] / (math.sqrt(body_lengths[doc_id]) * query_vector_length)

        # Combine scores with weights (favor title more)
        final_scores[doc_id] = title_score * 2 + body_score

    # Return top results
    sorted_ids = sorted(final_scores.keys(), key=lambda x: final_scores[x], reverse=True)[:50]
    pages = session.query(Page).filter(Page.id.in_(sorted_ids)).all()

    return [(page, final_scores[page.id]) for page in
            sorted(pages, key=lambda p: final_scores[p.id], reverse=True)]