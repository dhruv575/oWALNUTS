import hashlib,io,json,sys,tarfile
from pathlib import Path
import numpy as np
study=Path(__file__).resolve().parent;local=study/'local_recovery';name=sys.argv[1];qualification=name=='nativemodels01';assert qualification or name in [f'nativescreen{i:02d}' for i in range(1,5)]
root=local/name;s=json.loads((root/'SUMMARY.json').read_text());models=['arma-arma11','arK-arK','sblrc-blr','eight_schools-eight_schools_centered','garch-garch11','gp_pois_regr-gp_pois_regr']
if qualification:assert s['passed']
else:assert len(s['rows'])==42 and len({(r['model'],r['seed'],r['arm']) for r in s['rows']})==42 and s['unchanged']
files={str(p.relative_to(root)):p for p in root.rglob('*') if p.is_file() and '__pycache__' not in p.parts};audits=[]
for model in models:
    folder=root/model;sup=json.loads((folder/'SUPERVISION.json').read_text());assert sup['group_drained']
    if sup['exit_code']!=0:
        assert not qualification;assert all(not r['passed'] for r in s['rows'] if r['model']==model);audits.append(dict(model=model,failed_worker=True));continue
    cell=json.loads((folder/'SUMMARY.json').read_text())
    for i,(p,h) in enumerate(cell['inputs'].items()):
        path=Path(p);assert hashlib.sha256(path.read_bytes()).hexdigest()==h;files[f'dependencies/{model}/{i}-{path.name}']=path
    if qualification:
        assert cell['passed'] and cell['explicit_gradient_calls']==64
        for mode in ['draw_diag','diag','low_rank']:
            with np.load(folder/(mode+'-plain.npz')) as a,np.load(folder/(mode+'-counted.npz')) as b:assert np.array_equal(a['draws'],b['draws']) and np.array_equal(a['sample_stats__diverging'],b['sample_stats__diverging'])
        audits.append(dict(model=model,three_exact_trajectories=True))
    else:
        assert cell['unchanged'];pilot=json.loads((folder/'pilot/RESULT.json').read_text());pt=json.loads((folder/'pilot/TIMING.json').read_text())['post_import_operation_seconds']
        for row in cell['rows']:
            if 'error' in row:assert not row['passed'];continue
            arm=row['arm'];p=folder/arm;timing=json.loads((p/'TIMING.json').read_text());result=json.loads((p/'RESULT.json').read_text());counts=timing['api_calls'];assert all(counts[k]==0 for k in ['value','hessian','hvp'])
            assert row['seconds']==timing['operation_seconds'] and row['seconds']>0
            if arm.startswith('native_'):
                assert row['calls']==counts['gradient'] and counts['gradient']>=result['native_steps'] and timing['shared_pilot_seconds']==0
                settings=json.loads((p/'SETTINGS.json').read_text());assert settings['tune']==1100 and settings['draws']==2000 and settings['seed']==row['seed']
            else:
                policy=json.loads((p/'POLICY.json').read_text());args=json.loads((p/'INPUT.json').read_text());assert counts['gradient']==policy['calls']
                assert row['calls']==pilot['target_calls']+policy['calls']+result['target_calls'];assert timing['shared_pilot_seconds']==pt and row['seconds']==pt+timing['stage_operation_seconds']
                assert args['warmup']==750 and args['draws']==2000 and args['seed']==row['seed']+100000 and args['starts']==np.asarray(pilot['draws'])[:,-1,:].tolist()
            if row.get('bulk') is not None:assert row['efficiency']==row['bulk']/row['calls'] and row['time_efficiency']==row['bulk']/row['seconds']
        audits.append(dict(model=model,costs_and_schedules_verified=True))
for i,(p,h) in enumerate(s.get('inputs',{}).items()):
    path=Path(p);assert hashlib.sha256(path.read_bytes()).hexdigest()==h;files[f'provenance/{i}-{path.name}']=path
for p in [Path(__file__),study/'run_native_model_qualification.py',study/'NATIVE-COMPARISON-SCREEN.md',local/'inputs/resource_monitor.py']:files['provenance/'+p.name]=p
dest=local/(name+'_archive');dest.mkdir(exist_ok=False);manifest={n:dict(bytes=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for n,p in files.items()};archive=dest/'evidence.tar.gz'
with tarfile.open(archive,'w:gz') as tar:
    raw=json.dumps(manifest,indent=2).encode();info=tarfile.TarInfo('EVIDENCE-MANIFEST.json');info.size=len(raw);tar.addfile(info,io.BytesIO(raw))
    for n,p in files.items():tar.add(p,arcname=n,recursive=False)
with tarfile.open(archive) as tar:
    for n,e in manifest.items():
        raw=tar.extractfile(n).read();assert len(raw)==e['bytes'] and hashlib.sha256(raw).hexdigest()==e['sha256']
r=dict(passed=True,members=len(manifest),sha256=hashlib.sha256(archive.read_bytes()).hexdigest(),audits=audits,scope='Local archive read-back/cost audit, not statistical success or off-device backup.')
(dest/'VERIFICATION.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r))
