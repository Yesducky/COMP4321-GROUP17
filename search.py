import re
import math
from nltk.stem import PorterStemmer
from model import db, BodyInvertedIndex, TitleInvertedIndex, Page, DocumentStats
from collections import defaultdict
from indexer import parse_query

stemmer = PorterStemmer()


def get_phrase_count(phrase_terms, page_id, index_class, session):
    """Count occurrences of a phrase in a document."""
    # Get positions of all terms in one batch query
    stems = [stemmer.stem(term) for term in phrase_terms]
    entries = session.query(index_class).filter(
        index_class.stem.in_(stems),
        index_class.page_id == page_id
    ).all()

    # Exit early if we're missing any term
    if len(entries) != len(stems):
        return 0

    # Map stems to their positions
    positions = {entry.stem: entry.positions for entry in entries}

    # Check for consecutive positions
    first_stem = stems[0]
    count = 0
    for pos in positions.get(first_stem, []):
        if all(pos+i in positions.get(stems[i], []) for i in range(1, len(stems))):
            count += 1
    return count


def search(query_string):
    """Search documents using vector space model with title preference."""
    session = db.session
    query_parts = parse_query(query_string)

    # Extract terms and phrases
    terms = [content for part_type, content in query_parts if part_type == 'term']
    phrases = [content for part_type, content in query_parts if part_type == 'phrase']

    # Initialize score tracking
    title_scores = defaultdict(float)
    body_scores = defaultdict(float)
    title_lengths = defaultdict(float)
    body_lengths = defaultdict(float)
    query_vector_length = 0
    total_docs = session.query(Page).count() or 1  # Avoid division by zero

    # Process individual terms
    if terms:
        stems = [stemmer.stem(term) for term in terms]

        # Get document frequencies in batch
        df_records = session.query(DocumentStats).filter(
            DocumentStats.stem.in_(stems)
        ).all()
        df_map = {record.stem: (record.df_title or 1, record.df_body or 1) for record in df_records}

        # Process each term
        for term in terms:
            stem = stemmer.stem(term)
            if stem not in df_map:
                continue

            df_title, df_body = df_map[stem]

            # Calculate query weight
            query_weight = math.log(1 + (total_docs / df_body))
            query_vector_length += query_weight ** 2

            # Process title matches
            title_entries = session.query(TitleInvertedIndex).filter_by(stem=stem).all()
            for entry in title_entries:
                page = session.query(Page).get(entry.page_id)
                if not page or not page.max_tf_title:
                    continue

                weight = (0.5 + 0.5 * (entry.frequency / page.max_tf_title)) * math.log(1 + (total_docs / df_title))
                title_scores[entry.page_id] += weight * query_weight
                title_lengths[entry.page_id] += weight ** 2

            # Process body matches
            body_entries = session.query(BodyInvertedIndex).filter_by(stem=stem).all()
            for entry in body_entries:
                page = session.query(Page).get(entry.page_id)
                if not page or not page.max_tf_body:
                    continue

                weight = (0.5 + 0.5 * (entry.frequency / page.max_tf_body)) * math.log(1 + (total_docs / df_body))
                body_scores[entry.page_id] += weight * query_weight
                body_lengths[entry.page_id] += weight ** 2

    # Process phrases
    for phrase in phrases:
        phrase_terms = re.findall(r'\w+', phrase)
        if not phrase_terms:
            continue

        # Find candidate documents using first term
        first_stem = stemmer.stem(phrase_terms[0])
        df_record = session.query(DocumentStats).filter_by(stem=first_stem).first()
        if not df_record:
            continue

        # Query weight for phrase
        phrase_query_weight = math.log(1 + (total_docs / (df_record.df_body or 1)))
        query_vector_length += phrase_query_weight ** 2

        # Get candidate documents
        title_ids = [id[0] for id in session.query(TitleInvertedIndex.page_id).filter_by(stem=first_stem).all()]
        body_ids = [id[0] for id in session.query(BodyInvertedIndex.page_id).filter_by(stem=first_stem).all()]
        candidate_docs = set(title_ids + body_ids)

        # Check phrase matches
        for page_id in candidate_docs:
            page = session.query(Page).get(page_id)
            if not page:
                continue

            # Score title matches
            title_count = get_phrase_count(phrase_terms, page_id, TitleInvertedIndex, session)
            if title_count > 0 and page.max_tf_title:
                weight = (0.5 + 0.5 * (title_count / page.max_tf_title)) * math.log(1 + (total_docs / (df_record.df_title or 1)))
                title_scores[page_id] += weight * phrase_query_weight
                title_lengths[page_id] += weight ** 2

            # Score body matches
            body_count = get_phrase_count(phrase_terms, page_id, BodyInvertedIndex, session)
            if body_count > 0 and page.max_tf_body:
                weight = (0.5 + 0.5 * (body_count / page.max_tf_body)) * math.log(1 + (total_docs / (df_record.df_body or 1)))
                body_scores[page_id] += weight * phrase_query_weight
                body_lengths[page_id] += weight ** 2

    # Combine scores with title bias
    query_vector_length = math.sqrt(query_vector_length) or 1  # Avoid division by zero
    final_scores = {}

    all_doc_ids = set(title_scores.keys()) | set(body_scores.keys())
    for doc_id in all_doc_ids:
        title_norm = math.sqrt(title_lengths[doc_id]) * query_vector_length
        body_norm = math.sqrt(body_lengths[doc_id]) * query_vector_length

        title_score = title_scores[doc_id] / title_norm if title_norm > 0 else 0
        body_score = body_scores[doc_id] / body_norm if body_norm > 0 else 0

        # Title matches weighted 3x more than body matches
        final_scores[doc_id] = title_score * 3 + body_score

    # Return top 50 results
    sorted_ids = sorted(final_scores.keys(), key=lambda x: final_scores[x], reverse=True)[:50]
    results = session.query(Page).filter(Page.id.in_(sorted_ids)).all()

    return [(page, final_scores[page.id]) for page in
            sorted(results, key=lambda p: final_scores[p.id], reverse=True)]