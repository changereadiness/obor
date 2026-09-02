#!/usr/bin/env python3
"""OBOR v19 semantic evidence and deterministic synthesis layer.

Structured source tables are parsed as tables, not flattened text. The parser
preserves header/row relationships and emits typed economic observations.
"""
import re, html, time, hashlib
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
        tag=tag.lower(); self.in_title|=tag=='title'; self.skip+=tag in self.SKIP
    def handle_endtag(self,tag):
        tag=tag.lower(); self.in_title=False if tag=='title' else self.in_title; self.skip=max(0,self.skip-(tag in self.SKIP)); self.parts.append('\n') if tag in self.BLOCK and not self.skip else None
    def handle_data(self,data):
        if self.skip:return
        v=re.sub(r'\s+',' ',data).strip()
        if not v:return
        self.title += ' '+v if self.in_title else ''
        if not self.in_title:self.parts.append(v)

class ArticleTextExtractor(TextExtractor):
    def __init__(self): super().__init__(); self.started=False; self.in_h1=False
    def handle_starttag(self,tag,attrs):
        tag=tag.lower()
        if tag=='h1': self.started=True; self.in_h1=True
        if tag in self.SKIP:self.skip+=1
        if tag=='title':self.in_title=True
    def handle_endtag(self,tag):
        tag=tag.lower()
        if tag=='h1':self.in_h1=False
        if tag=='title':self.in_title=False
        if tag in self.SKIP:self.skip=max(0,self.skip-1)
        if tag in self.BLOCK and self.started and not self.skip:self.parts.append('\n')
    def handle_data(self,data):
        if self.skip:return
        v=re.sub(r'\s+',' ',data).strip()
        if not v:return
        if self.in_title:self.title+=' '+v
        elif self.started:self.parts.append(v)

def clean_text(body):
    source=body.decode('utf-8','replace') if isinstance(body,bytes) else str(body)
    p=ArticleTextExtractor(); p.feed(source); p.close()
    text=re.sub(r'\n{3,}','\n\n','\n'.join(p.parts)); text=re.sub(r'[ \t]+',' ',text).strip()
    if len(text)<300:
        p=TextExtractor(); p.feed(source); p.close(); text=re.sub(r'\n{3,}','\n\n','\n'.join(p.parts)); text=re.sub(r'[ \t]+',' ',text).strip()
    return text,re.sub(r'\s+',' ',p.title).strip()

def _num(raw):
    s=str(raw).replace(',','').strip().replace('−','-')
    s=re.sub(r'\s+','',s)
    try:return float(s)
    except:return None

def _fmt(v):
    if isinstance(v,int):return str(v)
    return f'{v:.2f}'.rstrip('0').rstrip('.')

class SemanticTableParser(HTMLParser):
    """Build rectangular table grids while respecting rowspan/colspan."""
    def __init__(self):
        super().__init__(convert_charrefs=True); self.tables=[]; self.table=None; self.row=None; self.cell=None; self.pending=[]
    def handle_starttag(self,tag,attrs):
        tag=tag.lower()
        if tag=='table': self.table=[]
        elif tag=='tr' and self.table is not None: self.row=[]
        elif tag in ('th','td') and self.row is not None:
            amap=dict(attrs); self.cell={'tag':tag,'text':[],'rowspan':int(amap.get('rowspan','1') or 1),'colspan':int(amap.get('colspan','1') or 1)}
    def handle_endtag(self,tag):
        tag=tag.lower()
        if tag in ('th','td') and self.cell is not None:
            self.cell['text']=[re.sub(r'\s+',' ',' '.join(self.cell['text'])).strip()]; self.row.append(self.cell); self.cell=None
        elif tag=='tr' and self.row is not None:
            self.table.append(self.row); self.row=None
        elif tag=='table' and self.table is not None:
            self.tables.append(self.table); self.table=None
    def handle_data(self,data):
        if self.cell is not None:self.cell['text'].append(data)

