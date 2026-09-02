#!/usr/bin/env python3
"""Production quality gate for semantic signals."""
import json,sys,re
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; data=json.loads((ROOT/'data/signals.json').read_text())
errors=[]; seen=set(); allowed={'OPPORTUNITY','RISK','WATCH','NEUTRAL'}
for s in data:
 if s.get('status') in ('demo','suppressed'):
  continue
 sid=s.get('id')
 if not sid or sid in seen: errors.append(f'duplicate/missing id: {sid}')
 seen.add(sid)
 for k in ('title','slug','published_at','source','source_url','summary','what_happened','canadian_relevance','source_type','direction'):
  if not s.get(k): errors.append(f'{sid}: missing {k}')
 if s.get('opportunity_or_risk') not in allowed: errors.append(f'{sid}: invalid classification')
 if not 0<=int(s.get('relevance_score',-1))<=100: errors.append(f'{sid}: invalid relevance')
 if not 0<=int(s.get('confidence_score',-1))<=100: errors.append(f'{sid}: invalid confidence')
 if not re.match(r'^https?://',s.get('source_url','')): errors.append(f'{sid}: invalid source URL')
 if len(s.get('summary',''))<40: errors.append(f'{sid}: thin summary')
 if not isinstance(s.get('what_happened'),list): errors.append(f'{sid}: what_happened must be bullet list')
 synth=s.get('synthesis',{}); obs=synth.get('observations',[])
 for o in obs:
  if o.get('metric') in {'growth_rate_yoy','growth_rate_mom','price_change_rate','share'} and abs(float(o.get('value',0)))>1000: errors.append(f"{sid}: implausible rate {o.get('value')}")
 if synth.get('observation_errors',0): errors.append(f"{sid}: {synth['observation_errors']} invalid semantic observations")
if errors: print('\n'.join(errors)); sys.exit(1)
print(f'Quality gate passed: {len(data)} signals')
