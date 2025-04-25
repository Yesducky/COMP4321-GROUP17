import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import re
import queue
from threading import Lock, Thread
from sqlalchemy.orm import sessionmaker
from collections import Counter
from model import db, Page, TitleInvertedIndex, BodyInvertedIndex
from indexer import stemmer, process_terms, update_inverted_index, STOP_WORDS, update_stats

def crawl(start_url, socketio):
    domain = urlparse(start_url).netloc
    url_queue = queue.Queue()
    url_queue.put((start_url, None))
    visited = set()
    visited_lock = Lock()
    db_lock = Lock()
    num_workers = 5
    poison_pill = (None, None)

    Session = sessionmaker(bind=db.engine)

    def worker():
        session = Session()
        try:
            while True:
                url = None
                parent_id = None
                try:
                    # Get URL from queue with timeout
                    url, parent_id = url_queue.get(timeout=5)

                    # Check for poison pill immediately
                    if url is None:
                        break

                    # Process only if not already visited
                    with visited_lock:
                        already_visited = url in visited or session.query(Page).filter_by(url=url).first()
                        # Mark as visited before processing to prevent race conditions
                        if not already_visited:
                            visited.add(url)

                    if already_visited:
                        continue

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
                                keywords=Counter(
                                    {stem: len(positions) for stem, positions in body_positions.items()}).most_common(
                                    10),
                                parent_id=parent_id,
                                max_tf_title=max(len(v) for v in title_positions.values()) if title_positions else 0,
                                max_tf_body=max(len(v) for v in body_positions.values()) if body_positions else 0
                            )
                            session.add(page)
                            session.flush()

                            # Update inverted indices
                            update_inverted_index(title_positions, page.id, TitleInvertedIndex, session)
                            update_inverted_index(body_positions, page.id, BodyInvertedIndex, session)
                            update_stats(title_positions, 'title', session)
                            update_stats(body_positions, 'body', session)

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

                            socketio.emit('update', {'data': 'Crawled ' + url})

                        except Exception as e:
                            session.rollback()
                            print(f"Database error processing {url}: {e}")

                except queue.Empty:
                    # Just continue waiting for new items
                    continue
                except requests.RequestException as e:
                    print(f"Request error for {url}: {e}")
                except Exception as e:
                    print(f"General error processing {url}: {e}")
                finally:
                    # Always mark task as done if we got a URL from the queue
                    if url is not None:
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
        # No need to emit here, app.py will handle the completion message
    finally:
        final_session.close()

    return True