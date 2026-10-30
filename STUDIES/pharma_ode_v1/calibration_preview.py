import json
from analyze import rows,tuning_key
from backend import ROOT
from worker import CASES
rr=rows(ROOT/'initial02');out={}
for case in CASES[:4]:
    out[case]={}
    for e in ('walnuts','nuts'):
        pool=[r for r in rr if r['phase']=='calibrate' and r['case']==case and r['config'].startswith(e+'_')]
        if any(r['status']=='missing_or_censored' for r in pool):out[case][e]='Calibration incomplete';continue
        r=min(pool,key=tuning_key);out[case][e]={k:r.get(k) for k in ('config','seconds','target_calls','summary')}
print(json.dumps(out,indent=2))
