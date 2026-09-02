#!/usr/bin/env python3
"""OBOR v9 synthesis layer.

Turns a screened source item into an evidence-backed economic signal.
No LLM is required: source pages are fetched, article text is extracted,
key numeric facts are parsed, and the signal is synthesized deterministically.
"""
import re, html, time
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
from html.parser import HTMLParser
from urllib.parse import urlparse

RETRIES = 2
TIMEOUT = 15
UA = 'Mozilla/5.0 (compatible; OBOR/0.9; +https://obor.ca/)'

class TextExtractor(HTMLParser):
    SKIP = {'script','style','noscript','svg','nav','footer','header','form','aside'}
    BLOCK = {'p','div','article','section','li','h1','h2','h3','h4','h5','h6','br','tr'}
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.skip = 0
        self.parts = []
        self.title = ''
        self.in_title = False
    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        if tag == 'title': self.in_title = True
        if tag in self.SKIP: self.skip += 1
    def handle_endtag(self, tag):
        tag = tag.lower()
        if tag == 'title': self.in_title = False
        if tag in self.SKIP and self.skip: self.skip -= 1
        if tag in self.BLOCK and self.skip == 0: self.parts.append('\n')
    def handle_data(self, data):
        if self.skip: return
        value = re.sub(r'\s+', ' ', data).strip()
        if not value: return
        if self.in_title: self.title += ' ' + value
        else: self.parts.append(value)

def fetch(url):
    last = None
    for attempt in range(RETRIES + 1):
        try:
            req = Request(url, headers={'User-Agent': UA, 'Accept': 'text/html,application/xhtml+xml'})
            with urlopen(req, timeout=TIMEOUT) as r:
                return r.read(), r.headers.get('Content-Type',''), r.status
        except (HTTPError, URLError, TimeoutError, OSError) as exc:
            last = exc
            if attempt < RETRIES: time.sleep(1.2 * (attempt + 1))
    raise last

def clean_text(body):
    parser = TextExtractor(); parser.feed(body.decode('utf-8', errors='replace'))
    text = re.sub(r'\s+', ' ', ' '.join(parser.parts)).strip()
    return text, re.sub(r'\s+', ' ', parser.title).strip()

def sentences(text):
    return [s.strip() for s in re.split(r'(?<=[.!?。！？])\s+', text) if len(s.strip()) >= 30]

def parse_number(token):
    try: return float(token.replace(',',''))
    except: return None

def extract_facts(text):
    facts = []
    # Percentages and percentage-point changes.
    pat = re.compile(r'(?P<num>[+-]?\d+(?:,\d{3})*(?:\.\d+)?)\s*(?P<pct>%|percent|percentage points?)', re.I)
    for m in pat.finditer(text):
        sentence = next((s for s in sentences(text) if m.group(0) in s), '')
        if sentence:
            facts.append({'value': m.group('num'), 'unit': m.group('pct'), 'text': sentence[:500]})
    # Currency/large-number figures, e.g. 28.77 trillion yuan / RMB 1.2 trillion.
    pat2 = re.compile(r'(?P<currency>RMB|CNY|yuan|¥|US\$|USD|dollars?)?\s*(?P<num>\d+(?:,\d{3})*(?:\.\d+)?)\s*(?P<scale>trillion|billion|million|万亿元|亿元|million yuan|billion yuan|trillion yuan)', re.I)
    for m in pat2.finditer(text):
        sentence = next((s for s in sentences(text) if m.group(0) in s), '')
        if sentence:
            facts.append({'value': m.group('num'), 'unit': (m.group('currency') or '').strip() + ' ' + m.group('scale'), 'text': sentence[:500]})
    # Index values such as PMI 49.8 or index at 102.4.
    pat3 = re.compile(r'\b(?P<label>PMI|index|index of)\b[^.]{0,80}?\b(?P<num>\d+(?:\.\d+)?)\b', re.I)
    for m in pat3.finditer(text):
        sentence = next((s for s in sentences(text) if m.group(0) in s), '')
        if sentence:
            facts.append({'value': m.group('num'), 'unit': m.group('label'), 'text': sentence[:500]})
    # Deduplicate exact fact sentences.
    out=[]; seen=set()
    for f in facts:
        key=(f['value'],f['unit'],f['text'])
        if key not in seen: seen.add(key); out.append(f)
    return out[:30]

