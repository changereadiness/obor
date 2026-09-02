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
MAX_SOURCE_BYTES = 5 * 1024 * 1024
UA = 'Mozilla/5.0 (compatible; OBOR/0.9; +https://obor.ca/)'


def fetch(url):
    """Fetch a source page with retries and return (body, content_type, status)."""
    if not url:
        raise ValueError('empty source URL')
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

def clean_text(body):
    """Extract readable page text and HTML title from an HTML response."""
    if isinstance(body, bytes):
        source = body.decode('utf-8', errors='replace')
    else:
        source = str(body)
    parser = TextExtractor()
    parser.feed(source)
    parser.close()
    text = re.sub(r'\n{3,}', '\n\n', '\n'.join(parser.parts))
    text = re.sub(r'[ \t]+', ' ', text)
    return text.strip(), re.sub(r'\s+', ' ', parser.title).strip()


def _number_value(raw):
    value = raw.replace(',', '').strip()
    try:
        return float(value)
    except ValueError:
        return None


def extract_facts(text):
    """Extract conservative numeric facts from readable source text.

    This is deliberately generic: it only records values that are visibly
    expressed as percentages, index readings, or currency/large-number
    amounts. Structured tables are handled separately.
    """
    facts = []
    seen = set()
    sentences = re.split(r'(?<=[.!?])\s+', text)
    patterns = [
        (re.compile(r'([+-]?\d+(?:\.\d+)?)\s*%'), '%', '%'),
        (re.compile(r'\bPMI\s*(?:was|stood at|came in at|registered)?\s*([0-9]+(?:\.[0-9]+)?)', re.I), 'index', 'PMI'),
        (re.compile(r'(?:¥|CNY|RMB|yuan)\s*([0-9][0-9,]*(?:\.[0-9]+)?)\s*(trillion|billion|million|thousand)?', re.I), 'currency', 'CNY'),
    ]
    for sentence in sentences:
        sentence = re.sub(r'\s+', ' ', sentence).strip()
        if not sentence or len(sentence) < 12:
            continue
        for pattern, unit, label in patterns:
            for m in pattern.finditer(sentence):
                raw = m.group(1)
                value = _number_value(raw)
                if value is None:
                    continue
                # Ignore percentages that are plainly product specifications
                # or composition values; the dedicated table parser handles
                # economic rates when the source presents them in tables.
                if unit == '%' and re.search(r'\b(?:content|purity|grade|concentration|composition|specification)\b', sentence, re.I):
                    continue
                key = (value, unit, sentence[:240])
                if key in seen:
                    continue
                seen.add(key)
                facts.append({
                    'value': raw,
                    'unit': unit,
                    'text': sentence[:500],
                    'source_kind': 'text',
                    'label': label,
                })
                if len(facts) >= 30:
                    return facts
    return facts


def find_relevant_sentences(title, text):
    """Rank source sentences against the release title and economic vocabulary."""
    sentences = [re.sub(r'\s+', ' ', s).strip() for s in re.split(r'(?<=[.!?])\s+', text)]
    sentences = [s for s in sentences if len(s) >= 40]
    title_terms = {t for t in re.findall(r'[a-zA-Z]{4,}', title.lower())
                   if t not in {'from','january','february','march','april','may','june','july','august','september','october','november','december','china'}}
    economic_terms = {
        'growth','decline','increase','decrease','rose','fell','rising','falling','output',
        'production','sales','investment','demand','price','prices','profit','profits','pmi',
        'export','exports','import','imports','trade','market','manufacturing','consumption',
        'activity','industrial','business','revenue','employment','unemployment','index'
    }
    scored = []
    for idx, sentence in enumerate(sentences):
        low = sentence.lower()
        title_hits = sum(1 for term in title_terms if term in low)
        econ_hits = sum(1 for term in economic_terms if term in low)
        numeric = bool(re.search(r'\d', sentence))
        movement = bool(re.search(r'\b(?:up|down|rose|fell|increased|decreased|grew|declined|growth|change|higher|lower)\b', low))
        score = title_hits * 4 + econ_hits * 2 + (2 if numeric else 0) + (2 if movement else 0)
        if score:
            scored.append((score, -idx, sentence))
    scored.sort(reverse=True)
    return [s for _, _, s in scored[:8]]


