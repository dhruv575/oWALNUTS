import json,hashlib
from pathlib import Path
p=Path(__file__).resolve().parent;L=lambda f:json.loads(f.read_text());sha=lambda f:hashlib.file_digest(f.open('rb'),'sha256').hexdigest()
checks=[];rows=[]
for pair in [0,1]:
 for arm in ['public','reference']:
  d=p/'run-v2'/f'pair{pair}-{arm}';report=L(d/('python-pymc-flow-report.json' if arm=='public' else 'report.json'))
  selected=report['attempts'][-1]['draws'];execution=next(x for x in L(p/'run-v2/execution.json')['records'] if x['pair']==pair and x['arm']==arm)
  rows.append(dict(pair=pair,arm=arm,selected_draws=selected,precision_pass=report['precision_pass'],outer_seconds=execution['outer_seconds']))
  for tier in [1000,2000]:
   if arm=='public':
    old=p.parent/'parallel-continuation-latency-v1/run-v1'/f'pair{pair}-threads4'/f'draws-{tier}/python-pymc-flow-raw.json';new=d/f'draws-{tier}/python-pymc-flow-raw.json'
   else:old=p.parent/'parallel-reference-latency-v1/run-v1'/f'pair{pair}-parallel-reference'/f'draws-{tier}-raw.json';new=d/f'draws-{tier}-raw.json'
   checks.append(dict(pair=pair,arm=arm,draws=tier,entire_raw_bytes_identical=sha(old)==sha(new)))
out=dict(qualified=False,rows=rows,prefix_checks=checks,failed_v1_cost_seconds=L(p/'run-v1/execution.json')['outer_seconds'],corrected_v2_cost_seconds=L(p/'run-v2/execution.json')['outer_seconds'],scope='Posthoc reused-seed schedule investigation, nonexclusive host, not fresh qualification')
(p/'comparison.json').write_text(json.dumps(out,indent=2));print(json.dumps(out,indent=2))
