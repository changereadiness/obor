#!/usr/bin/env python3
"""Deterministic candidate filter, classifier, scorer and signal builder.
AI is intentionally optional: a future analyzer can replace/augment analyze_item().
"""
import json,re,hashlib
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; DATA=ROOT/'data'; RAW=DATA/'raw'

KEYWORDS={
'Trade':['tariff','trade','export','import','quota','market access','customs','duty','sanction'],
'Policy':['policy','stimulus','subsid','industrial policy','five-year','fiscal','economic plan'],
'Investment':['investment','foreign direct investment','fdi','merger','acquisition','capital'],
'Markets':['demand','consumption','sales','prices','production','manufacturing','retail','market'],
'Supply Chain':['supply chain','shipping','freight','port','logistics','factory','manufacturing','shortage','capacity'],
'Regulation':['regulation','licence','license','standard','compliance','restriction','approval','rule'],
'Industry':['steel','battery','solar','semiconductor','automotive','machinery','equipment','construction','aircraft'],
'Macroeconomics':['gdp','inflation','interest rate','employment','unemployment','industrial production','currency','yuan','renminbi']}
SECTORS={
'Agriculture & Food':['agriculture','food','grain','canola','wheat','pork','beef','dairy','seafood'],
'Energy':['oil','gas','lng','energy','electricity','power','coal'],
'Mining & Critical Minerals':['mining','lithium','nickel','cobalt','graphite','rare earth','critical mineral','copper'],
'Manufacturing':['manufacturing','factory','industrial production'],
'Machinery & Equipment':['machinery','equipment','excavator','loader','machine tools'],
'Technology':['semiconductor','chip','software','technology','ai','artificial intelligence','electronics'],
'Clean Technology':['solar','battery','ev','electric vehicle','wind','hydrogen','clean energy'],
'Automotive':['automotive','vehicle','car','ev','electric vehicle'],
'Logistics & Transportation':['shipping','freight','port','logistics','rail','aviation','transport'],
'Finance':['bank','financial','finance','credit','interest rate','bond'],
'Consumer Goods':['retail','consumer','e-commerce','household','apparel'],
'Healthcare':['healthcare','health','pharmaceutical','medical'],
'Professional Services':['services','consulting','legal','accounting'],
'Construction & Infrastructure':['construction','infrastructure','real estate','property']}
CHINA=['china','chinese','beijing','shanghai','shenzhen','guangzhou','prc']
CANADA=['canada','canadian','ottawa','toronto','vancouver','montreal','alberta','quebec','british columbia']
COMMERCIAL=['business','company','companies','export','import','investment','supplier','manufacturer','market','industry','trade','tariff','production','demand']

def norm(s): return re.sub(r'\\s+',' ',(s or '').lower())
def matches(text, terms): return sum(1 for t in terms if t in text)

def analyze(x):
    text=norm(x['title']+' '+x.get('description',''))
    china=matches(text,CHINA)
    canada=matches(text,CANADA)
    categories=sorted(KEYWORDS,key=lambda c:matches(text,KEYWORDS[c]),reverse=True)
    categories=[c for c in categories if matches(text,KEYWORDS[c])][:3]
    if not categories: categories=['Markets']
    sectors=[]
    for s,terms in SECTORS.items():
        if matches(text,terms): sectors.append(s)
    if not sectors: sectors=['Other']
    if canada and china: direction='Two-way'
    elif canada: direction='Canada → China'
    elif china: direction='China → Canada'
    else: direction='Global → Canada/China'
    trade=matches(text,KEYWORDS['Trade']); reg=matches(text,KEYWORDS['Regulation'])
    opp_terms=['access','open','growth','increase','support','reduce','agreement','demand','recovery','investment']
    risk_terms=['tariff','restriction','ban','sanction','decline','disruption','shortage','weakness','cut','uncertainty']
    opp=matches(text,opp_terms); risk=matches(text,risk_terms)
    if opp>=risk+2: classification='OPPORTUNITY'
    elif risk>=opp+2: classification='RISK'
    elif commercial:=matches(text,COMMERCIAL): classification='WATCH'
    else: classification='NEUTRAL'
    source_bonus=12 if x['source_type']=='Primary source' else 4
    score=min(100,30 + china*8 + canada*10 + min(20,trade*5) + min(12,len(sectors)*4) + source_bonus + min(10, matches(text,COMMERCIAL)*2))
    confidence=min(95,45+source_bonus+(15 if x.get('published_at') else 0)+(10 if china else 0)+(10 if title_has_fact(x['title']) else 0))
    return {**x,'categories':categories,'sectors':sectors,'direction':direction,'opportunity_or_risk':classification,'relevance_score':score,'confidence_score':confidence}

