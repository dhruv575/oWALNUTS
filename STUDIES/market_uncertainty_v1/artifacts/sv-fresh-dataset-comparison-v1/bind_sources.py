"""Run only after production workflow source-final and independent review."""
import sys,json,hashlib,importlib.util,zipfile
from pathlib import Path
P=Path(__file__).resolve().parent;R=P.parents[1];S=R/'STUDIES/market_uncertainty_v1/sv_prototype';O=R/'STUDIES/options_flow_v1';prepared=P/'prepared';manifest=json.loads((prepared/'fixture-manifest.json').read_text());protocol=json.loads((prepared/'protocol.json').read_text())
package=R/'target/parallel-continuation-route-v1-worktree/integrations/python/python';runtime=[package/'owalnuts/__init__.py',*package.joinpath('owalnuts').glob('*.pyd')]
files=[*S.glob('*.py'),*O.glob('*.py'),*P.glob('*.py'),*prepared.glob('*.json'),Path(sys.executable),*runtime]
for name in ['jax','jaxlib','numpyro']:
 q=Path(importlib.util.find_spec(name).origin).parent;files.extend(q.rglob('*.py'));files.extend(q.rglob('*.pyd'))
sha=lambda f:hashlib.sha256(f.read_bytes()).hexdigest();cells=[]
for row,roles in zip(manifest['fixtures'],protocol['streams'],strict=True):
 if row['status']!='prepared':raise RuntimeError('Fixture preparation failed; retain full denominator and review instead of silently omitting')
 for arm in roles['order']:cells.append(dict(id=row['id']+'-'+arm,arm=arm,seed=roles['sampler'],fixture=row['path']))
c=dict(status='draft_not_authorized_to_run',bindings={str(f.resolve()):sha(f) for f in files},runtime_bindings={str(f.resolve()):sha(f) for f in runtime},package=str(package),cells=cells,protocol=protocol)
with (prepared/'config.json').open('x') as f:json.dump(c,f,indent=2)
with zipfile.ZipFile(prepared/'sources.zip','x',zipfile.ZIP_DEFLATED) as z:
 for i,f in enumerate(files):
  if f.suffix=='.py':z.write(f,f'{i}/{f.name}')
print('Prepared12-cell draft',sha(prepared/'config.json'))