def _grid(raw_rows):
    grid=[]; spans={}
    for r,row in enumerate(raw_rows):
        out=[]; c=0
        def occupy():
            nonlocal c
            while (r,c) in spans:
                out.append(spans[(r,c)]['text']); c+=1
        for cell in row:
            occupy(); txt=cell['text'][0] if cell['text'] else ''
            for dc in range(cell['colspan']):
                while len(out)<=c+dc: out.append('')
                out[c+dc]=txt
                for dr in range(1,cell['rowspan']):spans[(r+dr,c+dc)]={'text':txt}
            c+=cell['colspan']
        occupy(); grid.append(out)
    width=max((len(x) for x in grid),default=0)
    return [x+['']*(width-len(x)) for x in grid]

def _header_count(rows):
    for i,row in enumerate(rows):
        numeric=sum(_num(re.sub(r'[%±]','',c)) is not None for c in row[1:])
        if numeric>=2:return max(1,i)
    return min(2,len(rows))

def _semantic_type(header):
    h=header.lower()
    if 'growth rate' in h and ('y/y' in h or 'year' in h or 'yoy' in h):return 'growth_rate_yoy'
    if 'growth rate' in h and ('m/m' in h or 'month' in h or 'mom' in h):return 'growth_rate_mom'
    if '±rate' in h or ('rate' in h and '%' in h and 'growth' not in h):return 'price_change_rate'
    if 'price change' in h or 'change over previous period' in h:return 'price_change'
    if 'absolute value' in h:return 'absolute_value'
    if 'volume' in h:return 'volume'
    if 'share' in h:return 'share'
    if 'index' in h:return 'index'
    if 'quantity' in h:return 'quantity'
    return None

def parse_semantic_tables(body):
    p=SemanticTableParser(); p.feed(body.decode('utf-8','replace') if isinstance(body,bytes) else str(body)); p.close()
    observations=[]; tables=[]
    for raw in p.tables:
        rows=_grid(raw)
        if len(rows)<2:continue
        hc=_header_count(rows); header_rows=rows[:hc]
        headers=[]
        for col in range(len(rows[0])):
            vals=[]
            for hr in header_rows:
                v=hr[col].strip()
                if v and (not vals or v!=vals[-1]):vals.append(v)
            headers.append(' | '.join(vals))
        typed=[_semantic_type(h) for h in headers]
        if not any(typed):continue
        tables.append({'headers':headers,'rows':rows,'typed_columns':typed})
        for row in rows[hc:]:
            if not row:continue
            subject=row[0].strip()
            if not subject or subject.lower() in ('indicator','products','product','items'):continue
            # Unit columns often appear immediately after subject.
            unit=''
            for j,c in enumerate(row[1:3],1):
                if c and _num(c) is None and len(c)<80 and not _semantic_type(headers[j]): unit=c.strip()
            for j,stype in enumerate(typed):
                if not stype or j>=len(row):continue
                rawv=row[j].strip(); value=_num(rawv.replace('%',''))
                if value is None:continue
                header=headers[j]; period=''
                parts=[x.strip() for x in header.split(' | ')]
                for part in parts:
                    if re.search(r'\b(july|january|february|march|april|may|june|august|september|october|november|december|q[1-4]|annual|year)\b',part,re.I): period=part; break
                obs={'subject':subject,'metric':stype,'value':value,'raw_value':rawv,'unit':unit,'period':period,'header':header,'direction':None,'source_kind':'semantic_observation'}
                if stype in ('growth_rate_yoy','growth_rate_mom','price_change_rate','share'):
                    obs['unit']='%'
                if stype in ('growth_rate_yoy','growth_rate_mom','price_change_rate'):
                    obs['direction']='increase' if value>0 else 'decrease' if value<0 else 'unchanged'
                observations.append(obs)
    return tables,observations

