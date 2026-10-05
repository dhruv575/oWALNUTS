import hashlib,json,os,runpy,sys
from pathlib import Path
p=Path(__file__).resolve().parent;c=json.loads((p/'config.json').read_text());sha=lambda f:hashlib.sha256(Path(f).read_bytes()).hexdigest()
def verify():
 for f,h in c['bindings'].items():assert sha(f)==h,f
verify()
import jax,numpyro
assert jax.default_backend()=='cpu' and jax.local_device_count()==4
out=Path(sys.argv[sys.argv.index('--out')+1]);out.parent.mkdir(exist_ok=True,parents=True)
(out.parent/(out.name+'-runtime.json')).write_text(json.dumps(dict(jax=jax.__version__,numpyro=numpyro.__version__,jax_path=jax.__file__,numpyro_path=numpyro.__file__,devices=[str(x) for x in jax.local_devices()]),indent=2))
sys.argv=[c['worker']]+sys.argv[1:]
try:runpy.run_path(c['worker'],run_name='__main__')
finally:verify()
