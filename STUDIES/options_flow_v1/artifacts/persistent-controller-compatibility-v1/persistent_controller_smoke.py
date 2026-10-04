import copy,json,time,sys,os
from pathlib import Path
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
from continuation_comparison import sha,save,attested_dependencies
from persistent_comparison_plan import validate_transport_proofs,validate_fit,timing_report
from persistent_masked_workflow import execute
out=HERE/'artifacts/persistent-controller-compatibility-v1'
out.mkdir(exist_ok=False)
package=HERE.parents[1]/'integrations/python/python'
attest=HERE/'artifacts/continuation-release-attested-v1.json'
identity=attested_dependencies(attest,Path(sys.executable).resolve(),package)
# Exploratory smoke streams only; these are not prospective benchmark seeds.
seeds={'numpyro':[196120001,196120002,196120003],'pymc':[196120011,196120012,196120013]}
data=dict(y=[[.05*((i%7)-3)]*4 for i in range(128)],x=[[.1*((i%5)-2)]*4 for i in range(128)],observation_mask=[[i%3!=0]*4 for i in range(128)],grid_index=list(range(128)),rho=.95,nu=5.)
from flow_starts import canonical_starts
data['initial_positions']=canonical_starts(data,4).tolist()
a=dict(data=data,precision_family=[[1,0],[1,2]],holdout=dict(x=[[.2]*4],y=[[None]*4],x_available=[[True,False,True,False]],observation_mask=[[False]*4],grid_index=[128]))
b=copy.deepcopy(a);b['data']['observation_mask'][0]=[True]*4
paths=[]
for i,f in enumerate([a,b,a]):
    path=out/f'fixture-{i}.json';save(path,f);paths.append(path)
save(out/'intent.json',dict(kind='Actual schema/transport smoke; not benchmark or qualification',seeds=seeds,predictive_seeds={k:[s+130000 for s in v] for k,v in seeds.items()},bindings=identity,study_sources={str(p):sha(p) for p in HERE.glob('*.py')},warmup=1000,draws=1000,T=128,G=4,full_production_cap_unchanged=True))
results=[];records=[]
for backend in ['numpyro','pymc']:
    tick=time.perf_counter();directory=out/f'pair0-{backend}'
    reports=execute(paths,directory,seeds[backend],backend,warmup=1000,tiers=(1000,),batch=1000)
    elapsed=time.perf_counter()-tick;checks=[]
    for i,r in enumerate(reports):
        f=dict(path=str(paths[i]),sha256=sha(paths[i]),starts=data['initial_positions'],forecast_cells=a['precision_family'])
        row=dict(index=i,status=r['status'],error=r.get('error'))
        try:
            validate_transport_proofs(r,f,seeds[backend][i],backend,directory/f'fit-{i}')
            row['transport_proofs_pass']=True
            try:
                passed=validate_fit(r,f,seeds[backend][i],backend,directory/f'fit-{i}');row['production_gate']=passed
                if not r['precision_pass']:raise AssertionError('Truncated nonpassing cap was accepted')
            except ValueError as exc:
                if r['precision_pass'] or 'cap mismatch' not in str(exc):raise
                row['expected_truncated_cap_rejection']=str(exc)
        except Exception as exc:row['validation_error']=f'{type(exc).__name__}: {exc}'
        checks.append(row)
    results.append(dict(backend=backend,elapsed_seconds=elapsed,checks=checks));records.append(dict(id=f'pair0-{backend}',elapsed_seconds=elapsed,success=False))
    save(out/f'{backend}-validation.json',results[-1]);print(json.dumps(results[-1]),flush=True)
save(out/'timing-validation.json',timing_report({'cohorts':records},out))
save(out/'summary.json',dict(results=results,qualified=False,performance_claim=False))
