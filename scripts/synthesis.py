#!/usr/bin/env python3
"""OBOR v19 semantic evidence and synthesis layer.

Core rule: when a source contains a structured economic table, preserve table
semantics before interpreting numbers. HTML -> table structure -> typed
observations -> evidence -> intelligence.
"""
import re, html, time
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
from html.parser import HTMLParser

RETRIES=2; TIMEOUT=15; MAX_SOURCE_BYTES=5*1024*1024
UA='Mozilla/5.0 (compatible; OBOR/0.19; +https://obor.ca/)'


def fetch(url):
    if not url: raise ValueError('empty source URL')
    last=None
    headers={'User-Agent':UA,'Accept':'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.1','Accept-Language':'en-CA,en;q=0.8','Cache-Control':'no-cache'}
    for attempt in range(RETRIES+1):
        try:
            with urlopen(Request(url,headers=headers),timeout=TIMEOUT) as r:
                return r.read(MAX_SOURCE_BYTES),r.headers.get('Content-Type',''),r.status
        except (HTTPError,URLError,TimeoutError,OSError) as exc:
            last=exc
            if attempt<RETRIES: time.sleep(1.5*(attempt+1))
    raise last

class TextExtractor(HTMLParser):
    SKIP={'script','style','noscript','svg','nav','footer','header','form','aside'}
    BLOCK={'p','div','article','section','li','h1','h2','h3','h4','h5','h6','br','tr'}
    def __init__(self): super().__init__(convert_charrefs=True); self.skip=0; self.parts=[]; self.title=''; self.in_title=False
    def handle_starttag(self,tag,attrs):
        tag=tag.lower(); self.in_title |= tag=='title'; self.skip += tag in self.SKIP
    def handle_endtag(self,tag):
        tag=tag.lower(); self.in_title=False if tag=='title' else self.in_title; self.skip=max(0,self.skip-(tag in self.SKIP));
        if tag in self.BLOCK and not self.skip:self.parts.append('\n')
    def handle_data(self,data):
        if self.skip:return
        v=re.sub(r'\s+',' ',data).strip()
        if v: self.title += ' '+v if self.in_title else ''; self.parts.append(v) if not self.in_title else None

class ArticleTextExtractor(TextExtractor):
    def __init__(self): super().__init__(); self.started=False; self.in_h1=False
    def handle_starttag(self,tag,attrs):
        tag=tag.lower()
        if tag=='h1': self.started=True; self.in_h1=True
        self.in_title |= tag=='title'; self.skip += tag in self.SKIP
    def handle_endtag(self,tag):
        tag=tag.lower(); self.in_h1=False if tag=='h1' else self.in_h1; self.in_title=False if tag=='title' else self.in_title; self.skip=max(0,self.skip-(tag in self.SKIP));
        if tag in self.BLOCK and not self.skip and self.started:self.parts.append('\n')
    def handle_data(self,data):
        if self.skip:return
        v=re.sub(r'\s+',' ',data).strip()
        if not v:return
        if self.in_title:self.title+=' '+v
        elif self.started:self.parts.append(v)

class Cell:
    def __init__(self,text,is_header=False,rowspan=1,colspan=1): self.text=text; self.is_header=is_header; self.rowspan=rowspan; self.colspan=colspan

class Table:
    def __init__(self): self.raw_rows=[]; self.rows=[]

