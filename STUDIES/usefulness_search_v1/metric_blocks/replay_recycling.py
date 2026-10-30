import hashlib,json
from pathlib import Path
import numpy as np
study=Path(__file__).resolve().parent;repo=study.parents[2];local=study/'local_recovery';root=local/'recycling_test02'
s=json.loads((root/'SUMMARY.json').read_text());assert s['passed'] and s['unchanged']
for p,h in s['inputs'].items():assert hashlib.sha256(Path(p).read_bytes()).hexdigest()==h
original=json.loads((local/'recycling_source02/ORIGINAL-SOURCE.json').read_text())
for p,h in original.items():assert hashlib.sha256((repo/p).read_bytes()).hexdigest()==h
rows=[]
for summary in s['rows']:
    target=summary['target'];results={}
    for mode in ['original','disabled','enabled']:
        folder=root/(target+'-'+mode);sup=json.loads((folder/'SUPERVISION.json').read_text());assert sup['exit_code']==0 and sup['group_drained'];results[mode]=json.loads((folder/'RAW.json').read_text())
    for a,b,c in zip(*(results[k]['chains'] for k in ['original','disabled','enabled'])):
        for k in a:
            if k!='seconds':assert a[k]==b[k]==c[k]
        assert b['recycled']==[] and len(c['recycled'])==len(c['draws'])
        assert np.isfinite(c['recycled']).all()
    v=np.asarray([c['recycled'] for c in results['enabled']['chains']]);d=v.shape[-1]//4
    assert np.min(v[:,:,2*d:])>=0 and np.max(v[:,:,2*d:])<=1+1e-14
    assert np.min(v[:,:,d:2*d])>=0
    # Jensen's inequality for each transition's conditional second moment.
    assert np.min(v[:,:,d:2*d]-v[:,:,:d]**2)>-1e-10
    if 'truth' in summary:
        means=v.mean(axis=(0,1));assert np.allclose(means,summary['conditional_estimates'],rtol=0,atol=1e-14)
        assert np.all(np.abs(means-summary['truth'])<=summary['tolerances'])
    rows.append(dict(target=target,transitions=int(np.prod(v.shape[:2])),draw_work_parity=True,probability_bounds=True,jensen_second_moment=True))
receipt=dict(passed=True,production_source_unchanged=True,checks=rows)
(study/'RECYCLING-PREFLIGHT-REPLAY.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt))
