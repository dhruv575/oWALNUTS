from pathlib import Path
import json,hashlib,zipfile,shutil,importlib.metadata
folder=Path('target/market-compute-route-v1').resolve();out=folder/'evidence';out.mkdir()
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()
sourcefiles=[p for p in folder.glob('*') if p.suffix in ('.py','.txt')]
manifest={str(p):dict(sha256=sha(p),size=p.stat().st_size) for p in sourcefiles}
with zipfile.ZipFile(out/'executed-and-analysis-sources.zip','x',compression=zipfile.ZIP_DEFLATED) as z:
 for p in sourcefiles:z.write(p,p.name)
(out/'source-manifest.json').write_text(json.dumps(manifest,indent=2))
raw={str(p):dict(sha256=sha(p),bytes=p.stat().st_size,scope='Retained canonical draws, no pickle; preserved externally to compact archive') for p in folder.rglob('draws.npy')}
(out/'raw-array-manifest.json').write_text(json.dumps(raw,indent=2))
files=[]
for p in folder.rglob('*'):
 if not p.is_file() or out in p.parents or '__pycache__' in p.parts or p.suffix=='.npy':continue
 files.append(p)
for p in files:
 dest=out/'artifacts'/p.relative_to(folder);dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,dest)
versions={n:importlib.metadata.version(n) for n in ('numpy','scipy','arviz','numba','jax','jaxlib','numpyro','pymc','pytensor')}
(out/'validation-and-runtime.json').write_text(json.dumps(dict(oracle_tests=3,oracle_runtime_seconds=.625,tests_passed=True,oracle_scope='Dense conditional Gaussian likelihood and moments; explicit FFBS seed731; missing NaN placeholders and grid preservation',versions_recorded_after_terminal=versions,all_jobs_terminal=True,scope='Exploratory synthetic; no qualification; source versions in original config checked after each first-batch arm, corrected source separately retained'),indent=2))
(out/'.gitattributes').write_text('* -text\n')
checks={str(p.relative_to(out)).replace('\\','/'):sha(p) for p in out.rglob('*') if p.is_file()}
(out/'CHECKSUMS.json').write_text(json.dumps(checks,indent=2));print(json.dumps(dict(files=len(checks),raw_bytes=sum(v['bytes'] for v in raw.values()),archive=str(out))))