class TableExtractor(HTMLParser):
    """Extract simple HTML tables while preserving row/column structure."""
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.in_table = False
        self.in_row = False
        self.in_cell = False
        self.rows = []
        self.current = []
        self.cell = []
    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        if tag == 'table': self.in_table = True
        elif self.in_table and tag == 'tr':
            self.in_row = True; self.current = []
        elif self.in_row and tag in ('td','th'):
            self.in_cell = True; self.cell = []
    def handle_endtag(self, tag):
        tag = tag.lower()
        if tag in ('td','th') and self.in_cell:
            self.current.append(re.sub(r'\s+', ' ', ' '.join(self.cell)).strip())
            self.in_cell = False
        elif tag == 'tr' and self.in_row:
            if self.current: self.rows.append(self.current)
            self.in_row = False
        elif tag == 'table':
            self.in_table = False
    def handle_data(self, data):
        if self.in_cell: self.cell.append(data.strip())

def extract_price_table_facts(body):
    """Extract economic price movements from tables with a rate/change column.

    Percentages inside product names/specifications are ignored. Only values
    belonging to a column whose header denotes an economic rate/change are
    treated as movements.
    """
    parser = TableExtractor(); parser.feed(body.decode('utf-8', errors='replace'))
    facts = []
    rate_re = re.compile(r'^[+-]?\d+(?:\.\d+)?$')
    for header_i, header in enumerate(parser.rows):
        headers = [c.lower() for c in header]
        rate_idx = next((i for i,c in enumerate(headers) if ('±rate' in c or 'rate (%)' in c or ('rate' in c and '%' in c) or 'change rate' in c)), None)
        if rate_idx is None: continue
        # Rows after this header are data until another header-like row.
        for row in parser.rows[header_i + 1:]:
            if len(row) <= rate_idx: continue
            if any(str(c).lower() == 'products' for c in row): break
            value = row[rate_idx].replace('%','').strip()
            if not rate_re.match(value): continue
            name = row[0].strip() if row else ''
            if not name or name.lower() in ('products','product','items'): continue
            unit = row[1].strip() if len(row) > 1 else ''
            current = row[2].strip() if len(row) > 2 else ''
            change = row[3].strip() if len(row) > 3 else ''
            facts.append({
                'value': value,
                'unit': '% economic price movement',
                'text': f'{name} {unit} current price {current}; price change over previous period {change}; rate {value}%.',
                'source_kind': 'structured_table',
                'product': name,
                'current_price': current,
                'price_change': change,
            })
        break
    out=[]; seen=set()
    for f in facts:
        key=(f['product'], f['value'])
        if key not in seen: seen.add(key); out.append(f)
    return out

def synthesize(item):
    result = dict(item)
    url = item.get('url','')
    try:
        body, ctype, status = fetch(url)
        text, page_title = clean_text(body)
        if len(text) < 300:
            raise ValueError('source page yielded insufficient text')
        facts = extract_facts(text)
        table_facts = extract_price_table_facts(body)
        # Structured table facts take precedence over free-text percentages.
        if table_facts:
            facts = table_facts + [f for f in facts if f.get('source_kind') != 'structured_table']
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
    structured=[f for f in facts if f.get('source_kind') == 'structured_table']
    if structured:
        # Rank table movements by absolute rate, not by incidental product-spec percentages.
        structured = sorted(structured, key=lambda f: abs(float(f['value'])), reverse=True)
        return structured[:8]
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
    elif any(f.get('source_kind') == 'structured_table' for f in facts):
        headline = 'China production-input prices show mixed movement'
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
    if any(f.get('source_kind') == 'structured_table' for f in facts):
        moves = [float(f['value']) for f in facts if f.get('source_kind') == 'structured_table']
        rising = sum(v > 0 for v in moves); falling = sum(v < 0 for v in moves)
        interpretation = (
            f'The table shows mixed price movement across production inputs, with {rising} tracked items rising and {falling} falling over the previous period. The largest movements in the extracted sample are concentrated in selected products rather than indicating a uniform price trend.'
        )
    elif pct_values and any(v < 1 for v in pct_values):
        interpretation='The latest data point indicates limited momentum in the measured activity, although individual subcategories may be performing differently.'
    elif any(v < 50 for v in pct_values):
        interpretation='The reported movement points to weaker conditions in the measured activity relative to a stronger growth environment.'
    else:
        interpretation='The latest release provides a current measure of economic activity and shows how performance is evolving across the reported period or categories.'

    sector=', '.join(item.get('sectors',['Other'])[:3]).lower()
    if any(f.get('source_kind') == 'structured_table' for f in facts):
        canadian='The release does not establish a direct Canada-specific effect. For Canadian businesses exposed to Chinese industrial inputs, commodities or supply chains, the data is a watchpoint for changes in input costs, supplier pricing and procurement conditions.'
    else:
        canadian=f'The source does not explicitly establish a Canada-specific effect. For Canadian businesses in {sector}, the data is a watchpoint because changes in Chinese demand, production, investment or pricing can affect market conditions, suppliers and competitive dynamics.'
    return headline, what, interpretation, data_points, canadian
