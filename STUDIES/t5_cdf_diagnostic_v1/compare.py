"""Local fixed saved-draw arithmetic replay; no sampler imports or calls."""
import os
for name in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS']:os.environ[name]='1'
import hashlib,json,sys,time,platform
from pathlib import Path
from datetime import datetime,timezone
import numpy as np,scipy
from scipy.special import stdtr
import processor_snapshot as processor
started_import=time.perf_counter();import t5
jit_import_seconds=time.perf_counter()-started_import
H=Path(__file__).resolve().parent
D=Path('C:/dev/owalnuts-wt/amm-functional-audit/STUDIES/resident_predictive_harness_v1/host-development-20261027/attempt02/run/outputs')
O=H/'comparison.json'
if O.exists():raise SystemExit('Refuse overwrite')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
manifest=json.loads((D/'results.json').read_text())
files=[D/f'tick-{i:03d}.npy' for i in range(1,5)]
expected={x['tick']:x['compact_identity']['sha256'] for x in manifest['rows']}
for i,p in enumerate(files,1):assert sha(p)==expected[i]
assert sha(H/'processor_snapshot.py')=='fffc989bb6b59f4f2f055b1199f9e391fc49a5a97ea3fc436b1a348bb88875fd'
assert json.loads((H/'validation02.json').read_text())['passed']
result=dict(kind='posthoc local arithmetic only; same draws and GH64/128; no qualification',started_utc=datetime.now(timezone.utc).isoformat(),jit_import_seconds=jit_import_seconds,python=sys.version,platform=platform.platform(),versions=dict(numpy=np.__version__,scipy=scipy.__version__),thread_environment={k:os.environ[k] for k in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS']},inputs=[dict(file=str(p),sha256=sha(p)) for p in files],sources={p.name:sha(p) for p in [H/'t5.py',H/'processor_snapshot.py',Path(__file__),H/'COMPARISON.md']},rows=[])
start=time.perf_counter();deadline=start+300
for tick,p in enumerate(files,1):
    a=np.load(p,allow_pickle=False);assert a.shape==(4,400,4) and np.isfinite(a).all()
    a=a.reshape(-1,4);m=a[:,0]+.95*(a[:,3]-a[:,0]);sigma=np.exp(a[:,1]);beta=a[:,2]
    for rep in range(3):
        for name in (['scipy','exact'] if rep%2==0 else ['exact','scipy']):
            row=dict(tick=tick,repetition=rep,implementation=name,status='failed');t=time.perf_counter()
            try:
                processor.stdtr=stdtr if name=='scipy' else t5.stdtr5
                cdfs=[processor.ReturnCDF(m,sigma,beta,5,n,deadline,64*1024*1024,512) for n in [64,128]]
                rules=[c.quantiles() for c in cdfs]
                discrepancy=max(abs(cdfs[0](q)-p0) for p0,q in zip(processor.PS,rules[1]['quantiles']))
                width=rules[1]['quantiles'][2]-rules[1]['quantiles'][0]
                endpoint=max(abs(x-y)/width for x,y in zip(rules[0]['quantiles'],rules[1]['quantiles']))
                if discrepancy>1e-6 or endpoint>1e-6:raise ValueError('cross-order discrepancy')
                row.update(status='ok',rules=rules,cdf_discrepancy=discrepancy,normalized_endpoint_difference=endpoint)
            except Exception as exc:row['error']=repr(exc)
            row['seconds']=time.perf_counter()-t;result['rows'].append(row)
            O.write_text(json.dumps(result,indent=2))
            if time.perf_counter()>deadline:raise TimeoutError('overall300s')
result['inputs_unchanged']=all(sha(p)==expected[i] for i,p in enumerate(files,1))
result['summary']=[]
for tick in range(1,5):
    rows=[x for x in result['rows'] if x['tick']==tick]
    b=[x for x in rows if x['implementation']=='scipy'];c=[x for x in rows if x['implementation']=='exact']
    ok=all(x['status']=='ok' for x in rows)
    item=dict(tick=tick,all_six_ok=ok,scipy_median_seconds=float(np.median([x['seconds'] for x in b])),exact_median_seconds=float(np.median([x['seconds'] for x in c])))
    if ok:item['max_quantile_difference']=float(np.max(np.abs(np.array([x['rules'][1]['quantiles'] for x in b])-np.array([x['rules'][1]['quantiles'] for x in c]))))
    result['summary'].append(item)
result.update(elapsed_seconds=time.perf_counter()-start,ended_utc=datetime.now(timezone.utc).isoformat())
O.write_text(json.dumps(result,indent=2));print(json.dumps(result['summary'],indent=2))