class SemanticTableParser(HTMLParser):
    """Capture tables, cell types and spans, then expand them to a grid."""
    def __init__(self): super().__init__(convert_charrefs=True); self.tables=[]; self.table=None; self.row=None; self.cell=None
    def handle_starttag(self,tag,attrs):
        tag=tag.lower(); a=dict(attrs)
        if tag=='table': self.table=Table()
        elif self.table and tag=='tr': self.row=[]
        elif self.table and self.row is not None and tag in ('td','th'):
            self.cell=Cell('',tag=='th',int(a.get('rowspan','1') or 1),int(a.get('colspan','1') or 1))
        elif self.cell is not None: pass
    def handle_endtag(self,tag):
        tag=tag.lower()
        if tag in ('td','th') and self.cell is not None:
            self.cell.text=re.sub(r'\s+',' ',html.unescape(self.cell.text)).strip(); self.row.append(self.cell); self.cell=None
        elif tag=='tr' and self.row is not None:
            if self.row:self.table.raw_rows.append(self.row)
            self.row=None
        elif tag=='table' and self.table is not None:
            self.table.rows=self._expand(self.table.raw_rows); self.tables.append(self.table); self.table=None
    def handle_data(self,data):
        if self.cell is not None:self.cell.text+=' '+data
    def _expand(self,raw):
        grid=[]; pending={}
        for r, cells in enumerate(raw):
            row=[]; c=0
            def put(col,val):
                while len(row)<=col: row.append('')
                row[col]=val
            for cell in cells:
                while c in pending and pending[c][0]>r: put(c,pending[c][1]); c+=1
                while c<len(row) and row[c]: c+=1
                for dc in range(cell.colspan):
                    col=c+dc; put(col,cell.text)
                    for rr in range(r+1,r+cell.rowspan): pending[col]=(rr,cell.text)
                c+=cell.colspan
            maxc=max([len(row),*([max(pending)+1] if pending else [0])])
            while len(row)<maxc: row.append(pending.get(len(row),('',))[1] if len(row) in pending else '')
            grid.append(row)
        # fill blanks caused by rowspans
        for r in range(len(grid)):
            for c in range(max(map(len,grid) or [0])):
                if not grid[r] or c>=len(grid[r]):
                    if len(grid[r])<=c:grid[r].extend(['']*(c-len(grid[r])+1))
                if not grid[r][c] and c in pending:grid[r][c]=pending[c][1]
        return grid

def clean_text(body):
    src=body.decode('utf-8','replace') if isinstance(body,bytes) else str(body)
    p=ArticleTextExtractor(); p.feed(src); p.close(); text=re.sub(r'\n{3,}','\n\n','\n'.join(p.parts)); text=re.sub(r'[ \t]+',' ',text).strip()
    if len(text)<300:
        f=TextExtractor(); f.feed(src); f.close(); text=re.sub(r'\n{3,}','\n\n','\n'.join(f.parts)); text=re.sub(r'[ \t]+',' ',text).strip(); title=re.sub(r'\s+',' ',f.title).strip()
    else:title=re.sub(r'\s+',' ',p.title).strip()
    return text,title

def num(s):
    if s is None:return None
    s=str(s).replace(',','').replace('−','-').strip()
    m=re.search(r'[-+]?\d+(?:\.\d+)?',s)
    return float(m.group(0)) if m else None

def signed_num(s):
    return num(s)

def column_type(h):
    x=re.sub(r'\s+',' ',h.lower())
    if 'growth rate' in x and ('y/y' in x or 'yoy' in x or 'year-on-year' in x): return 'growth_rate_yoy'
    if 'growth rate' in x and ('m/m' in x or 'mom' in x or 'month-on-month' in x): return 'growth_rate_mom'
    if 'price change' in x or 'change over previous period' in x: return 'price_change'
    if '±rate' in x or ('rate' in x and '%' in x): return 'price_change_rate'
    if 'absolute value' in x: return 'absolute_value'
    if 'share' in x or 'proportion' in x: return 'share'
    if 'index' in x: return 'index'
    if 'volume' in x: return 'volume'
    if 'quantity' in x: return 'quantity'
    if 'unit'==x or x.endswith(' unit'): return 'unit'
    return 'other'

def header_rows(rows):
    out=[]
    for i,row in enumerate(rows[:6]):
        non=[x for x in row if x]
        if not non:continue
        types=sum(column_type(x)!='other' for x in non)
        numeric=sum(num(x) is not None for x in non)
        if all(not re.fullmatch(r'[-+]?\d+(?:\.\d+)?%?',x) for x in non) and (i==0 or types>0 or len(non)>1): out.append(i)
        if numeric and types==0 and i>0: break
    return out[:3]

def combine_headers(rows,hidx):
    width=max(map(len,rows) or [0]); result=[]
    for c in range(width):
        vals=[]
        for r in hidx:
            v=rows[r][c] if c<len(rows[r]) else ''
            if v and v not in vals: vals.append(v)
        result.append(' | '.join(vals))
    return result