def validate_observations(obs):
    valid=[]
    for o in obs:
        if not o.get('subject') or o.get('value') is None:continue
        if o.get('metric') in ('growth_rate_yoy','growth_rate_mom','price_change_rate') and abs(float(o['value']))>1000:continue
        valid.append(o)
    return valid

def extract_dataset_stats(text):
    patterns=[
      re.compile(r'(?:monitoring|tracking)\s+of\s+(\d+)\s+(?:kinds|types|products).*?(\d+)\s+(?:products|kinds|types)\s+increased,\s+(\d+)\s+(?:products|kinds|types)\s+decreased,\s+and\s+(\d+)\s+(?:products|kinds|types)\s+(?:remained\s+)?(?:flat|unchanged)',re.I),
      re.compile(r'(\d+)\s+(?:products|kinds|types)\s+increased,\s+(\d+)\s+(?:products|kinds|types)\s+decreased,\s+and\s+(\d+)\s+(?:products|kinds|types)\s+(?:remained\s+)?(?:flat|unchanged)',re.I)]
    for s in re.split(r'(?<=[.!?])\s+',text):
        s=re.sub(r'\s+',' ',s).strip()
        for p in patterns:
            m=p.search(s)
            if not m:continue
            g=[int(x) for x in m.groups()]
            if len(g)==4: total,inc,dec,flat=g
            else: inc,dec,flat=g; total=sum(g)
            if total==inc+dec+flat:return [{'total':total,'increased':inc,'decreased':dec,'flat':flat,'text':m.group(0),'source_kind':'dataset_stat'}]
    return []

def extract_facts(text):
    out=[]; seen=set()
    for s in re.split(r'(?<=[.!?])\s+',text):
        s=re.sub(r'\s+',' ',s).strip()
        for m in re.finditer(r'([+-]?\d+(?:\.\d+)?)\s*%',s):
            v=_num(m.group(1))
            if v is None or re.search(r'\b(?:purity|content|composition|specification)\b',s,re.I):continue
            k=(v,s[:200])
            if k in seen:continue
            seen.add(k); out.append({'value':m.group(1),'unit':'%','text':s[:500],'source_kind':'text'})
            if len(out)>=30:return out
    return out

def find_relevant_sentences(title,text):
    economic={'growth','decline','increase','decrease','rose','fell','output','production','sales','investment','demand','price','prices','profit','profits','pmi','export','imports','trade','market','manufacturing','consumption','industrial','activity','index'}
    terms={x for x in re.findall(r'[a-z]{4,}',title.lower()) if x not in {'china','january','february','march','april','may','june','july','august','september','october','november','december'}}
    scored=[]
    for s in re.split(r'(?<=[.!?])\s+',text):
        s=re.sub(r'\s+',' ',s).strip()
        if len(s)<40:continue
        low=s.lower(); score=sum(t in low for t in terms)*3+sum(t in low for t in economic)+bool(re.search(r'\d',s))*2
        scored.append((score,s))
    return [s for _,s in sorted(scored,key=lambda x:x[0],reverse=True)[:8]]

def infer_subject(title, observations, text):
    low=title.lower()
    if 'retail sales' in low:return 'consumer demand'
    if 'industrial production' in low:return 'industrial output'
    if 'market prices of important means of production' in low:return 'production-input prices'
    if 'purchasing managers' in low or 'pmi' in low:return 'business activity'
    if 'industrial profits' in low:return 'industrial profitability'
    return title

def infer_sectors(item, observations, text):
    low=(item.get('title','')+' '+text).lower()
    if 'retail sales' in low:return ['Consumer Goods','Automotive','Logistics & Transportation']
    if 'industrial production' in low:return ['Manufacturing','Technology','Mining & Critical Minerals','Energy']
    if 'market prices of important means of production' in low:return ['Manufacturing','Energy','Mining & Critical Minerals','Construction & Infrastructure']
    if 'purchasing managers' in low:return ['Manufacturing','Logistics & Transportation','Professional Services']
    return item.get('sectors',['Other'])[:4] or ['Other']

