import os
from model import db, Page

def output_records_to_txt(file_path='spider_result.txt'):
    pages = Page.query.limit(30).all()
    with open(file_path, 'w', encoding='utf-8') as f:
        for page in pages:
            f.write(f"Page title: {page.title}\n")
            f.write(f"URL: {page.url}\n")
            f.write(f"Last modified date: {page.last_modified}, size of page: {page.size} words\n")
            f.write("Keywords: ")
            keywords = [f"{keyword['stem']} ({keyword['frequency']})" for keyword in page.keywords]
            f.write("; ".join(keywords) + "\n")
            f.write(f"Parent {page.parent.url if page.parent else 'None'}\n")
            if page.children:
                children_urls = [child.url for child in page.children]
                f.write("\n".join(f"Child {url}" for url in children_urls) + "\n")
            else:
                f.write("None\n")
            f.write("------------------------------------------------------------------------------------\n")