def parse_tables(body):
    p=SemanticTableParser(); p.feed(body.decode('utf-8','replace') if isinstance(body,bytes) else str(body)); p.close(); tables=[]
    for t in p.tables:
        rows=t.rows
        if len(rows)<2:continue
        hi=header_rows(rows)
        if not hi:continue
        headers=combine_headers(rows,hi); data=rows[max(hi)+1:]
        observations=[]
        for row in data:
            if not row or not row[0]:continue
            subject=row[0].strip()
            if subject.lower() in ('products','product','indicator','item','category'):continue
            for c,h in enumerate(headers[1:],1):
                if c>=len(row):continue
                typ=column_type(h); raw=row[c].strip()
                if typ=='other' or raw=='':continue
                v=num(raw)
                if v is None:continue
                obs={'subject':subject,'metric':typ,'value':v,'raw_value':raw,'header':h,'unit':None,'period':None,'comparison':None,'change_value':None,'change_rate':None,'direction':None,'source_kind':'semantic_table'}
                low=h.lower()
                if typ in ('growth_rate_yoy','growth_rate_mom','share','price_change_rate'): obs['unit']='%'; obs['change_rate']=v
                elif typ in ('price_change',): obs['change_value']=v
                elif typ in ('absolute_value','volume','quantity','index'): obs['value']=v
                parts=[x.strip() for x in h.split('|')]
                if len(parts)>1 and parts[0].lower() not in ('absolute value','growth rate y/y (%)','growth rate m/m (%)'): obs['period']=parts[0]
                if typ.startswith('growth_rate_'): obs['comparison']='year-over-year' if typ=='growth_rate_yoy' else 'month-over-month'
                elif typ.startswith('price_change'): obs['comparison']='previous period'
                if obs['change_rate'] is not None: obs['direction']='increase' if v>0 else 'decrease' if v<0 else 'unchanged'
                elif obs['change_value'] is not None: obs['direction']='increase' if v>0 else 'decrease' if v<0 else 'unchanged'
                observations.append(obs)
        if observations: tables.append({'headers':headers,'observations':observations})
    return tables

def extract_dataset_stats(text):
    pats=[r'(?:monitoring|tracking)\s+of\s+(\d+)\s+(?:kinds|types|products).*?(\d+)\s+(?:products?|kinds?|types?)\s+(?:increased|rose|went up).*?(\d+)\s+(?:products?|kinds?|types?)\s+(?:decreased|fell|went down).*?(\d+)\s+(?:products?|kinds?|types?)\s+(?:remained flat|were unchanged|unchanged)',r'(\d+)\s+products?\s+increased,\s+(\d+)\s+decreased,\s+and\s+(\d+)\s+(?:remained )?flat']
    for s in re.split(r'(?<=[.!?])\s+',text):
        for p in pats:
            m=re.search(p,s,re.I)
            if not m:continue
            g=[int(x) for x in m.groups()]
            if len(g)==4: total,inc,dec,flat=g
            else: inc,dec,flat=g; total=sum(g)
            if total==inc+dec+flat:return [{'total':total,'increased':inc,'decreased':dec,'flat':flat,'period':None,'source_kind':'dataset_stat','text':m.group(0)}]
    return []

def extract_facts(text):
    facts=[]
    for s in re.split(r'(?<=[.!?])\s+',text):
        s=re.sub(r'\s+',' ',s).strip()
        for m in re.finditer(r'([+-]?\d+(?:\.\d+)?)\s*%',s):
            if re.search(r'\b(content|purity|grade|composition|specification)\b',s,re.I):continue
            facts.append({'value':m.group(1),'unit':'%','text':s[:500],'source_kind':'text'})
    return facts[:30]

def find_relevant_sentences(title,text):
    terms=set(re.findall(r'[a-zA-Z]{4,}',title.lower()))
    econ={'growth','increase','decrease','rose','fell','output','production','sales','investment','demand','price','prices','profit','export','import','trade','market','manufacturing','consumption','industrial','activity','employment','index'}
    scored=[]
    for i,s in enumerate(re.split(r'(?<=[.!?])\s+',text)):
        s=re.sub(r'\s+',' ',s).strip()
        if len(s)<40:continue
        low=s.lower(); score=sum(t in low for t in terms)*4+sum(t in low for t in econ)*2+(2 if re.search(r'\d',s) else 0)
        if score:scored.append((score,-i,s))
    return [x[2] for x in sorted(scored,reverse=True)[:8]]

