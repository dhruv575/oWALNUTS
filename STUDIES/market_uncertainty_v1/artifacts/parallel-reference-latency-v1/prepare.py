import hashlib,json,sys,zipfile,importlib.util
from pathlib import Path
p=Path(__file__).resolve().parent;r=p.parents[1];s=r/'STUDIES/options_flow_v1'
f=s/'artifacts/fresh-paired-comparison-v1/run-v1/pair00-public-fixture.json'
files=[*s.glob('*.py'),*p.glob('*.py'),f,Path(sys.executable)]
for name in ['jax','jaxlib','numpyro']:
 spec=importlib.util.find_spec(name)
 files.extend(Path(spec.origin).parent.rglob('*.py'))
 files.extend(Path(spec.origin).parent.rglob('*.pyd'))
bindings={str(x.resolve()):hashlib.sha256(x.read_bytes()).hexdigest() for x in files}
c=dict(worker=str(s/'mixed_flow_reference.py'),fixture=str(f),bindings=bindings,source_commit='924e04e',chains=4,warmup=1000,tiers=[1000,2000,4000,8000],seeds=[4101,4201],scope='Development reused seeds, reference runs after public; not randomized comparative qualification',cpus=[0,1,2,3],target_accept=.9,implementation='associative',chain_method='parallel',timeout_seconds=1800)
(p/'config.json').write_text(json.dumps(c,indent=2))
with zipfile.ZipFile(p/'executed-study-sources.zip','x',zipfile.ZIP_DEFLATED) as z:
 for x in [*s.glob('*.py'),*p.glob('*.py')]:z.write(x,str(x.relative_to(r)))
print(hashlib.sha256((p/'config.json').read_bytes()).hexdigest())
