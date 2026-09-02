#!/usr/bin/env python3
"""OBOR page-first source ingestion.

Official publication pages are the primary collection surface. RSS/Atom is optional
and may be used first when configured, but failures fall through to HTML pages.
No third-party feed is required.
"""
import hashlib, html, json, re, time
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin
from urllib.request import Request, urlopen
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'data'
RAW = DATA / 'raw'
RAW.mkdir(exist_ok=True)

UA = 'OBOR/0.3 (+https://obor.ca; economic-intelligence collector)'
TIMEOUT = 20
RETRIES = 2
MAX_ITEMS = 100


def clean(value):
    value = html.unescape(value or '')
    value = re.sub(r'<[^>]+>', ' ', value)
    return re.sub(r'\s+', ' ', value).strip()


def iso_date(value):
    if not value:
        return None
    value = clean(value)
    for parser in (
        lambda x: parsedate_to_datetime(x).astimezone(timezone.utc),
        lambda x: datetime.fromisoformat(x.replace('Z', '+00:00')).astimezone(timezone.utc),
    ):
        try:
            return parser(value).isoformat()
        except Exception:
            pass
    return None


def date_from_text(value):
    value = clean(value)
    patterns = [
        r'\b(20\d{2})[-/](\d{2})[-/](\d{2})\b',
        r'\b(20\d{2})\.(\d{2})\.(\d{2})\b',
    ]
    for pattern in patterns:
        m = re.search(pattern, value)
        if m:
            return f'{m.group(1)}-{m.group(2)}-{m.group(3)}T00:00:00+00:00'
    return iso_date(value)


def date_from_url(url):
    m = re.search(r'/((?:20)\d{2})[/-](\d{2})[/-](\d{2})(?:/|[-_.])', url)
    if m:
        return f'{m.group(1)}-{m.group(2)}-{m.group(3)}T00:00:00+00:00'
    m = re.search(r'/(20\d{2})(\d{2})(\d{2})[-_/]', url)
    if m:
        return f'{m.group(1)}-{m.group(2)}-{m.group(3)}T00:00:00+00:00'
    return None


def fetch(url):
    last = None
    headers = {
        'User-Agent': UA,
        'Accept': 'text/html,application/xhtml+xml,application/atom+xml,application/rss+xml,application/xml;q=0.9,*/*;q=0.1',
        'Accept-Language': 'en-CA,en;q=0.8',
        'Cache-Control': 'no-cache',
    }
    for attempt in range(RETRIES + 1):
        try:
            req = Request(url, headers=headers)
            with urlopen(req, timeout=TIMEOUT) as response:
                return response.read(), response.headers.get('Content-Type', ''), response.status
        except (HTTPError, URLError, TimeoutError, OSError) as exc:
            last = exc
            if attempt < RETRIES:
                time.sleep(1.5 * (attempt + 1))
    raise last


def node_text(node, names):
    for child in list(node):
        tag = child.tag.rsplit('}', 1)[-1].lower()
        if tag in names:
            return clean(''.join(child.itertext()))
    return ''


def node_link(node, base_url):
    for child in list(node):
        tag = child.tag.rsplit('}', 1)[-1].lower()
        if tag != 'link':
            continue
        href = child.attrib.get('href')
        rel = child.attrib.get('rel', 'alternate')
        if href and rel in ('alternate', 'self'):
            return urljoin(base_url, href)
        value = clean(''.join(child.itertext()))
        if value:
            return urljoin(base_url, value)
    return ''


def make_item(title, url, description, published_at, source):
    key = hashlib.sha256((url + '|' + title).encode()).hexdigest()[:20]
    return {
        'id': 'raw-' + key,
        'title': clean(title),
        'url': url,
        'description': clean(description),
        'published_at': published_at,
        'source': source['name'],
        'source_url': source.get('url', ''),
        'source_type': source['source_type'],
        'country': source['country'],
        'collected_at': datetime.now(timezone.utc).isoformat(),
    }


def parse_xml(body, source):
    root = ET.fromstring(body)
    out = []
    for node in root.iter():
        if node.tag.rsplit('}', 1)[-1].lower() not in ('item', 'entry'):
            continue
        title = node_text(node, {'title'})
        url = node_link(node, source.get('url', ''))
        desc = node_text(node, {'description', 'summary', 'content', 'encoded'})
        published = node_text(node, {'pubdate', 'published', 'updated', 'date', 'issued', 'modified'})
        if title and url:
            out.append(make_item(title, url, desc, iso_date(published) or date_from_url(url), source))
        if len(out) >= MAX_ITEMS:
            break
    if not out:
        raise ValueError('XML contained no usable items')
    return out