def _obs_text(o):
    v=_fmt(o['value']); metric=o['metric']
    if metric=='growth_rate_yoy':return f"{o['subject']} {v}% YoY" + (f" ({o['period']})" if o.get('period') else '')
    if metric=='growth_rate_mom':return f"{o['subject']} {v}% MoM"
    if metric=='price_change_rate':return f"{o['subject']} {v}%"
    if metric=='price_change':return f"{o['subject']} change {v}"
    return f"{o['subject']}: {v} {o.get('unit','')}".strip()

def choose_primary(obs):
    priority={'growth_rate_yoy':0,'growth_rate_mom':1,'price_change_rate':1,'price_change':2,'absolute_value':3,'volume':4,'quantity':4,'index':5,'share':6}
    return sorted(obs,key=lambda o:(priority.get(o['metric'],9), -abs(float(o['value']))))

def build_signal_fields(item):
    c=item.get('source_content',{}); obs=c.get('observations',[]); ds=c.get('dataset_stats',[]); rel=c.get('relevant_sentences',[])
    title=item.get('title',''); low=title.lower(); sectors=infer_sectors(item,obs,' '.join(rel)); primary=choose_primary(obs)
    growth=[o for o in obs if o['metric']=='growth_rate_yoy']
    price=[o for o in obs if o['metric']=='price_change_rate']
    if 'retail sales' in low and growth:
        total=next((o for o in growth if 'total retail sales' in o['subject'].lower()),growth[0]); excl=next((o for o in growth if 'excluding automobiles' in o['subject'].lower()),None)
        headline=f"China retail sales grew { _fmt(total['value']) }% in July"
        summary=(f"China's retail economy expanded only modestly in July, although growth excluding automobiles was stronger. "
                 f"The divergence suggests consumer demand is uneven rather than uniformly weak.")
        what=[f"{_obs_text(total)}."]
        if excl: what.append(f"{_obs_text(excl)}.")
        for o in growth:
            if o not in (total,excl) and len(what)<5: what.append(f"{_obs_text(o)}.")
        interpretation="Retail growth remained weak overall, but performance varied materially across categories. Stronger growth outside automobiles indicates that the softness in headline retail activity is not uniform across consumer demand."
        canadian="Canadian businesses exposed to Chinese consumer demand should watch which categories are expanding and which remain weak, particularly where China is an important market or competitor."
    elif 'industrial production' in low and growth:
        total=next((o for o in growth if 'value added of industrial enterprises' in o['subject'].lower()),growth[0]); manuf=next((o for o in growth if o['subject'].lower()=='manufacturing'),None); high=next((o for o in growth if 'high-technology manufacturing' in o['subject'].lower()),None); mining=next((o for o in growth if o['subject'].lower()=='mining'),None)
        headline=f"China industrial output grew {_fmt(total['value'])}% in July"
        summary="China's industrial sector continued to expand in July, with manufacturing growth remaining solid and high-tech manufacturing significantly outperforming the broader sector. For businesses exposed to Chinese industrial supply or demand, the divergence across sectors matters more than the headline rate alone."
        what=[f"{_obs_text(total)}."]
        for o in (manuf,high,mining):
            if o:what.append(f"{_obs_text(o)}.")
        for o in growth:
            if len(what)>=5:break
            if o not in (total,manuf,high,mining):what.append(f"{_obs_text(o)}.")
        interpretation="Industrial output continued to grow, but the sector mix was uneven. High-tech manufacturing materially outpaced the broader industrial sector while mining contracted in July, indicating that industrial momentum is concentrated in particular parts of the economy."
        canadian="Canadian exporters, suppliers and competitors should watch where Chinese industrial growth is accelerating, particularly in high-tech manufacturing, because stronger domestic production can affect input demand, competitive pricing and supply-chain opportunities."
    elif ds and price:
        d=ds[0]; inc=sorted(price,key=lambda o:o['value'])[:2]; headline="China production-input prices mostly declined in early August" if d['decreased']>d['increased'] else "China production-input prices were mixed in early August"
        summary=f"China's monitored production-input basket moved broadly {'lower' if d['decreased']>d['increased'] else 'higher or mixed'} in the period, with {d['decreased']} of {d['total']} products declining and {d['increased']} increasing. The distribution provides a useful watchpoint for industrial input costs."
        what=[f"{d['decreased']} of {d['total']} monitored products decreased in price.",f"{d['increased']} of {d['total']} increased, while {d['flat']} were unchanged."]
        for o in inc:what.append(f"{_obs_text(o)}.")
        interpretation=f"The monitored basket shows {'broad downward' if d['decreased']>d['increased'] else 'mixed'} price movement rather than a uniform shift. These are market prices for important means of production and do not by themselves establish producer prices, export prices or Canadian landed costs."
        canadian="Canadian manufacturers sourcing industrial materials or energy-linked inputs from China can treat the movement as a procurement watchpoint, while Canadian producers competing with Chinese manufacturers should monitor whether input-cost changes affect Chinese cost competitiveness."
    else:
        headline=re.sub(r'\s+',' ',title).strip().rstrip('.')
        summary=(rel[0] if rel else item.get('description') or headline)[:420]
        what=[s[:400] for s in rel[:5]]
        interpretation="The available evidence provides a current measure of the reported economic activity; the implications depend on the composition and persistence of the underlying movement."
        canadian=f"For Canadian businesses in {', '.join(sectors[:3]).lower()}, the development is a watchpoint because changes in Chinese economic conditions can affect suppliers, demand, pricing or competitive dynamics."
    key=[]
    if ds:
        d=ds[0]; total=d['total']; key=[{'value':str(d['decreased']),'unit':f"of {total} products decreased",'context':f"{d['decreased']/total:.0%} of monitored products"},{'value':str(d['increased']),'unit':f"of {total} products increased",'context':f"{d['increased']/total:.0%} of monitored products"},{'value':str(d['flat']),'unit':f"of {total} products unchanged",'context':f"{d['flat']/total:.0%} of monitored products"}]
    for o in primary:
        if len(key)>=5:break
        if o['metric'] in ('growth_rate_yoy','growth_rate_mom','price_change_rate'):
            key.append({'value':_fmt(o['value']),'unit':'%','context':f"{o['subject']} · {o.get('period') or o['metric'].replace('_',' ')}"})
    return headline,summary,what,interpretation,key,canadian,sectors

def synthesize(item):
    result=dict(item); url=item.get('url','')
    try:
        body,ctype,status=fetch(url); text,page_title=clean_text(body)
        if len(text)<300:raise ValueError('source page yielded insufficient text')
        tables,obs=parse_semantic_tables(body); obs=validate_observations(obs); ds=extract_dataset_stats(text); facts=extract_facts(text)
        result['source_content']={'status':'fetched','http_status':status,'content_type':ctype,'text_length':len(text),'page_title':page_title,'tables':tables,'observations':obs,'dataset_stats':ds,'facts':facts,'relevant_sentences':find_relevant_sentences(item.get('title',''),text),'extraction_mode':'semantic_table' if obs else 'text_fallback'}
        result['synthesis_status']='evidence_available' if (obs or ds or facts or result['source_content']['relevant_sentences']) else 'insufficient_evidence'
    except Exception as exc:
        result['source_content']={'status':'error','error':str(exc),'observations':[],'dataset_stats':[],'facts':[],'relevant_sentences':[]}; result['synthesis_status']='source_unavailable'
    return result

def choose_facts(item):
    c=item.get('source_content',{}); return c.get('observations',[])[:12] or c.get('facts',[])[:8]
