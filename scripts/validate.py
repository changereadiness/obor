#!/usr/bin/env python3
"""Production quality gate for structured signals."""
import json,sys,re
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; data=json.loads((ROOT/'data/signals.json').read_text())
errors=[]; seen=set()
allowed={'OPPORTUNITY','RISK','WATCH','NEUTRAL'}
for s in data:
    if s.get('status') == 'demo':
        continue
    sid=s.get('id');
    if not sid or sid in seen: errors.append(f'duplicate/missing id: {sid}')
    seen.add(sid)
    for k in ('title','slug','published_at','source','source_url','summary','what_happened','canadian_relevance','source_type','direction'):
        if not s.get(k): errors.append(f'{sid}: missing {k}')
    if s.get('opportunity_or_risk') not in allowed: errors.append(f'{sid}: invalid classification')
    if not 0<=int(s.get('relevance_score',-1))<=100: errors.append(f'{sid}: invalid relevance')
    if not 0<=int(s.get('confidence_score',-1))<=100: errors.append(f'{sid}: invalid confidence')
    if not re.match(r'^https?://',s.get('source_url','')): errors.append(f'{sid}: invalid source URL')
    if len(s.get('summary',''))<40 or len(s.get('summary',''))>500: errors.append(f'{sid}: invalid summary length')
    wh=s.get('what_happened')
    if not isinstance(wh,list) or not (3<=len(wh)<=6): errors.append(f'{sid}: What Happened must contain 3-6 bullets')
    for b in wh if isinstance(wh,list) else []:
        if not isinstance(b,str) or len(b)<20: errors.append(f'{sid}: weak What Happened bullet')
    obs=s.get('observations',[])
    for o in obs:
        if o.get('metric','').startswith(('growth_rate','price_change_rate')) and abs(float(o.get('value',0)))>1000: errors.append(f'{sid}: invalid observation rate')
if errors:
    print('\n'.join(errors)); sys.exit(1)
print(f'Quality gate passed: {len(data)} signals')