def title_has_fact(t): return bool(re.search(r'\\b(announces|announced|reports|reported|raises|cuts|falls|rises|approves|launches|changes|expands|restricts|opens|closes)\\b',t.lower()))

def candidate(x):
    t=norm(x['title']+' '+x.get('description',''))
    if not any(k in t for k in CHINA): return False
    if not any(k in t for k in COMMERCIAL+['economy','economic','policy','industry','manufacturing']): return False
    if len(x['title'])<18: return False
    return True

raw=json.loads((RAW/'items.json').read_text()) if (RAW/'items.json').exists() else []
items=[analyze(x) for x in raw if candidate(x)]
items.sort(key=lambda x:(x['relevance_score'],x.get('published_at') or ''),reverse=True)
# Keep enough candidates for optional AI analysis while avoiding API spend.
candidates=items[:50]
(RAW/'candidates.json').write_text(json.dumps(candidates,ensure_ascii=False,indent=2))

# Deterministic publication gate. AI can later enrich candidates before this gate.
existing=json.loads((DATA/'signals.json').read_text()) if (DATA/'signals.json').exists() else []
overrides=json.loads((DATA/'overrides.json').read_text())
supp=set(overrides.get('suppressed_sources',[]))
new=[]
for x in candidates:
    if x['source'] in supp or x['relevance_score']<55 or x['confidence_score']<50: continue
    if any(s.get('source_url')==x['url'] for s in existing): continue
    slug=re.sub(r'[^a-z0-9]+','-',x['title'].lower()).strip('-')[:80]
    sid='sig-'+hashlib.sha1(x['url'].encode()).hexdigest()[:12]
    summary=x.get('description') or x['title']
    summary=re.sub(r'\\s+',' ',summary).strip()[:420]
    canadian=("The development may be relevant to Canadian businesses through " + ', '.join(x['sectors'][:3]).lower() + ".")
    signal={'id':sid,'title':x['title'],'slug':slug,'published_at':(x.get('published_at') or datetime.now(timezone.utc).isoformat())[:10],
            'event_date':(x.get('published_at') or '')[:10] or None,'source':x['source'],'source_url':x['url'],'source_type':x['source_type'],
            'summary':summary,'what_happened':summary,'canadian_relevance':canadian,'opportunity_or_risk':x['opportunity_or_risk'],
            'relevance_score':x['relevance_score'],'confidence_score':x['confidence_score'],'sectors':x['sectors'],'categories':x['categories'],
            'direction':x['direction'],'entities':['China'],'related_signals':[],'status':'published'}
    ov=overrides.get('items',{}).get(sid,{})
    signal.update(ov); new.append(signal)
# Keep the demo records until the first real run, but never mix them into production after real signals exist.
real=[s for s in existing if s.get('status') not in ('demo','suppressed')]
all_signals=((real+new) if (real or new) else existing)[-200:]
(DATA/'signals.json').write_text(json.dumps(all_signals,ensure_ascii=False,indent=2))
print(f"raw={len(raw)} candidates={len(candidates)} published_new={len(new)} total={len(all_signals)}")