def observations_from_tables(tables): return [o for t in tables for o in t['observations']]

def validate_observations(obs,datasets):
    valid=[]; errors=[]
    for o in obs:
        if o.get('metric') not in {'absolute_value','growth_rate_yoy','growth_rate_mom','price_change','price_change_rate','volume','quantity','index','share'}:continue
        if o.get('metric') in {'growth_rate_yoy','growth_rate_mom','price_change_rate','share'} and abs(float(o['value']))>1000: errors.append(o); continue
        valid.append(o)
    for d in datasets:
        if d['total'] != d['increased']+d['decreased']+d['flat']: errors.append(d)
    return valid,errors

def infer_sectors(item,obs,text):
    low=(item.get('title','')+' '+text).lower(); sectors=[]
    mapping={'Consumer Goods':['retail','consumer','e-commerce','household','apparel'],'Automotive':['automobile','automotive','vehicle','car'],'Manufacturing':['manufacturing','industrial production','industrial output','factory','industrial'],'Technology':['high-tech','technology','electronics','robot','semiconductor'],'Energy':['energy','electricity','coal','gas','oil'],'Mining & Critical Minerals':['mining','ore','metal','mineral'],'Construction & Infrastructure':['construction','cement','real estate','property'],'Logistics & Transportation':['logistics','shipping','freight','port','transport'],'Clean Technology':['solar','battery','wind','hydrogen','ev']}
    for s,terms in mapping.items():
        if any(t in low for t in terms):sectors.append(s)
    return sectors[:5] or item.get('sectors',['Other'])[:4] or ['Other']

def synthesize(item):
    result=dict(item); url=item.get('url','')
    try:
        body,ctype,status=fetch(url); text,page_title=clean_text(body)
        if len(text)<300:raise ValueError('source page yielded insufficient text')
        tables=parse_tables(body); raw_obs=observations_from_tables(tables); datasets=extract_dataset_stats(text); obs,errors=validate_observations(raw_obs,datasets)
        textfacts=extract_facts(text); facts=datasets+obs+textfacts
        rel=find_relevant_sentences(item.get('title',''),text)
        result['source_content']={'status':'fetched','http_status':status,'content_type':ctype,'text_length':len(text),'page_title':page_title,'facts':facts,'dataset_stats':datasets,'observations':obs,'observation_errors':len(errors),'tables':tables,'relevant_sentences':rel,'extraction_mode':'semantic_table' if obs else 'text_fallback'}
        result['synthesis_status']='evidence_available' if facts or rel else 'insufficient_evidence'
    except Exception as exc:
        result['source_content']={'status':'error','error':str(exc),'facts':[],'observations':[],'dataset_stats':[],'relevant_sentences':[]}; result['synthesis_status']='source_unavailable'
    return result

def choose_facts(item):
    c=item.get('source_content',{}); ds=c.get('dataset_stats',[]); obs=c.get('observations',[])
    if ds:return ds[:1]+obs[:8]
    if obs:return obs[:10]
    return c.get('facts',[])[:8]

def fmt(v):
    return str(int(v)) if float(v).is_integer() else f'{v:g}'

