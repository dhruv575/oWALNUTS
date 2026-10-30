import hashlib,json,tarfile,time
from pathlib import Path
import numpy as np
from fisher_qr_mp import covariance_from_samples as fast
from fisher_high_precision import covariance_from_samples as oracle
root=Path(__file__).resolve().parent;study=root.parent.parent
assert json.loads((root/'SUMMARY.json').read_text())['passed']
archive=study/'hybrid01_archive/evidence.tar-s3-restored.tar.gz';receipt=json.loads((study/'hybrid01_archive/S3-VERIFICATION.json').read_text())
assert hashlib.sha256(archive.read_bytes()).hexdigest()==receipt['sha256']
rows=[];saved=root/'exposed_inputs';saved.mkdir(exist_ok=False)
with tarfile.open(archive) as tar:
    manifest=json.load(tar.extractfile('EVIDENCE-MANIFEST.json'))
    def read(name):
        raw=tar.extractfile(name).read();entry=manifest[name];assert len(raw)==entry['bytes'] and hashlib.sha256(raw).hexdigest()==entry['sha256']
        dest=saved/name;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(raw);return json.loads(raw)
    for name in sorted(n for n in manifest if n.startswith('runs/') and n.endswith('-fit/RESULT.json')):
        prep=read(name);pilot=read(name.replace('-fit/','-pilot/'));x=np.asarray(pilot['draws']);x=x.reshape(-1,x.shape[-1]);y=np.asarray(prep['scores'])
        assert hashlib.sha256((saved/name.replace('-fit/','-pilot/')).read_bytes()).hexdigest()==prep['pilot_sha256']
        durations={'fast':[],'oracle':[]};outputs={};errors=[]
        for rep in range(3):
            for label,fn in ([('fast',fast),('oracle',oracle)] if rep%2==0 else [('oracle',oracle),('fast',fast)]):
                start=time.perf_counter();outputs[label]=fn(x,y);durations[label].append(time.perf_counter()-start)
            l=np.linalg.cholesky(outputs['oracle']);delta=outputs['fast']-outputs['oracle'];w=np.linalg.solve(l,delta);w=np.linalg.solve(l,w.T).T
            errors.append(float(np.linalg.norm(w,2)))
        ratios=np.asarray(durations['oracle'])/durations['fast']
        rows.append(dict(cell=name,passed=max(errors)<=1e-7,whitened_errors=errors,seconds=durations,geomean_speedup=float(np.exp(np.log(ratios).mean())),fast_covariance=outputs['fast'].tolist(),oracle_covariance=outputs['oracle'].tolist()))
assert len(rows)==24
gain=float(np.exp(np.mean([np.log(r['geomean_speedup']) for r in rows])))
result=dict(passed=all(r['passed'] for r in rows) and gain>=2,rows=rows,geomean_speedup=gain,target_calls=0,parent_archive_sha256=receipt['sha256'],inputs={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in [root/'fisher_qr_mp.py',root/'fisher_high_precision.py',Path(__file__),root/'FISHER-QR-MP-PREFLIGHT.md']})
(root/'MODEL-SUMMARY.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(dict(passed=result['passed'],geomean_speedup=gain,cells=len(rows))))
if not result['passed']:raise SystemExit(1)
