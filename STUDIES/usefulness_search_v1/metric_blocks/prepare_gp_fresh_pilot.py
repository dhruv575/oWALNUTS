from pathlib import Path
p=Path(__file__).resolve().parent;s=(p/'gp24_confirmation_worker.py').read_text()
old="so,data,source=model_files(name);shim=LOCAL/'nativemodels01'/name/'counted_model.so'"
new="so,_,source=model_files(name);data=LOCAL/f'gp_fresh_data01/scenario-{fold}/DATA.json';manifest=json.loads((LOCAL/'gp_fresh_data01/SUMMARY.json').read_text());assert hashlib.sha256(data.read_bytes()).hexdigest()==manifest['rows'][fold]['data_sha256'];shim=LOCAL/'nativemodels01'/name/'counted_model.so'"
assert old in s;s=s.replace(old,new)
old="refpath=STUDY.parent/'gp_count/REFERENCE.json';reference=json.loads(refpath.read_text());assert reference['qualified'];ref=dict(reference['stats'],names=reference['names']);assert len(ref['names'])==24"
new="refpath=LOCAL/'gp_fresh_reference01/SUMMARY.json';reference=next(x for x in json.loads(refpath.read_text())['references'] if x['scenario']==fold);assert reference['passed'];ref=dict(reference['stats'],names=['rho','alpha']+[f'f[{j}]' for j in range(1,12)]+[f'intensity[{j}]' for j in range(1,12)])"
assert old in s;s=s.replace(old,new).replace('8000','2000').replace('GP-24-CONFIRMATION-PROTOCOL.md','GP-FRESH-PILOT-PROTOCOL.md')
s+='''
if passed:
    from bounded_transport import fit
    from gp_workflow_setup import target_data
    t=time.perf_counter();m=fit(q[:,:100].reshape(-1,13));fit_seconds=time.perf_counter()-t
    (root/'MAP.json').write_text(json.dumps(m,indent=2)+'\\n')
    for affine in [True,False]:
        cfg=target_data(json.loads(data.read_text()),m,affine=affine)
        (root/('affine.json' if affine else 'bounded.json')).write_text(json.dumps(cfg)+'\\n')
    (root/'MAP-SETUP.json').write_text(json.dumps(dict(passed=True,training_positions=400,fit_seconds=fit_seconds,pilot_calls=counts,inputs={str(f):hashlib.sha256(f.read_bytes()).hexdigest() for f in [STUDY/'bounded_transport.py',STUDY/'gp_workflow_setup.py']}),indent=2)+'\\n')
'''
compile(s,'gp_fresh_pilot_worker.py','exec');(p/'gp_fresh_pilot_worker.py').write_text(s)
print('Prepared fixed fresh-pilot worker')