def find_relevant_sentences(title, text, max_sent=8):
    ss = sentences(text)
    keys = [k.lower() for k in re.findall(r'[A-Za-z]{4,}', title)]
    scored=[]
    for s in ss:
        low=s.lower(); score=0
        if '%' in s or re.search(r'\b(trillion|billion|million|yuan|rmb|index|pmi)\b', low): score += 4
        score += sum(1 for k in keys if k in low)
        if re.search(r'year on year|year-over-year|yoy|month on month|compared with|increased|decreased|rose|fell|growth|decline|up |down ', low): score += 3
        scored.append((score,s))
    return [s for _,s in sorted(scored, reverse=True)[:max_sent]]

def synthesize(item):
    result = dict(item)
    url = item.get('url','')
    try:
        body, ctype, status = fetch(url)
        text, page_title = clean_text(body)
        if len(text) < 300:
            raise ValueError('source page yielded insufficient text')
        facts = extract_facts(text)
        rel = find_relevant_sentences(item.get('title',''), text)
        result['source_content'] = {
            'status': 'fetched', 'http_status': status, 'content_type': ctype,
            'text_length': len(text), 'page_title': page_title,
            'facts': facts, 'relevant_sentences': rel,
        }
        result['synthesis_status'] = 'evidence_available' if facts or rel else 'insufficient_evidence'
    except Exception as exc:
        result['source_content'] = {'status':'error','error':str(exc),'facts':[],'relevant_sentences':[]}
        result['synthesis_status'] = 'source_unavailable'
    return result

def choose_facts(item):
    facts=item.get('source_content',{}).get('facts',[])
    # Prefer percentages, then monetary/scale figures, then index values.
    pct=[f for f in facts if '%' in f['unit'].lower() or 'percent' in f['unit'].lower()]
    other=[f for f in facts if f not in pct]
    return (pct + other)[:8]

def build_signal_fields(item):
    content=item.get('source_content',{})
    facts=choose_facts(item)
    rel=content.get('relevant_sentences',[])
    title=item.get('title','')
    lower=' '.join(rel).lower()
    # Headline: use a source-specific metric when possible, never the raw release title.
    pct_values=[]
    for f in facts:
        if '%' in f['unit'].lower() or 'percent' in f['unit'].lower():
            try: pct_values.append(float(f['value']))
            except: pass
    headline = title.rstrip('.')
    if 'retail sales' in lower or 'retail sales' in title.lower():
        headline = 'China retail growth remains subdued'
    elif 'purchasing managers' in lower or 'pmi' in title.lower():
        headline = 'China factory activity remains near contraction territory'
    elif 'industrial profits' in lower or 'profits of industrial enterprises' in title.lower():
        headline = 'China industrial profits show continued pressure'
    elif 'industrial production' in lower or 'industrial production' in title.lower():
        headline = 'China industrial output provides a fresh read on factory demand'
    elif 'fixed asset investment' in title.lower():
        headline = 'China investment growth offers a mixed signal for domestic demand'
    elif 'real estate' in title.lower() or 'property' in title.lower():
        headline = 'China property investment remains a drag on domestic activity'
    elif 'new economic growth drivers' in title.lower():
        headline = 'China reports continued expansion of its new growth drivers'
    elif pct_values:
        v=pct_values[0]
        headline=f'{title.split(" from ")[0].strip()} shows a {v:g}% movement'
    else:
        headline = re.sub(r'\s+', ' ', title).strip().rstrip('.')

    what = rel[0] if rel else (item.get('description') or title)
    # Add up to three distinct numerical facts, keeping the source wording intact enough to be traceable.
    extras=[]
    seen=set()
    for f in facts:
        sentence=f['text']
        if sentence == what or sentence in seen: continue
        seen.add(sentence); extras.append(sentence)
        if len(extras)>=3: break
    if extras:
        what = what + ' ' + ' '.join(extras)
    what = what[:1100]

    data_points=[]
    for f in facts[:8]:
        data_points.append({'value':f['value'],'unit':f['unit'],'context':f['text'][:300]})

    # Conservative interpretation: distinguish observed movement from inferred implication.
    if pct_values and any(v < 1 for v in pct_values):
        interpretation='The latest data point indicates limited momentum in the measured activity, although individual subcategories may be performing differently.'
    elif any(v < 50 for v in pct_values):
        interpretation='The reported movement points to weaker conditions in the measured activity relative to a stronger growth environment.'
    else:
        interpretation='The latest release provides a current measure of economic activity and shows how performance is evolving across the reported period or categories.'

    sector=', '.join(item.get('sectors',['Other'])[:3]).lower()
    canadian=f'The source does not explicitly establish a Canada-specific effect. For Canadian businesses in {sector}, the data is a watchpoint because changes in Chinese demand, production, investment or pricing can affect market conditions, suppliers and competitive dynamics.'
    return headline, what, interpretation, data_points, canadian
