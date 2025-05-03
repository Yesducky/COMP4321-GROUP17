import re
import math
from nltk.stem import PorterStemmer
from model import db, BodyInvertedIndex, TitleInvertedIndex, DocumentStats, Page
from collections import defaultdict
from nltk.util import ngrams
import shlex


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


def update_stats(stem_map, index_type, session):
    for stem in stem_map.keys():
        stats = session.query(DocumentStats).filter_by(stem=stem).first()
        if not stats:
            stats = DocumentStats(stem=stem, df_title=0, df_body=0)
            session.add(stats)

        if index_type == 'title':
            stats.df_title += 1
        else:
            stats.df_body += 1


def update_inverted_index(stem_map, page_id, index_class, session):
    max_freq = 0
    for stem, positions in stem_map.items():
        index_entry = session.query(index_class).filter_by(stem=stem, page_id=page_id).first()
        freq = len(positions)
        max_freq = max(max_freq, freq)

        if not index_entry:
            index_entry = index_class(stem=stem, page_id=page_id, positions=positions, frequency=freq)
            session.add(index_entry)
        else:
            index_entry.positions.extend(positions)
            index_entry.frequency += freq

    page = session.query(Page).get(page_id)
    if index_class == TitleInvertedIndex:
        page.max_tf_title = max(page.max_tf_title, max_freq)
    else:
        page.max_tf_body = max(page.max_tf_body, max_freq)
    session.add(page)


def parse_query(query):
    explicit_phrases = re.findall(r'"([^"]+)"', query.lower())

    remaining_text = re.sub(r'"[^"]+"', '', query.lower())

    remaining_terms = [t for t in re.findall(r'\w+', remaining_text) if t not in STOP_WORDS]

    ngram_phrases = []
    for n in [2, 3]:
        if len(remaining_terms) >= n:
            ngram_phrases.extend(' '.join(gram) for gram in ngrams(remaining_terms, n))

    all_phrases = list(set(explicit_phrases + ngram_phrases))

    return [('phrase', p) for p in all_phrases] + [('term', t) for t in remaining_terms]
