import itertools,json
from pathlib import Path
import numpy as np,arviz as az
root=Path(__file__).resolve().parent/'results';rows=json.loads((root/'PROGRESS.json').read_text())
result=dict(passed=False,rows=rows,scope='160 training functionals only; independent audit pending')
if len(rows)==4 and all(x['passed'] for x in rows):
    v=np.concatenate([np.load(root/str(g)/'FUNCTIONALS.npz')['values'] for g in range(4)])
    ds=az.convert_to_dataset({'p':v});stats={k:np.asarray(fn(ds).p) for k,fn in [('rhat',lambda x:az.rhat(x,method='rank')),('bulk',lambda x:az.ess(x,method='bulk')),('tail',lambda x:az.ess(x,method='tail')),('mcse',lambda x:az.mcse(x,method='mean'))]};stats.update(mean=v.mean((0,1)),sd=v.reshape(-1,160).std(0,ddof=1))
    pairs=[]
    for a,b in itertools.combinations(rows,2):
        x,y=a['stats'],b['stats'];delta=abs(np.array(x['mean'])-y['mean']);z=delta/np.sqrt(np.array(x['mcse'])**2+np.array(y['mcse'])**2);rel=abs(np.array(x['sd'])-y['sd'])/((np.array(x['sd'])+y['sd'])/2)
        pairs.append(dict(groups=[a['group'],b['group']],max_z=float(max(z)),max_mean_sd=float(max(delta/stats['sd'])),max_sd_relative=float(max(rel))))
    checks=dict(finite=all(np.isfinite(x).all() for x in stats.values()),rhat=max(stats['rhat'])<=1.01,bulk=min(stats['bulk'])>=4000,tail=min(stats['tail'])>=2000,mcse=max(stats['mcse']/stats['sd'])<=.02,pairs=all(x['max_z']<=4 and x['max_mean_sd']<=.05 and x['max_sd_relative']<=.1 for x in pairs))
    result.update(passed=bool(all(checks.values())),checks={k:bool(x) for k,x in checks.items()},pairs=pairs,stats={k:x.tolist() for k,x in stats.items()})
(root/'SUMMARY.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n');print(json.dumps(dict(passed=result['passed'])))
