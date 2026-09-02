#!/usr/bin/env python3
"""OBOR deterministic intelligence engine.

Stages: candidate screening -> evidence extraction -> classification -> scoring ->
conservative publication gate -> structured signal creation.
No AI or paid service is required.
"""
import hashlib, json, re, html
from synthesis import synthesize, build_signal_fields
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'data'
RAW = DATA / 'raw'

CATEGORIES = {
    'Trade': ['tariff','trade','export','exports','import','imports','quota','market access','customs','duty','duties','sanction','countermeasure'],
    'Policy': ['policy','stimulus','subsid','industrial policy','five-year','fiscal','economic plan','government work report','opening up'],
    'Investment': ['investment','foreign direct investment','fdi','merger','acquisition','capital','joint venture'],
    'Markets': ['demand','consumption','sales','prices','production','manufacturing','retail','market','pmi'],
    'Supply Chain': ['supply chain','shipping','freight','port','logistics','factory','manufacturing','shortage','capacity','inventory'],
    'Regulation': ['regulation','licence','license','standard','compliance','restriction','approval','rule','investigation','requirement'],
    'Industry': ['steel','battery','solar','semiconductor','automotive','machinery','equipment','construction','aircraft','shipbuilding','robotics'],
    'Macroeconomics': ['gdp','inflation','interest rate','employment','unemployment','industrial production','currency','yuan','renminbi','cpi','ppi'],
}

SECTORS = {
    'Agriculture & Food':['agriculture','food','grain','canola','wheat','pork','beef','dairy','seafood','soybean'],
    'Energy':['oil','gas','lng','energy','electricity','power','coal'],
    'Mining & Critical Minerals':['mining','lithium','nickel','cobalt','graphite','rare earth','critical mineral','copper'],
    'Manufacturing':['manufacturing','factory','industrial production','industrial output'],
    'Machinery & Equipment':['machinery','equipment','excavator','loader','machine tools','industrial equipment'],
    'Technology':['semiconductor','chip','software','technology','ai','artificial intelligence','electronics','robotics'],
    'Clean Technology':['solar','battery','ev','electric vehicle','wind','hydrogen','clean energy'],
    'Automotive':['automotive','vehicle','car','ev','electric vehicle'],
    'Logistics & Transportation':['shipping','freight','port','logistics','rail','aviation','transport','container'],
    'Finance':['bank','financial','finance','credit','interest rate','bond','lending'],
    'Consumer Goods':['retail','consumer','e-commerce','household','apparel'],
    'Healthcare':['healthcare','health','pharmaceutical','medical'],
    'Professional Services':['services','consulting','legal','accounting'],
    'Construction & Infrastructure':['construction','infrastructure','real estate','property','housing'],
}

CHINA = ['china','chinese','beijing','shanghai','shenzhen','guangzhou','prc','mainland china']
CANADA = ['canada','canadian','ottawa','toronto','vancouver','montreal','alberta','quebec','british columbia','ontario','canadian exporter','canadian importer']
COMMERCIAL = ['business','company','companies','export','exports','import','imports','investment','supplier','manufacturer','market','industry','trade','tariff','production','demand','sales','cost','price','sourcing','procurement']
ECONOMIC_SIGNALS = ['pmi','purchasing managers','industrial production','industrial output','retail sales','fixed asset investment','fixed investment','property investment','real estate investment','consumer prices','producer prices','cpi','ppi','employment','unemployment','gdp','gross domestic product','industrial profits','foreign trade','trade surplus','trade deficit','services production','manufacturing activity','economic activity','business activity','new orders','factory activity','capacity utilization','investment growth','sales growth','output growth']

OPPORTUNITY = ['access','open','opens','growth','increase','support','reduce','agreement','demand','recovery','investment','approve','approval','ease','easing','expand','expands','export growth']
RISK = ['tariff','restriction','ban','sanction','decline','disruption','shortage','weakness','cut','cuts','uncertainty','investigation','compliance burden','barrier','limit','limits','slowdown','contraction']
FACT_VERBS = ['announces','announced','reports','reported','raises','raised','cuts','cut','falls','fell','rises','rose','approves','approved','launches','launched','changes','changed','expands','expanded','restricts','restricted','opens','opened','closes','closed','increases','increased','decreases','decreased','issues','issued','releases','released']

