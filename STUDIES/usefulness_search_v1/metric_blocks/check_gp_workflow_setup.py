import hashlib,json,time
from pathlib import Path
from gp_workflow_setup import target_data
from native_common import model_files
p=Path(__file__).resolve().parent;l=p/'local_recovery';r=l/'gp_workflow_setup01';r.mkdir(exist_ok=False)
_,data,_=model_files('gp_pois_regr-gp_pois_regr');original=json.loads(data.read_text());rows=[]
inputs={str(f):hashlib.sha256(f.read_bytes()).hexdigest() for f in [data,p/'gp_workflow_setup.py',p/'bounded_transport.py',Path(__file__)]}
for fold in range(4):
    mpath=l/f'gp_pilot_replay01/fold-{fold}/MAP.json';m=json.loads(mpath.read_text());inputs[str(mpath)]=hashlib.sha256(mpath.read_bytes()).hexdigest()
    for affine in [True,False]:
        label=f"fold-{fold}-{'affine' if affine else 'bounded'}";prior=l/'bounded_gp_target01'/(label+'.json');inputs[str(prior)]=hashlib.sha256(prior.read_bytes()).hexdigest()
        t=time.perf_counter();cfg=target_data(original,m,affine);(r/(label+'.json')).write_text(json.dumps(cfg));elapsed=time.perf_counter()-t
        expected=json.loads(prior.read_text());same=cfg==expected
        rows.append(dict(label=label,passed=same,construction_and_serialization_seconds=elapsed))
assert all(hashlib.sha256(Path(f).read_bytes()).hexdigest()==h for f,h in inputs.items())
result=dict(passed=all(x['passed'] for x in rows),rows=rows,inputs=inputs,scope='Exact decoded JSON equality to previously qualified bounded/affine compiled-target inputs. Component measurements only; not comparative timing.')
(r/'SUMMARY.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
