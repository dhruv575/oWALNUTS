import hashlib,json,subprocess,sys
from pathlib import Path
planpath=Path(sys.argv[1]);plan=json.loads(planpath.read_text());assert plan['archive']['passed'] and plan['archive']['version_id']=='awDQS7v.mEXHblmQ_VW1wQPdOACoiPjf' and plan['archive']['sha256']=='da938d25f945fa8affb85753450c7cf6d80a6a831257cc5eab893158d3d69498'
roots=[Path(x).resolve(strict=True) for x in plan['allowed_roots']];assert {str(x) for x in roots}=={'/home/ubuntu/lanes/real-counts-reference-20261030','/home/ubuntu/lanes/real-counts-importance-20261030','/home/ubuntu/lanes/real-counts-sampler-screen-20261030'}
processes=subprocess.check_output(['ps','-eo','args'],text=True)
for name in ['reference_worker.py','importance_worker.py','sampler_screen_worker.py','predictive_worker.py','repair_predictive_probability.py','audit_predictive_worker.py','score_predictive.py','audit_predictive_score.py','audit_importance.py','audit_reference.py','audit_fresh_workflows.py']:assert name not in processes,('Live dependency reader',name)
for row in plan['files']:
    p=Path(row['path']);resolved=p.resolve(strict=True);assert str(p)==str(resolved) and p.is_file() and not p.is_symlink() and any(resolved.is_relative_to(root/'results') for root in roots)
    assert p.name in ['DRAWS-STATS.npz','FUNCTIONALS.npz','RAW.json','DRAWS.npz','GRID.npz'] and p.stat().st_size==row['bytes'] and hashlib.sha256(p.read_bytes()).hexdigest()==row['sha256'],str(p)
apply='--apply' in sys.argv
if apply:
    for row in plan['files']:Path(row['path']).unlink()
    assert all(not Path(row['path']).exists() for row in plan['files'])
result=dict(passed=True,applied=apply,files=len(plan['files']),bytes=sum(x['bytes'] for x in plan['files']),plan_sha256=hashlib.sha256(planpath.read_bytes()).hexdigest(),archive=plan['archive'],scope='Individual verified archived files only; no recursive deletion')
out=planpath.with_name(planpath.stem+('-deleted.json' if apply else '-audit.json'));assert not out.exists();out.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
