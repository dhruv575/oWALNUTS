import hashlib,json,os,runpy,sys,time
from pathlib import Path
HERE=Path(__file__).resolve().parent
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
config=json.loads((HERE/'config.json').read_text())
def verify():
 for p,h in config['bindings'].items():
  if sha(p)!=h:raise RuntimeError('Source drift: '+p)
verify()
import owalnuts,owalnuts._owalnuts as native
runtime={str(Path(m.__file__).resolve()):sha(m.__file__) for m in [owalnuts,native]}
if set(runtime.values())!=set(config['runtime_hashes']):raise RuntimeError('Imported runtime mismatch')
out=Path(sys.argv[sys.argv.index('--out')+1]);out.parent.mkdir(parents=True,exist_ok=True)
(out.parent/(out.name+'-runtime.json')).write_text(json.dumps(runtime,indent=2))
sys.argv=[config['worker']]+sys.argv[1:]
try:runpy.run_path(config['worker'],run_name='__main__')
finally:verify()
