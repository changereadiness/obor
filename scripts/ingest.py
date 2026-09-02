#!/usr/bin/env python3
"""Fetch enabled RSS/Atom feeds and normalize them into data/raw/items.json.
No third-party dependencies: stdlib XML parsing only.
"""
import json, re, time, hashlib
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.request import Request, urlopen
import xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/'data'
RAW=DATA/'raw'; RAW.mkdir(exist_ok=True)
UA='OBOR/0.1 (+https://obor.ca; economic-intelligence feed collector)'

def clean(s):
    return re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', ' ', s or '')).strip()

def iso_date(value):
    if not value: return None
    try:
        return parsedate_to_datetime(value).astimezone(timezone.utc).isoformat()
    except Exception: pass
    try:
        return datetime.fromisoformat(value.replace('Z','+00:00')).astimezone(timezone.utc).isoformat()
    except Exception: return None

def text(node, names):
    for child in list(node):
        tag=child.tag.rsplit('}',1)[-1].lower()
        if tag in names:
            return clean(''.join(child.itertext()))
    return ''

def link(node):
    for child in list(node):
        tag=child.tag.rsplit('}',1)[-1].lower()
        if tag=='link':
            href=child.attrib.get('href')
            if href: return href
            val=clean(''.join(child.itertext()))
            if val: return val
    return ''

def parse_feed(xml, source):
    root=ET.fromstring(xml)
    nodes=[]
    for n in root.iter():
        tag=n.tag.rsplit('}',1)[-1].lower()
        if tag in ('item','entry'): nodes.append(n)
    out=[]
    for n in nodes[:100]:
        title=text(n, {'title'}); url=link(n)
        desc=text(n, {'description','summary','content','encoded'})
        published=text(n, {'pubdate','published','updated','date','issued','modified'})
        if not title or not url: continue
        key=hashlib.sha256((url+'|'+title).encode()).hexdigest()[:20]
        out.append({'id':'raw-'+key,'title':title,'url':url,'description':desc,'published_at':iso_date(published),
                    'source':source['name'],'source_url':source.get('url',source['feed_url']),
                    'source_type':source['source_type'],'country':source['country'],'collected_at':datetime.now(timezone.utc).isoformat()})
    return out

sources=json.loads((DATA/'sources.json').read_text())
items=[]; errors=[]
for s in sources:
    if not s.get('enabled'): continue
    try:
        req=Request(s['feed_url'], headers={'User-Agent':UA,'Accept':'application/atom+xml,application/rss+xml,application/xml,text/xml'})
        with urlopen(req, timeout=20) as r: xml=r.read()
        parsed=parse_feed(xml,s); items.extend(parsed)
        print(f"{s['name']}: {len(parsed)} items")
    except Exception as e:
        errors.append({'source':s['name'],'feed_url':s['feed_url'],'error':str(e)})
        print(f"WARN {s['name']}: {e}")

seen=set(); dedup=[]
for x in sorted(items,key=lambda i:i.get('published_at') or '',reverse=True):
    norm=re.sub(r'[^a-z0-9]+',' ',x['title'].lower()).strip()
    fingerprint=hashlib.sha1(norm.encode()).hexdigest()[:16]
    if x['url'] in seen or fingerprint in seen: continue
    seen.add(x['url']); seen.add(fingerprint); dedup.append(x)
(RAW/'items.json').write_text(json.dumps(dedup,ensure_ascii=False,indent=2))
(RAW/'ingest_log.json').write_text(json.dumps({'collected_at':datetime.now(timezone.utc).isoformat(),'items':len(dedup),'errors':errors},indent=2))
