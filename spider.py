import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from collections import deque, Counter
from model import db, Page, ChildLink
import re


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

        #have to modifed (e.g. idk why it treat "s" as a word)
        text = soup.get_text()
        words = re.findall(r'\w+', text.lower())


        size = len(words)
        word_counts = Counter(words)
        top_keywords = word_counts.most_common(10)
        keywords_str = '; '.join([f"{word} {count}" for word, count in top_keywords])

        page = Page(
            url=url,
            title=title,
            last_modified=last_modified,
            size=size,
            keywords=keywords_str
        )
        db.session.add(page)
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
