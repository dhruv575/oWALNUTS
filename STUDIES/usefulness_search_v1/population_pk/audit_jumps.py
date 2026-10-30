import json
import numpy as np
import arviz as az
from native import Native,ROOT
from involutions import global_exchange,local_exchange
b=Native();rows=[];summary=[]
for folder in sorted((ROOT/'jump01').glob('*/result')):
 q=np.load(folder/'draws.npz')['q'];r=json.loads((folder/'RESULT.json').read_text())
 data=az.from_dict(posterior={'q':q})
 summary.append(dict(engine=r['engine'],rhat_max=float(np.max(az.rhat(data)['q'])),ess_bulk_min=float(np.min(az.ess(data,method='bulk')['q'])),seconds=r['seconds'],calls_errors=r['calls_errors'],divergences=r['divergences'],depth_hits=r['depth_hits'],primary_fraction=r['primary_fraction'],crossings=r['crossings'],accepted=r['accepted']))
 for c in range(4):
  for j in [0,13,26,39]:
   x=q[c,j]
   for label,T in [('identity',lambda v:v),('global',global_exchange)]+[(str(i),lambda v,i=i:local_exchange(v,i)) for i in range(12)]:
    y=T(x)
    try:value,_=b.value(y);offset=b.density(y)-value;rows.append(dict(engine=r['engine'],chain=c,draw=j,transform=label,offset=offset))
    except ValueError:rows.append(dict(engine=r['engine'],chain=c,draw=j,transform=label,error='ODE evaluation failed'))
offsets=[r['offset'] for r in rows if 'offset' in r];spread=float(np.ptp(offsets));failed=sum('error' in r for r in rows)
result=dict(summary=summary,density_audit=dict(points=len(rows),failed=failed,offset_range=spread,passed=failed==0 and spread<1e-5),rows=rows,qualified_reference=False)
(ROOT/'JUMP-AUDIT.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({k:v for k,v in result.items() if k!='rows'}));b.close()
