import argparse,hashlib,json,runpy,sys
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--config',type=Path,required=True);p.add_argument('--arm',required=True);a,rest=p.parse_known_args();rest=rest[1:] if rest[0]=='--' else rest
sha=lambda f:hashlib.sha256(Path(f).read_bytes()).hexdigest();identity=sha(a.config);c=json.loads(a.config.read_text())
def verify():
 assert sha(a.config)==identity
 for f,h in c['bindings'].items():assert sha(f)==h,f
verify()
if a.arm=='public':
 import owalnuts,owalnuts._owalnuts as native
 actual={str(Path(x.__file__).resolve()):sha(x.__file__) for x in [owalnuts,native]}
 assert set(actual.values())==set(c['public_runtime_hashes'])
else:
 import jax,numpyro
 assert jax.default_backend()=='cpu' and jax.local_device_count()==4
 actual=dict(jax=jax.__version__,numpyro=numpyro.__version__,devices=[str(x) for x in jax.local_devices()])
out=Path(rest[rest.index('--out')+1]);(out.parent/(out.name+'-runtime.json')).write_text(json.dumps(actual,indent=2))
sys.argv=rest
try:runpy.run_path(rest[0],run_name='__main__')
finally:verify()