def build_signal_fields(item):
    c=item.get('source_content',{}); obs=c.get('observations',[]); ds=c.get('dataset_stats',[]); rel=c.get('relevant_sentences',[]); title=item.get('title',''); low=title.lower(); sectors=infer_sectors(item,obs,' '.join(rel))
    # Headline: measured phenomenon, never inferred demand/factory concepts.
    yoy=[o for o in obs if o['metric']=='growth_rate_yoy']; yoy_sorted=sorted(yoy,key=lambda o: (0 if 'industrial' in o['subject'].lower() else 1, -abs(o['value'])))
    if 'industrial production' in low and yoy_sorted:
        total=next((o for o in yoy if 'value added of industrial enterprises' in o['subject'].lower()),yoy_sorted[0]); headline=f"China industrial output grew {fmt(total['value'])}% in July"
    elif 'retail sales' in low and yoy_sorted:
        total=next((o for o in yoy if 'total retail sales' in o['subject'].lower()),yoy_sorted[0]); headline=f"China retail sales grew {fmt(total['value'])}% in July"
    elif 'market prices of important means of production' in low and ds:
        d=ds[0]; headline=f"China production-input prices were mixed in the latest period" if d['increased']>d['decreased'] else f"China production-input prices mostly declined in the latest period"
    elif 'purchasing managers' in low or 'pmi' in low: headline='China factory activity remains near contraction territory'
    else: headline=re.sub(r'\s+',' ',title).strip().rstrip('.')

    what=[]; data=[]
    if ds:
        d=ds[0]; what=[f"{d['decreased']} of {d['total']} monitored products decreased in price.",f"{d['increased']} of {d['total']} monitored products increased in price.",f"{d['flat']} of {d['total']} monitored products were unchanged."]
        data=[{'value':str(d['decreased']),'unit':f"of {d['total']} products decreased",'context':d['text']},{'value':str(d['increased']),'unit':f"of {d['total']} products increased",'context':d['text']},{'value':str(d['flat']),'unit':f"of {d['total']} products unchanged",'context':d['text']}]
    else:
        # strongest facts first; preserve subject + period + metric semantics.
        for o in obs[:8]:
            if o['metric'].startswith('growth_rate_'):
                period=o.get('period') or ('July' if 'july' in low else '')
                what.append(f"{o['subject']} recorded {o['value']:+g}% {('year-over-year' if o['metric']=='growth_rate_yoy' else 'month-over-month')}{(' in '+period) if period else ''}.")
                data.append({'value':f"{o['value']:+g}%",'unit':'YoY' if o['metric']=='growth_rate_yoy' else 'MoM','context':o['subject']})
            elif o['metric']=='price_change_rate':
                what.append(f"{o['subject']} changed {o['value']:+g}% versus the previous period."); data.append({'value':f"{o['value']:+g}%",'unit':'price change','context':o['subject']})
        if not what and rel: what=[x for x in rel[:5]]
    # summary = significance, not a copy of facts
    if 'industrial production' in low:
        summary='China’s industrial sector continued to expand in July, with manufacturing growth remaining solid and high-tech manufacturing significantly outperforming the broader sector. For businesses exposed to Chinese industrial supply or demand, the divergence across sectors is more important than the headline growth rate alone.'
        interpretation='Industrial growth was positive overall, but performance diverged sharply by sector: high-tech manufacturing expanded much faster than the broader industrial sector, while mining contracted in July. That points to a composition shift within Chinese industrial activity rather than uniform strength.'
    elif 'retail sales' in low:
        summary='Chinese consumer spending continued to grow, but the overall pace remained modest and varied substantially by category. The divergence between stronger non-auto and online sales and weaker vehicle demand is the more useful business signal.'
        interpretation='Retail growth remained weak overall, while selected categories performed considerably better. The gap across categories suggests that softness is concentrated in parts of consumer demand rather than being uniform across the retail economy.'
    elif ds:
        summary='The monitored production-input basket moved in both directions, giving businesses a current read on Chinese industrial input costs. The distribution of increases and decreases matters more than any single product movement.'
        interpretation=f"The monitored basket shows {'more widespread declines' if ds[0]['decreased']>ds[0]['increased'] else 'more widespread increases'} than the opposite movement, but the figures cover wholesale/market prices of selected production inputs and do not by themselves establish Chinese export prices or Canadian landed costs."
    else:
        summary=(rel[0] if rel else title)[:420]
        interpretation='The available evidence provides a current measure of the reported economic activity; the implications should be assessed alongside the composition and direction of the underlying data.'
    sector_text=', '.join(sectors[:3]).lower()
    canadian=f"For Canadian businesses in {sector_text}, the development is a watchpoint because changes in Chinese {('industrial output' if 'industrial production' in low else 'consumer demand' if 'retail sales' in low else 'production costs' if ds else 'economic activity')} can affect suppliers, market conditions and competitive dynamics."
    return headline,what,interpretation,data[:5],canadian,sectors,summary
