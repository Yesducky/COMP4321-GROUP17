import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from collections import deque, Counter
from model import db, Page, ChildLink, TitleInvertedIndex, BodyInvertedIndex
from indexer import stemmer
import re
STOP_WORDS = set()
from indexer import STOP_WORDS, stemmer, process_terms, update_inverted_index


def crawl(start_url):
    domain = urlparse(start_url).netloc
    queue = deque([start_url])
    visited = set()

    while queue:
        url = queue.popleft()

        if url in visited:
            continue
        visited.add(url)

        # Skip existing pages
        if Page.query.filter_by(url=url).first():
            continue

        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
        except:
            continue

        soup = BeautifulSoup(response.text, features="html.parser")

        title = soup.title.string if soup.title else 'No Title'
        last_modified = response.headers.get('Last-Modified', 'N/A')

        # Process title text
        title_terms = re.findall(r'\w+', title.lower())
        title_stems = []
        title_positions = {}
        
        # Process body text
        body = soup.find('body')
        body_text = body.get_text() if body else ''
        body_terms = re.findall(r'\w+', body_text.lower())
        body_stems = []
        body_positions = {}
        
        # Process terms with stemming and position tracking
        title_stems, title_positions = process_terms(title_terms)
        body_stems, body_positions = process_terms(body_terms)

        # Calculate top 10 most frequent stemmed keywords from body text
        body_stem_freq = {stem: len(positions) for stem, positions in body_positions.items()}
        top_keywords = Counter(body_stem_freq).most_common(10)
        
        page = Page(
            url=url,
            title=title,
            last_modified=last_modified,
            size=len(body_terms),  # Original word count before processing
            keywords=[{"stem": stem, "frequency": freq} for stem, freq in top_keywords],
            title_stems={"stems": title_stems, "positions": title_positions},
            body_stems={"stems": body_stems, "positions": body_positions}
        )
        
        # Create inverted index entries

        db.session.add(page)
        db.session.flush()  # Get page ID after adding to session
        update_inverted_index(title_positions, page.id, TitleInvertedIndex)
        update_inverted_index(body_positions, page.id, BodyInvertedIndex)
        db.session.commit()

        # Extract and save child links
        links = set()
        for link in soup.find_all('a', href=True):
            absolute_url = urljoin(url, link['href'])
            parsed = urlparse(absolute_url)
            if parsed.netloc == domain and parsed.scheme in ('http', 'https'):
                links.add(absolute_url)

        for link in links:
            db.session.add(ChildLink(parent_id=page.id, child_url=link))
        db.session.commit()

        # Add new links to queue
        queue.extend([link for link in links if link not in visited])
