import hashlib,importlib.util,json,sys
from pathlib import Path
p=Path(__file__).resolve().parent;r=p.parents[1];s=r/'STUDIES/options_flow_v1';package=r/'target/parallel-continuation-route-v1-worktree/integrations/python/python'
fixture=s/'artifacts/fresh-paired-comparison-v1/run-v1/pair00-public-fixture.json'
files=[*s.glob('*.py'),*p.glob('*.py'),fixture,Path(sys.executable),package/'owalnuts/__init__.py',*package.joinpath('owalnuts').glob('*.pyd')]
for name in ['jax','jaxlib','numpyro']:
 q=Path(importlib.util.find_spec(name).origin).parent;files.extend(q.rglob('*.py'));files.extend(q.rglob('*.pyd'))
c=dict(status='prepared_not_launched',fixture=str(fixture),package=str(package),bindings={str(f.resolve()):hashlib.sha256(f.read_bytes()).hexdigest() for f in files},public_runtime_hashes=['9ec20beeac32f5dd4ce5544a86f34e35bc90034c1e874840b19cbadd57326064','c339aa4bfeb6e1f504c0b12762f46ab14081a6e1d60817db46bd240bdbaf0001'],tiers=[1000,2000,2500,3000,4000],scope='Posthoc development, reused seeds4101/4201; not independent confirmation',max_draws=4000,timeout_seconds=1800)
with (p/'config-v2.json').open('x') as f:json.dump(c,f,indent=2)

