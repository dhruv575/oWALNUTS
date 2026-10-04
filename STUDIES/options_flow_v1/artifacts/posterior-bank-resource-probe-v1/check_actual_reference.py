from pathlib import Path
import sys,json,time
H=Path(__file__).resolve().parent;sys.path.insert(0,str(H));import bank_adapter as a
R=H.parents[1];S=R/'STUDIES/options_flow_v1';P=S/'artifacts/posterior-resource-pilot-v1';plan=a.load(P/'plan.json');rows=[]
for c in plan['cells']:
 if c['backend']!='reference':continue
 d=Path(c['out']);rp=d/'fit/report.json';worker=a.load(rp)
 spec=dict(id=c['id'],backend=c['backend'],directory=str(d),result_sha256=a.sha(d/'resource-result.json'),compact_sha256=a.sha(d/'extracted/compact.npz'),worker_report=str(rp),worker_report_sha256=a.sha(rp),fixture=c['fixture'],fixture_sha256=c['fixture_sha256'],sampler_seed=c['seed'],initialization_seed=c['init_seed'],worker_bindings=worker['bindings'],study=plan['study'],initialization_helper_sha256=a.sha(S/'masked_market_comparison_plan.py'),predictive_contract=a.load(d/'resource-result.json')['extraction']['predictive_contract'])
 tick=time.perf_counter()
 try:
  result=a.admit_fit(spec,plan['posterior_sha256']);row=dict(id=c['id'],diagnostic_schema_pass=True,parameters=list(result['parameters']['8000']),qualified=False)
 except Exception as exc:row=dict(id=c['id'],diagnostic_schema_pass=False,error=f'{type(exc).__name__}: {exc}')
 row['seconds']=time.perf_counter()-tick;rows.append(row)
with (H/'actual-reference-adapter-v1.json').open('x') as f:json.dump(dict(rows=rows,scope='Pilot schema diagnostic only; excluded from bank',adapter_sha256=a.sha(H/'bank_adapter.py')),f,indent=2)
print(rows)
