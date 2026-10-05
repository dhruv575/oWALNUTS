import json,math
from pathlib import Path
p=Path(__file__).resolve().parent;root=p.parent
L=lambda f:json.loads(f.read_text())
def phases(d):
 starts={};totals={}
 for line in (d/'phase-events.jsonl').read_text().splitlines():
  r=json.loads(line);k=(r['stage'],r.get('draws'))
  if r['event']=='start':starts[k]=r['seconds']
  elif r['event']=='end' and k in starts:totals[r['stage']]=totals.get(r['stage'],0)+r['seconds']-starts[k]
 return totals
def endpoints(e):
 rows={n:(v['interval_90'],v['endpoint_mcse']) for n,v in e['functionals'].items()}
 for row in e['forecast']['rows']:rows[f"forecast_{row['horizon']}_{row['group']}"]=([row['lower'],row['upper']],row['endpoint_mcse'])
 return rows
result=[]
for pair in [0,1]:
 pd=root/'parallel-continuation-latency-v1/run-v1'/f'pair{pair}-threads4';rd=p/'run-v1'/f'pair{pair}-parallel-reference'
 pr=L(pd/'python-pymc-flow-report.json');rr=L(rd/'report.json');tier=pr['attempts'][-1]['draws'];pf=L(pd/f'draws-{tier}/fit-report.json')
 a=endpoints(pf['evaluation']);b=endpoints(rr['evaluation']);agreement=[]
 for n in a:
  for i in [0,1]:
   delta=abs(a[n][0][i]-b[n][0][i]);agreement.append(dict(name=n,end=i,absolute_difference=delta,reference_width_fraction=delta/(b[n][0][1]-b[n][0][0]),combined_mcse_units=delta/math.hypot(a[n][1][i],b[n][1][i])))
 result.append(dict(pair=pair,public_phases=phases(pd),reference_phases=phases(rd),public_attempts=[dict(draws=x['draws'],reasons=x['screen']['reasons'],worst=x['screen']['max_endpoint_mcse_over_width'],target_calls=x.get('added_target_calls')) for x in pr['attempts']],public_warmup_calls=pr['warmup_target_calls'],reference_checkpoints=rr['checkpoints'],max_combined_mcse=max(agreement,key=lambda x:x['combined_mcse_units']),max_width_difference=max(agreement,key=lambda x:x['reference_width_fraction']),agreement=agreement))
(p/'comparison.json').write_text(json.dumps(dict(qualified=False,scope='Two development pairs, reference executed later; endpoint agreement descriptive, shared prediction seeds induce dependence',pairs=result),indent=2))
for r in result:print({k:v for k,v in r.items() if k not in ['agreement','reference_checkpoints']})
