import hashlib,json,sys,zipfile
from pathlib import Path
p=Path(__file__).resolve().parent;r=p.parents[1];s=r/'STUDIES/options_flow_v1';package=r/'target/parallel-continuation-route-v1-worktree/integrations/python/python'
fixture=s/'artifacts/fresh-paired-comparison-v1/run-v1/pair00-public-fixture.json'
files=[*s.glob('*.py'),*p.glob('*.py'),fixture,Path(sys.executable),package/'owalnuts/__init__.py',*package.joinpath('owalnuts').glob('*.pyd')]
bindings={str(f.resolve()):hashlib.sha256(f.read_bytes()).hexdigest() for f in files}
c=dict(worker=str(s/'pymc_flow_continuation_workflow.py'),fixture=str(fixture),package=str(package),bindings=bindings,runtime_hashes=['9ec20beeac32f5dd4ce5544a86f34e35bc90034c1e874840b19cbadd57326064','c339aa4bfeb6e1f504c0b12762f46ab14081a6e1d60817db46bd240bdbaf0001'],tiers=[1000,2000,4000,8000],warmup=1000,chains=4,seeds=[4101,4201],seed_scope='Reused development seeds; no fresh-stream qualification',cpus=[0,1,2,3],seconds_per_fit=1800,disk_floor_bytes=12*1024**3)
(p/'config.json').write_text(json.dumps(c,indent=2))
with zipfile.ZipFile(p/'executed-sources.zip','x',zipfile.ZIP_DEFLATED) as z:
 for i,f in enumerate(files):z.write(f,f'{i:03d}/{f.name}')
print(hashlib.sha256((p/'config.json').read_bytes()).hexdigest())