class AnchorCollector(HTMLParser):
    def __init__(self, base_url):
        super().__init__(convert_charrefs=True)
        self.base_url = base_url
        self.links = []
        self.href = None
        self.text = []

    def handle_starttag(self, tag, attrs):
        if tag.lower() != 'a':
            return
        attrs = dict(attrs)
        href = attrs.get('href')
        if href:
            self.href = urljoin(self.base_url, href)
            self.text = []

    def handle_data(self, data):
        if self.href:
            self.text.append(data)

    def handle_endtag(self, tag):
        if tag.lower() == 'a' and self.href:
            title = clean(' '.join(self.text))
            self.links.append((title, self.href))
            self.href = None
            self.text = []


def parse_html(body, source, page_url):
    parser = AnchorCollector(page_url)
    parser.feed(body.decode('utf-8', errors='replace'))
    seen = set()
    out = []
    include = [x.lower() for x in source.get('include_url_terms', [])]
    exclude = [x.lower() for x in source.get('exclude_url_terms', [])]
    title_exclude = [x.lower() for x in source.get('exclude_title_terms', [])]
    page_root = page_url.rstrip('/')

    for title, url in parser.links:
        low_url, low_title = url.lower(), title.lower()
        if len(title) < source.get('min_title_length', 18):
            continue
        if include and not any(term in low_url or term in low_title for term in include):
            continue
        if exclude and any(term in low_url for term in exclude):
            continue
        if title_exclude and any(term in low_title for term in title_exclude):
            continue
        if url.rstrip('/') == page_root or url in seen:
            continue
        if not url.startswith(('http://', 'https://')):
            continue
        seen.add(url)
        out.append(make_item(title, url, '', date_from_url(url), source))
        if len(out) >= MAX_ITEMS:
            break

    if not out:
        raise ValueError('HTML page contained no matching article links')
    return out


def dedupe(items):
    seen_urls, seen_titles, result = set(), set(), []
    for item in sorted(items, key=lambda x: (x.get('published_at') or '', x.get('title') or ''), reverse=True):
        url = item.get('url', '').strip()
        title = re.sub(r'[^a-z0-9]+', ' ', item.get('title', '').lower()).strip()
        if not url or url in seen_urls or title in seen_titles:
            continue
        seen_urls.add(url); seen_titles.add(title); result.append(item)
    return result


def load_json(path, default):
    try:
        return json.loads(path.read_text())
    except Exception:
        return default


def collect_source(source):
    errors = []
    # Page-first: try configured pages in order. RSS is optional, never mandatory.
    for page_url in source.get('page_urls', []):
        try:
            body, ctype, status = fetch(page_url)
            items = parse_html(body, source, page_url)
            return items, 'html', status, ctype, errors
        except Exception as exc:
            errors.append(f'page {page_url}: {exc}')

    # Optional feed fallback.
    for feed_url in source.get('feed_urls', []):
        try:
            body, ctype, status = fetch(feed_url)
            items = parse_xml(body, source)
            return items, 'xml-fallback', status, ctype, errors
        except Exception as exc:
            errors.append(f'feed {feed_url}: {exc}')

    raise ValueError(' | '.join(errors) if errors else 'no collection endpoints configured')


def main():
    sources = load_json(DATA / 'sources.json', [])
    previous = load_json(RAW / 'items.json', [])
    all_items, errors, health = [], [], []
    successes = 0
    enabled = [s for s in sources if s.get('enabled')]

    for source in enabled:
        started = time.time()
        try:
            items, method, status, ctype, attempts = collect_source(source)
            all_items.extend(items)
            successes += 1
            health.append({'source': source['name'], 'status': 'ok', 'method': method,
                           'http_status': status, 'items': len(items), 'content_type': ctype,
                           'attempt_errors': attempts, 'seconds': round(time.time()-started, 2)})
            print(f"{source['name']}: {len(items)} items ({method})")
        except Exception as exc:
            msg = str(exc)
            errors.append({'source': source['name'], 'error': msg})
            health.append({'source': source['name'], 'status': 'error', 'items': 0,
                           'error': msg, 'seconds': round(time.time()-started, 2)})
            print(f"WARN {source['name']}: {msg}")

    new_items = dedupe(all_items)
    if new_items:
        merged = dedupe(new_items + previous)[:500]
        state = 'success' if successes == len(enabled) else 'degraded'
    else:
        merged = previous
        state = 'failed_preserved_previous' if previous else 'failed_no_data'

    log = {
        'collected_at': datetime.now(timezone.utc).isoformat(),
        'state': state,
        'sources_enabled': len(enabled),
        'sources_succeeded': successes,
        'items_new': len(new_items),
        'items_cached': len(merged),
        'errors': errors,
        'health': health,
    }
    (RAW / 'items.json').write_text(json.dumps(merged, ensure_ascii=False, indent=2))
    (RAW / 'ingest_log.json').write_text(json.dumps(log, ensure_ascii=False, indent=2))

    if successes == 0 and not previous:
        print('COLLECTION FAILED: no sources succeeded and no previous collection exists')
    else:
        print(f'Collection state: {state}; new={len(new_items)} cached={len(merged)}')


if __name__ == '__main__':
    main()
