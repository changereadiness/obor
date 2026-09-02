#!/usr/bin/env python3
"""Resilient, dependency-free source ingestion for OBOR.

The collector prefers RSS/Atom/API feeds, but can fall back to source pages when
feeds are malformed or blocked. A single source failure never erases the last
successful collection.
"""
import hashlib
import html
import json
import re
import time
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

UA = 'OBOR/0.2 (+https://obor.ca; economic-intelligence feed collector)'
TIMEOUT = 25
RETRIES = 3
MAX_ITEMS = 100


def clean(value):
    value = html.unescape(value or '')
    value = re.sub(r'<[^>]+>', ' ', value)
    return re.sub(r'\s+', ' ', value).strip()


def iso_date(value):
    if not value:
        return None
    value = clean(value)
    try:
        return parsedate_to_datetime(value).astimezone(timezone.utc).isoformat()
    except Exception:
        pass
    try:
        return datetime.fromisoformat(value.replace('Z', '+00:00')).astimezone(timezone.utc).isoformat()
    except Exception:
        return None


def extract_date(value):
    value = clean(value)
    patterns = [
        r'\b(20\d{2}-\d{2}-\d{2})\b',
        r'\b(20\d{2}/\d{2}/\d{2})\b',
        r'\b(20\d{2}-\d{2}-\d{2}T[^\s]+)\b',
    ]
    for pattern in patterns:
        match = re.search(pattern, value)
        if match:
            return iso_date(match.group(1))
    return iso_date(value)


def fetch(url):
    last_error = None
    headers = {
        'User-Agent': UA,
        'Accept': 'application/atom+xml,application/rss+xml,application/xml,text/xml,text/html;q=0.9,*/*;q=0.1',
        'Accept-Language': 'en-CA,en;q=0.8',
        'Cache-Control': 'no-cache',
    }
    for attempt in range(1, RETRIES + 1):
        try:
            req = Request(url, headers=headers)
            with urlopen(req, timeout=TIMEOUT) as response:
                body = response.read()
                content_type = response.headers.get('Content-Type', '')
                return body, content_type, response.status
        except (HTTPError, URLError, TimeoutError, OSError) as exc:
            last_error = exc
            if attempt < RETRIES:
                time.sleep(2 ** (attempt - 1))
    raise last_error


def node_text(node, names):
    for child in list(node):
        tag = child.tag.rsplit('}', 1)[-1].lower()
        if tag in names:
            return clean(''.join(child.itertext()))
    return ''


def node_link(node, base_url=''):
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


def parse_xml(body, source):
    root = ET.fromstring(body)
    nodes = []
    for node in root.iter():
        tag = node.tag.rsplit('}', 1)[-1].lower()
        if tag in ('item', 'entry'):
            nodes.append(node)

    out = []
    for node in nodes[:MAX_ITEMS]:
        title = node_text(node, {'title'})
        url = node_link(node, source.get('url', ''))
        description = node_text(node, {'description', 'summary', 'content', 'encoded'})
        published = node_text(node, {'pubdate', 'published', 'updated', 'date', 'issued', 'modified'})
        if not title or not url:
            continue
        out.append(make_item(title, url, description, iso_date(published), source))
    if not out:
        raise ValueError('XML parsed successfully but contained no usable items')
    return out


class LinkCollector(HTMLParser):
    """Small HTML fallback parser. It deliberately captures only anchors."""
    def __init__(self, base_url, source):
        super().__init__(convert_charrefs=True)
        self.base_url = base_url
        self.source = source
        self.items = []
        self.current_href = None
        self.current_text = []
        self.current_context = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag.lower() == 'a' and attrs.get('href'):
            self.current_href = urljoin(self.base_url, attrs['href'])
            self.current_text = []
            self.current_context = []
        elif self.current_href:
            self.current_context.append(tag.lower())

    def handle_data(self, data):
        if self.current_href:
            self.current_text.append(data)

    def handle_endtag(self, tag):
        if tag.lower() == 'a' and self.current_href:
            title = clean(' '.join(self.current_text))
            url = self.current_href
            context = clean(' '.join(self.current_text))
            if title and len(title) >= 12 and url.startswith(('http://', 'https://')):
                self.items.append((title, url, context))
            self.current_href = None
            self.current_text = []
            self.current_context = []


def parse_html(body, source):
    parser = LinkCollector(source['page_url'], source)
    parser.feed(body.decode('utf-8', errors='replace'))
    seen = set()
    out = []
    include = [x.lower() for x in source.get('include_url_terms', [])]
    exclude = [x.lower() for x in source.get('exclude_url_terms', [])]

    for title, url, context in parser.items:
        low_url = url.lower()
        low_title = title.lower()
        if include and not any(term in low_url or term in low_title for term in include):
            continue
        if exclude and any(term in low_url for term in exclude):
            continue
        if url.rstrip('/') == source.get('page_url', '').rstrip('/'):
            continue
        if url in seen:
            continue
        seen.add(url)
        out.append(make_item(title, url, context, extract_date(context), source))
        if len(out) >= MAX_ITEMS:
            break

    if not out:
        raise ValueError('HTML page contained no matching article links')
    return out