SOURCE_CONTEXT = {
    'National Bureau of Statistics of China — Latest Releases': 'China',
}

SYNTHESIS_VERSION = 19

SOURCE_WEIGHTS = {
    'Primary source': 30,
    'Secondary / institutional context': 20,
    'Secondary reporting': 12,
}


def norm(value):
    return re.sub(r'\s+', ' ', (value or '').lower()).strip()


def count_terms(text, terms):
    return sum(1 for term in terms if term in text)


def unique_terms(text, terms):
    return [term for term in terms if term in text]


def classify_direction(text):
    china = count_terms(text, CHINA) > 0
    canada = count_terms(text, CANADA) > 0
    to_china = any(p in text for p in ['exports to china','export to china','sell into china','market access in china','canadian exports to china'])
    from_china = any(p in text for p in ['imports from china','import from china','chinese imports','chinese goods','chinese investment in canada'])
    if to_china and from_china:
        return 'Two-way'
    if to_china:
        return 'Canada → China'
    if from_china:
        return 'China → Canada'
    if canada and china:
        return 'Two-way'
    if china:
        return 'Global → Canada/China'
    return 'Global → Canada/China'


def analyze(item):
    text = norm(item.get('title','') + ' ' + item.get('description',''))
    china_hits = unique_terms(text, CHINA)
    if not china_hits and SOURCE_CONTEXT.get(item.get('source')) == 'China':
        china_hits = ['[source: China]']
    canada_hits = unique_terms(text, CANADA)
    categories = [c for c in CATEGORIES if count_terms(text, CATEGORIES[c])]
    categories = categories[:3] or ['Markets']
    sectors = [s for s, terms in SECTORS.items() if count_terms(text, terms)] or ['Other']

    opp_hits = unique_terms(text, OPPORTUNITY)
    risk_hits = unique_terms(text, RISK)
    commercial_hits = unique_terms(text, COMMERCIAL)
    economic_hits = unique_terms(text, ECONOMIC_SIGNALS)
    fact_hits = unique_terms(text, FACT_VERBS)
    direction = classify_direction(text)

    if len(opp_hits) >= len(risk_hits) + 2 and opp_hits:
        classification = 'OPPORTUNITY'
    elif len(risk_hits) >= len(opp_hits) + 2 and risk_hits:
        classification = 'RISK'
    elif commercial_hits:
        classification = 'WATCH'
    else:
        classification = 'NEUTRAL'

    source_bonus = SOURCE_WEIGHTS.get(item.get('source_type'), 8)
    canada_evidence = min(25, len(canada_hits) * 8)
    china_evidence = min(15, len(china_hits) * 5)
    commercial_evidence = min(15, len(commercial_hits) * 2)
    economic_evidence = min(12, len(economic_hits) * 3)
    sector_evidence = min(10, len(sectors) * 3)
    category_evidence = min(10, len(categories) * 3)
    recency_evidence = 5 if item.get('published_at') else 0
    fact_evidence = 5 if fact_hits else 0

    # Conservative score: Canadian evidence carries the most weight.
    score = min(100, 20 + source_bonus + canada_evidence + china_evidence + commercial_evidence + economic_evidence + sector_evidence + category_evidence + recency_evidence + fact_evidence)

    confidence = min(95, 40 + source_bonus // 2 + (15 if fact_hits else 0) + (10 if item.get('published_at') else 0) + (10 if china_hits else 0) + (10 if item.get('url') else 0))
    if item.get('source_type') == 'Secondary reporting':
        confidence = max(35, confidence - 10)

    # Canada evidence is valuable, but not mandatory: OBOR exists to interpret
    # Chinese developments for Canadian business. Primary Chinese/institutional
    # sources can qualify when the development has clear commercial/sector evidence.
    if not canada_hits:
        score = min(score, 78)
        confidence = min(confidence, 82)

    # A source mentioning China only as background should not become a signal.
    if not china_hits:
        score = 0
        confidence = 0

    return {
        **item,
        'categories': categories,
        'sectors': sectors,
        'direction': direction,
        'opportunity_or_risk': classification,
        'relevance_score': score,
        'confidence_score': confidence,
        'evidence': {
            'china_terms': china_hits,
            'canada_terms': canada_hits,
            'commercial_terms': commercial_hits[:12],
            'economic_terms': economic_hits[:12],
            'opportunity_terms': opp_hits[:8],
            'risk_terms': risk_hits[:8],
            'fact_terms': fact_hits[:8],
        },
    }


def candidate(item):
    title = norm(item.get('title',''))
    text = norm(title + ' ' + item.get('description',''))
    if len(title) < 18:
        return False, 'title_too_short'
    source_is_china = SOURCE_CONTEXT.get(item.get('source')) == 'China'
    if not source_is_china and not any(term in text for term in CHINA):
        return False, 'no_china_signal'
    economic_hit = any(term in text for term in ECONOMIC_SIGNALS)
    business_hit = any(term in text for term in COMMERCIAL + ['economy','economic','policy','industry','manufacturing','market'])
    # Official statistical releases are intrinsically economic/business material.
    # Source provenance supplies the China context, while the release title supplies
    # the economic signal. This prevents titles such as 'Purchasing Managers Index'
    # or 'Industrial Production' from being discarded simply because they don't say
    # 'China' or use generic commercial vocabulary.
    if not business_hit and not economic_hit:
        return False, 'low_business_relevance'
    return True, None


def make_slug(title):
    slug = re.sub(r'[^a-z0-9]+', '-', title.lower()).strip('-')
    return slug[:80] or 'signal'


def recover_published_signals(existing):
    """Recover real published signals from signal pages when the canonical JSON
    was lost or stale. The generated pages are treated as a recovery ledger,
    never as the normal source of truth. This makes the pipeline self-healing
    after a bad deployment/package replacement.
    """
    signals_dir = ROOT / 'signals'
    if not signals_dir.exists():
        return existing

    recovered = {s.get('id'): s for s in existing if s.get('id')}
    known_urls = {s.get('source_url') for s in existing if s.get('source_url')}

    def text_between(body, start, end=None):
        i = body.find(start)
        if i < 0:
            return ''
        i += len(start)
        j = body.find(end, i) if end else len(body)
        return re.sub(r'\s+', ' ', html.unescape(re.sub(r'<[^>]+>', ' ', body[i:j]))).strip()

    for page in signals_dir.glob('*/index.html'):
        body = page.read_text(errors='ignore')
        # Ignore only explicit demo pages. Older real signal pages also contain
        # the legacy demo disclaimer because they were generated by an older
        # build.py. The disclaimer is therefore NOT a reliable demo marker.
        demo_title = bool(re.search(r'<h1[^>]*>\s*Illustrative signal:', body, re.S | re.I))
        demo_source = 'Illustrative / demo content' in html.unescape(body)
        if demo_title or demo_source:
            continue
        m = re.search(r'<h1[^>]*>(.*?)</h1>', body, re.S | re.I)
        if not m:
            continue
        title = re.sub(r'\s+', ' ', html.unescape(re.sub(r'<[^>]+>', ' ', m.group(1)))).strip()
        if not title:
            continue
        sm = re.search(r'<p class="eyebrow">SUMMARY</p>\s*<p>(.*?)</p>', body, re.S | re.I)
        summary = re.sub(r'\s+', ' ', html.unescape(re.sub(r'<[^>]+>', ' ', sm.group(1)))).strip() if sm else ''
        src = re.search(r'<p class="eyebrow">SOURCE</p>.*?<a href="([^"]+)"', body, re.S | re.I)
        source_url = html.unescape(src.group(1)) if src else ''
        if not source_url or source_url in known_urls:
            continue
        meta = re.search(r'<div[^>]*>\s*<strong>OBOR relevance</strong>\s*(\d+)/100</span>\s*<span><strong>Confidence</strong>\s*(\d+)/100</span>\s*<span>(.*?)</span>', body, re.S | re.I)
        relevance = int(meta.group(1)) if meta else 60
        confidence = int(meta.group(2)) if meta else 60
        cats = [x.strip() for x in re.sub(r'<[^>]+>', '', meta.group(3)).split('·')] if meta else ['Markets']
        date_m = re.search(r'<p class="eyebrow">(OPPORTUNITY|RISK|WATCH|NEUTRAL)\s*·\s*([^<]+)</p>', body, re.I)
        classification = date_m.group(1).upper() if date_m else 'WATCH'
        event_date = date_m.group(2).strip() if date_m else None
        # Recover section text where available.
        def section(label):
            pat = rf'<p class="eyebrow">{re.escape(label)}</p>\s*<p>(.*?)</p>'
            mm = re.search(pat, body, re.S | re.I)
            return re.sub(r'\s+', ' ', html.unescape(re.sub(r'<[^>]+>', ' ', mm.group(1)))).strip() if mm else ''
        canadian = section('CANADIAN RELEVANCE')
        what = section('WHAT HAPPENED')
        interp = section('WHAT THE DATA SHOWS')
        sec_text = section('SECTORS')
        sectors = [x.strip() for x in sec_text.split('·') if x.strip()] or ['Other']
        sid = 'sig-' + hashlib.sha1(source_url.encode()).hexdigest()[:12]
        recovered[sid] = {
            'id': sid, 'title': title, 'slug': page.parent.name,
            'published_at': event_date, 'event_date': event_date,
            'source': 'Recovered from published signal page', 'source_url': source_url,
            'source_type': 'Primary source', 'summary': summary,
            'what_happened': what, 'interpretation': interp,
            'key_data': [], 'canadian_relevance': canadian,
            'opportunity_or_risk': classification, 'relevance_score': relevance,
            'confidence_score': confidence, 'sectors': sectors, 'categories': cats,
            'direction': 'Global → Canada/China', 'entities': ['China'],
            'related_signals': [], 'status': 'published', 'recovered': True
        }
        known_urls.add(source_url)
    return list(recovered.values())

def main():
    raw_path = RAW / 'items.json'
    raw = json.loads(raw_path.read_text()) if raw_path.exists() else []
    overrides = json.loads((DATA / 'overrides.json').read_text()) if (DATA / 'overrides.json').exists() else {}
    suppressed_sources = set(overrides.get('suppressed_sources', []))

    screened, rejected = [], []
    for item in raw:
        if item.get('source') in suppressed_sources:
            rejected.append({'id': item.get('id'), 'reason': 'suppressed_source'})
            continue
        ok, reason = candidate(item)
        if not ok:
            rejected.append({'id': item.get('id'), 'reason': reason})
            continue
        screened.append(analyze(item))

    screened.sort(key=lambda x: (x['relevance_score'], x['confidence_score'], x.get('published_at') or ''), reverse=True)
    candidates = [synthesize(x) for x in screened[:50]]
    for x in candidates:
        if x.get('synthesis_status') == 'source_unavailable':
            x['confidence_score'] = min(x.get('confidence_score', 0), 55)
        elif x.get('synthesis_status') == 'insufficient_evidence':
            x['confidence_score'] = min(x.get('confidence_score', 0), 60)
    rejection_counts = {}
    for r in rejected:
        rejection_counts[r['reason']] = rejection_counts.get(r['reason'], 0) + 1
    (RAW / 'candidates.json').write_text(json.dumps(candidates, ensure_ascii=False, indent=2))
    (RAW / 'rejections.json').write_text(json.dumps(rejected, ensure_ascii=False, indent=2))
    (RAW / 'screening_summary.json').write_text(json.dumps({'raw': len(raw), 'screened': len(screened), 'candidates': len(candidates), 'rejected': len(rejected), 'rejection_reasons': rejection_counts}, ensure_ascii=False, indent=2))
    print('screening_rejections=' + json.dumps(rejection_counts, sort_keys=True))

    existing = json.loads((DATA / 'signals.json').read_text()) if (DATA / 'signals.json').exists() else []
    existing = recover_published_signals(existing)
    existing_by_url = {s.get('source_url'): s for s in existing if s.get('source_url')}
    existing_urls = set(existing_by_url)
    real_existing = [s for s in existing if s.get('status') not in ('demo','suppressed')]

    new = []
    updated = []
    unchanged = 0

    # Re-synthesize every already-published real signal directly from the
    # checked-out repository state. Existing signals must not depend on the
    # current screening rank or publication gate: they were already admitted
    # by an earlier version of the engine. This makes synthesis upgrades
    # deterministic and independent of package-time generated data.
    raw_by_url = {item.get('url'): item for item in raw if item.get('url')}
    for existing_signal in real_existing:
        if existing_signal.get('synthesis_version') == SYNTHESIS_VERSION:
            unchanged += 1
            continue
        source_url = existing_signal.get('source_url')
        base = dict(raw_by_url.get(source_url, {}))
        if not base:
            base = {
                'url': source_url,
                'title': existing_signal.get('title', ''),
                'description': existing_signal.get('summary', ''),
                'published_at': existing_signal.get('event_date') or existing_signal.get('published_at'),
                'source': existing_signal.get('source', ''),
                'source_type': existing_signal.get('source_type', 'Primary source'),
                'categories': existing_signal.get('categories', []),
                'sectors': existing_signal.get('sectors', ['Other']),
                'direction': existing_signal.get('direction', 'Global → Canada/China'),
                'evidence': existing_signal.get('evidence', {}),
                'relevance_score': existing_signal.get('relevance_score', 0),
                'confidence_score': existing_signal.get('confidence_score', 0),
                'opportunity_or_risk': existing_signal.get('opportunity_or_risk', 'WATCH'),
            }
        else:
            base = analyze(base)
        rebuilt = synthesize(base)
        print(f"reprocess: {existing_signal.get('slug', existing_signal.get('id'))} -> {rebuilt.get('synthesis_status')}")
        if rebuilt.get('synthesis_status') == 'source_unavailable':
            print(f"  synthesis_error: {rebuilt.get('source_content', {}).get('error', 'unknown')}")
        if rebuilt.get('synthesis_status') != 'evidence_available':
            # Preserve the existing valid signal if the source is temporarily
            # unavailable or the new extractor cannot establish evidence.
            continue
        headline, summary, what_happened, interpretation, data_points, synthesized_canadian, synthesized_sectors = build_signal_fields(rebuilt)
        sector_text = ', '.join(synthesized_sectors[:3]).lower()
        if rebuilt.get('evidence', {}).get('canada_terms'):
            canadian = f"The source directly connects the development to Canada. Canadian businesses in {sector_text} should assess the implications for trade exposure, sourcing, market access and competitive conditions."
        else:
            canadian = f"The source does not explicitly mention Canada. For Canadian businesses in {sector_text}, the development is a watchpoint because it may affect Chinese production, demand, pricing, supply conditions or competitive dynamics."
        updated_signal = dict(existing_signal)
        updated_signal.update({
            'title': headline,
            'slug': make_slug(rebuilt.get('title', existing_signal.get('title', 'signal'))),
            'summary': summary,
            'what_happened': what_happened,
            'interpretation': interpretation,
            'key_data': data_points,
            'canadian_relevance': synthesized_canadian if synthesized_canadian else canadian,
            'sectors': synthesized_sectors,
            'source_url': source_url,
            'source_type': rebuilt.get('source_type', existing_signal.get('source_type')),
            'synthesis': rebuilt.get('source_content', {}),
            'synthesis_version': SYNTHESIS_VERSION,
            'evidence': rebuilt.get('evidence', existing_signal.get('evidence', {})),
        })
        updated.append(updated_signal)

    updated_ids = {s.get('id') for s in updated}
    for x in candidates:
        # Publication gate: conservative and intentionally deterministic.
        if x['source'] in suppressed_sources:
            continue
        if x['relevance_score'] < 60 or x['confidence_score'] < 60:
            continue
        if x.get('synthesis_status') not in ('evidence_available',):
            continue
        # Explicit Canada evidence is preferred, not mandatory. A primary-source
        # China development with strong business + sector evidence can itself be
        # a Canadian watchpoint; the Canadian implication is written as analysis.
        strong_china_signal = (
            x['evidence']['china_terms']
            and x['source_type'] in ('Primary source', 'Secondary / institutional context')
            and (len(x['evidence']['commercial_terms']) >= 2 or len(x['evidence'].get('economic_terms', [])) >= 1)
            and x['sectors'] != ['Other']
        )
        if not x['evidence']['canada_terms'] and not strong_china_signal:
            continue
        existing_signal = existing_by_url.get(x['url'])
        # Existing real signals were handled in the dedicated re-synthesis pass above.
        if existing_signal:
            continue

        sid = 'sig-' + hashlib.sha1(x['url'].encode()).hexdigest()[:12]
        headline, summary, what_happened, interpretation, data_points, synthesized_canadian, synthesized_sectors = build_signal_fields(x)
        summary = summary
        sector_text = ', '.join(synthesized_sectors[:3]).lower()
        if x['evidence']['canada_terms']:
            canadian = f"The source directly connects the development to Canada. Canadian businesses in {sector_text} should assess the implications for trade exposure, sourcing, market access and competitive conditions."
        else:
            canadian = f"The source does not explicitly mention Canada. For Canadian businesses in {sector_text}, the development is a watchpoint because it may affect Chinese production, demand, pricing, supply conditions or competitive dynamics."
        signal = {
            'id': sid,
            'title': headline,
            'slug': make_slug(x['title']),
            'published_at': (x.get('published_at') or datetime.now(timezone.utc).isoformat())[:10],
            'event_date': (x.get('published_at') or '')[:10] or None,
            'source': x['source'],
            'source_url': x['url'],
            'source_type': x['source_type'],
            'summary': summary,
            'what_happened': what_happened,
            'interpretation': interpretation,
            'key_data': data_points,
            'canadian_relevance': synthesized_canadian if synthesized_canadian else canadian,
            'sectors': synthesized_sectors,
            'opportunity_or_risk': x['opportunity_or_risk'],
            'relevance_score': x['relevance_score'],
            'confidence_score': x['confidence_score'],
            'sectors': synthesized_sectors,
            'categories': x['categories'],
            'direction': x['direction'],
            'entities': ['China'],
            'related_signals': [],
            'status': 'published',
            'evidence': x['evidence'],
            'synthesis': x.get('source_content', {}),
            'synthesis_version': SYNTHESIS_VERSION,
            'observations': x.get('source_content', {}).get('observations', []),
        }
        signal.update(overrides.get('items', {}).get(sid, {}))
        new.append(signal)

    # Replace re-synthesized existing signals by id, while preserving any
    # previously valid signal whose new source fetch/evidence extraction failed.
    updated_by_id = {s['id']: s for s in updated}
    merged = []
    for s in real_existing:
        merged.append(updated_by_id.get(s.get('id'), s))
    merged.extend(new)

    # Keep the original visual demo until at least one real signal exists.
    all_signals = merged[-200:] if merged else existing
    (DATA / 'signals.json').write_text(json.dumps(all_signals, ensure_ascii=False, indent=2))

    print(f'raw={len(raw)} screened={len(screened)} candidates={len(candidates)} rejected={len(rejected)} published_new={len(new)} updated_existing={len(updated)} unchanged={unchanged} total={len(all_signals)}')

if __name__ == '__main__':
    main()
