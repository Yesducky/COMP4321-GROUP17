import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import re
import queue
from threading import Lock, Thread
from sqlalchemy.orm import sessionmaker
from collections import Counter
from model import db, Page, TitleInvertedIndex, BodyInvertedIndex
from indexer import stemmer, process_terms, update_inverted_index, STOP_WORDS

def crawl(start_url, socketio):
    domain = urlparse(start_url).netloc
    url_queue = queue.Queue()
    url_queue.put((start_url, None))
    visited = set()
    visited_lock = Lock()
    db_lock = Lock()
    num_workers = 20
    poison_pill = (None, None)

    Session = sessionmaker(bind=db.engine)

    def worker():
        session = Session()
        try:
            while True:
                try:
                    item = url_queue.get(timeout=5)
                    if item == poison_pill:
                        url_queue.task_done()
                        break
                    url, parent_id = item
                except queue.Empty:
                    continue

                try:
                    with visited_lock:
                        # Check both visited set and database atomically
                        if url in visited or session.query(Page).filter_by(url=url).first():
                            url_queue.task_done()
                            continue
                        visited.add(url)

                    # Fetch page content
                    response = requests.get(url, timeout=10)
                    response.raise_for_status()

                    # Parse content
                    soup = BeautifulSoup(response.text, 'html.parser')
                    title = soup.title.string if soup.title else 'No Title'
                    last_modified = response.headers.get('Last-Modified', 'N/A')

                    # Process title
                    title_terms = re.findall(r'\w+', title.lower())
                    title_stems, title_positions = process_terms(title_terms)

                    # Process body
                    body = soup.find('body')
                    body_text = body.get_text() if body else ''
                    body_terms = re.findall(r'\w+', body_text.lower())
                    body_stems, body_positions = process_terms(body_terms)

                    # Calculate keywords
                    body_stem_freq = {stem: len(positions) for stem, positions in body_positions.items()}
                    top_keywords = Counter(body_stem_freq).most_common(10)

                    with db_lock:
                        try:
                            # Start transaction
                            session.begin_nested()

                            # Create page record
                            page = Page(
                                url=url,
                                title=title,
                                last_modified=last_modified,
                                size=len(body_terms),
                                keywords=[{"stem": stem, "frequency": freq} for stem, freq in top_keywords],
                                title_stems={"stems": title_stems, "positions": title_positions},
                                body_stems={"stems": body_stems, "positions": body_positions},
                                parent_id=parent_id
                            )

                            session.add(page)
                            session.flush()

                            # Update inverted indices
                            update_inverted_index(title_positions, page.id, TitleInvertedIndex, session)
                            update_inverted_index(body_positions, page.id, BodyInvertedIndex, session)

                            # Extract links before committing
                            links = set()
                            for link in soup.find_all('a', href=True):
                                absolute_url = urljoin(url, link['href'])
                                parsed = urlparse(absolute_url)
                                if parsed.netloc == domain and parsed.scheme in ('http', 'https'):
                                    links.add(absolute_url)

                            session.commit()

                            # Queue new URLs only after successful commit
                            for link in links:
                                url_queue.put((link, page.id))

                            socketio.emit('update', {'data': 'Crawled'})

                        except Exception as e:
                            session.rollback()
                            print(f"Database error processing {url}: {e}")

                except requests.RequestException as e:
                    print(f"Request error for {url}: {e}")
                except Exception as e:
                    print(f"General error processing {url}: {e}")
                finally:
                    url_queue.task_done()

        finally:
            session.close()

    # Start workers
    threads = []
    for _ in range(num_workers):
        t = Thread(target=worker, daemon=True)
        t.start()
        threads.append(t)

    # Wait for completion
    url_queue.join()

    # Stop workers
    for _ in range(num_workers):
        url_queue.put(poison_pill)

    for t in threads:
        t.join()

    # Final commit to ensure all data is saved
    final_session = Session()
    try:
        final_session.commit()
    finally:
        final_session.close()