def make_item(title, url, description, published_at, source):
    key = hashlib.sha256((url + '|' + title).encode()).hexdigest()[:20]
    return {
        'id': 'raw-' + key,
        'title': clean(title),
        'url': url,
        'description': clean(description),
        'published_at': published_at,
        'source': source['name'],
        'source_url': source.get('url', source.get('feed_url', source.get('page_url', ''))),
        'source_type': source['source_type'],
        'country': source['country'],
        'collected_at': datetime.now(timezone.utc).isoformat(),
    }


def dedupe(items):
    seen_urls = set()
    seen_titles = set()
    result = []
    for item in sorted(items, key=lambda x: x.get('published_at') or '', reverse=True):
        url = item.get('url', '').strip()
        title = re.sub(r'[^a-z0-9]+', ' ', item.get('title', '').lower()).strip()
        fingerprint = hashlib.sha1(title.encode()).hexdigest()[:16]
        if not url or url in seen_urls or fingerprint in seen_titles:
            continue
        seen_urls.add(url)
        seen_titles.add(fingerprint)
        result.append(item)
    return result


def load_json(path, default):
    try:
        return json.loads(path.read_text())
    except Exception:
        return default


def collect_source(source):
    adapter = source.get('adapter', 'rss_atom')
    primary_url = source.get('feed_url') or source.get('page_url')
    body, content_type, status = fetch(primary_url)

    if adapter in ('api_atom', 'rss_atom'):
        try:
            return parse_xml(body, source), 'xml', status, content_type
        except Exception as xml_error:
            fallback = source.get('fallback')
            if not fallback:
                raise ValueError(f'XML parse failed: {xml_error}')
            body2, content_type2, status2 = fetch(fallback)
            return parse_html(body2, {**source, 'page_url': fallback}), 'html-fallback', status2, content_type2

    if adapter == 'html_list':
        return parse_html(body, source), 'html', status, content_type

    raise ValueError(f'Unknown adapter: {adapter}')



def main():
    sources = load_json(DATA / 'sources.json', [])
    previous_items = load_json(RAW / 'items.json', [])
    all_items = []
    errors = []
    health = []
    successes = 0

    for source in sources:
        if not source.get('enabled'):
            continue
        started = time.time()
        try:
            parsed, method, status, content_type = collect_source(source)
            all_items.extend(parsed)
            successes += 1
            health.append({
                'source': source['name'], 'status': 'ok', 'method': method,
                'http_status': status, 'items': len(parsed),
                'content_type': content_type, 'seconds': round(time.time() - started, 2)
            })
            print(f"{source['name']}: {len(parsed)} items ({method})")
        except Exception as exc:
            error = str(exc)
            errors.append({'source': source['name'], 'url': source.get('feed_url') or source.get('page_url'), 'error': error})
            health.append({
                'source': source['name'], 'status': 'error',
                'items': 0, 'error': error, 'seconds': round(time.time() - started, 2)
            })
            print(f"WARN {source['name']}: {error}")

    new_items = dedupe(all_items)
    previous_by_url = {x.get('url'): x for x in previous_items if x.get('url')}

    # Preserve the last successful collection. Never replace a healthy cache with an empty run.
    if new_items:
        merged = dedupe(new_items + list(previous_by_url.values()))[:500]
        collection_state = 'success' if successes == len([s for s in sources if s.get('enabled')]) else 'degraded'
    else:
        merged = previous_items
        collection_state = 'failed_preserved_previous' if previous_items else 'failed_no_data'

    log = {
        'collected_at': datetime.now(timezone.utc).isoformat(),
        'state': collection_state,
        'sources_enabled': len([s for s in sources if s.get('enabled')]),
        'sources_succeeded': successes,
        'items_new': len(new_items),
        'items_cached': len(merged),
        'errors': errors,
        'health': health,
    }

    (RAW / 'items.json').write_text(json.dumps(merged, ensure_ascii=False, indent=2))
    (RAW / 'ingest_log.json').write_text(json.dumps(log, ensure_ascii=False, indent=2))

    if successes == 0 and not previous_items:
        print('COLLECTION FAILED: no sources succeeded and no previous collection exists')
    else:
        print(f"Collection state: {collection_state}; new={len(new_items)} cached={len(merged)}")

if __name__ == "__main__":
    main()
