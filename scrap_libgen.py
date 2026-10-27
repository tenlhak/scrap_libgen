import os
import re
import time
from urllib.parse import urljoin, quote_plus

import requests
from bs4 import BeautifulSoup
import pandas as pd
from tqdm import tqdm


output_dir = 'downloaded_books_libgen'  # name your output dir
file_path = 'YorBookList.xlsx'          # Excel file with a 'Title' column
preferred_exts = ('pdf', 'epub')        # tried first, in this order; otherwise first result is used
delay_between_books = 2                 # seconds, be polite to the mirrors
timeout = 15                            # seconds per request

# Mirrors that share the current libgen.li page layout. Tried in order; the first
# one that answers is used for each book. Add or remove entries as mirrors come and go.
MIRRORS = [
    'https://libgen.vg',
    'https://libgen.li',
    'https://libgen.la',
    'https://libgen.bz',
    'https://libgen.gl',
]

HEADERS = {'User-Agent': 'Mozilla/5.0'}
session = requests.Session()
session.headers.update(HEADERS)


def search_mirror(mirror, book_title):
    """Search one mirror. Returns a list of result dicts, or raises on network/parse failure."""
    url = f"{mirror}/index.php?req={quote_plus(book_title)}&res=25&filesuns=all"
    response = session.get(url, timeout=timeout)
    response.raise_for_status()
    soup = BeautifulSoup(response.content, 'html.parser')

    table = soup.find('table', id='tablelibgen')
    if table is None:
        raise ValueError('results table not found (layout differs or mirror returned an error page)')

    results = []
    for row in table.find_all('tr')[1:]:
        cols = row.find_all('td')
        if len(cols) < 9:
            continue
        title_tag = cols[0].find('a', href=re.compile(r'edition\.php'))
        title = title_tag.text.strip() if title_tag else 'No Title'
        author = cols[1].get_text(strip=True)
        ext = cols[7].get_text(strip=True).lower()
        ads = row.find('a', href=re.compile(r'ads\.php\?md5='))
        if ads:
            results.append({'title': title, 'author': author, 'ext': ext,
                            'ads_url': urljoin(mirror + '/', ads['href'])})
    return results


def pick_best(results):
    for ext in preferred_exts:
        for r in results:
            if r['ext'] == ext:
                return r
    return results[0] if results else None


def resolve_download_url(ads_url):
    """The ads.php page contains the real, time-limited get.php link."""
    response = session.get(ads_url, timeout=timeout)
    response.raise_for_status()
    soup = BeautifulSoup(response.content, 'html.parser')
    link = soup.find('a', href=re.compile(r'get\.php\?md5='))
    if link is None:
        raise ValueError('no get.php link on download page')
    return urljoin(ads_url, link['href'])


def download_book(url, output_path):
    with session.get(url, stream=True, timeout=timeout) as response:
        response.raise_for_status()
        if 'text/html' in response.headers.get('Content-Type', ''):
            raise ValueError('got an HTML page instead of a file')
        total = int(response.headers.get('Content-Length', 0)) or None
        try:
            with open(output_path, 'wb') as f, tqdm(
                    total=total, unit='B', unit_scale=True, unit_divisor=1024,
                    desc=os.path.basename(output_path)[:40], leave=False) as bar:
                for chunk in response.iter_content(chunk_size=1024 * 64):
                    if chunk:
                        f.write(chunk)
                        bar.update(len(chunk))
        except Exception:
            # don't leave a half-written file behind when falling back to the next mirror
            if os.path.exists(output_path):
                os.remove(output_path)
            raise


def fetch_book(book_title):
    """Try each mirror in turn until one search + download succeeds."""
    for mirror in MIRRORS:
        try:
            tqdm.write(f"  [{mirror}] searching...")
            results = search_mirror(mirror, book_title)
            best = pick_best(results)
            if best is None:
                tqdm.write(f"  [{mirror}] no results")
                continue

            tqdm.write(f"  [{mirror}] found: {best['title']} by {best['author']} ({best['ext']})")
            download_url = resolve_download_url(best['ads_url'])

            safe_title = "".join(c for c in best['title'] if c.isalnum() or c in (' ', '-', '_')).strip()[:100]
            output_path = os.path.join(output_dir, f"{safe_title or book_title}.{best['ext'] or 'bin'}")
            download_book(download_url, output_path)
            tqdm.write(f"  Downloaded: {output_path}")
            return True
        except Exception as e:
            tqdm.write(f"  [{mirror}] failed: {type(e).__name__}: {e}")
    return False


def main():
    os.makedirs(output_dir, exist_ok=True)
    book_titles = pd.read_excel(file_path)['Title'].dropna().astype(str).tolist()

    failed = []
    for book_title in tqdm(book_titles, desc='Books', unit='book'):
        tqdm.write(f"Searching for: {book_title}")
        if not fetch_book(book_title):
            failed.append(book_title)
        tqdm.write('-' * 40)
        time.sleep(delay_between_books)

    print(f"Done. {len(book_titles) - len(failed)}/{len(book_titles)} downloaded.")
    if failed:
        print("Failed:", ', '.join(failed))


if __name__ == '__main__':
    main()
