import hashlib,json
from pathlib import Path
P=Path(__file__).resolve().parent/'run-v1'
load=lambda p:json.loads(p.read_text())
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(8*1024**2),b''):h.update(b)
 return h.hexdigest()
e=load(P/'execution.json');assert e['status']=='terminal'
rows=[];pairs=[]
for r in e['records']:
 d=P/f"pair{r['pair']}-threads{r['threads']}";report=load(d/'python-pymc-flow-report.json')
 rows.append(dict(pair=r['pair'],threads=r['threads'],outer_seconds=r['outer_seconds'],status=report['status'],precision_pass=report.get('precision_pass'),compile_seconds=report.get('compilation',{}).get('compile_seconds'),adapt_seconds=report.get('adapt_seconds'),attempts=report.get('attempts'),worker_seconds=report.get('end_to_end_seconds')))
for pair in (0,1):
 a=P/f'pair{pair}-threads1';b=P/f'pair{pair}-threads4';ar=load(a/'python-pymc-flow-report.json');br=load(b/'python-pymc-flow-report.json')
 ad=sorted(x.name for x in a.glob('draws-*'));bd=sorted(x.name for x in b.glob('draws-*'));checks=dict(same_tiers=ad==bd)
 for tier in ad:
  left=a/tier/'python-pymc-flow-raw.json';right=b/tier/'python-pymc-flow-raw.json'
  checks[tier+'_raw_byte_identity']=right.exists() and sha(left)==sha(right)
 for field in ['warmup_diagnostics','warmup_work','initialization_target_calls','warmup_target_calls','adapted_metadata']:
  checks[field]=ar.get(field)==br.get(field)
 x,y=[next(r for r in rows if r['pair']==pair and r['threads']==t) for t in (1,4)]
 pairs.append(dict(pair=pair,checks=checks,identity_pass=all(checks.values()),both_precision_pass=x['precision_pass'] is True and y['precision_pass'] is True,outer_serial_over_parallel=x['outer_seconds']/y['outer_seconds'],adapt_serial_over_parallel=x['adapt_seconds']/y['adapt_seconds']))
result=dict(qualified=False,scope='Development mechanism test, same posterior and reused seeds; no NumPyro speed comparison or calibration claim',rows=rows,pairs=pairs,all_cost_seconds=e['outer_seconds'])
(P/'comparison.json').write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2))
