import importlib.metadata,json,platform,subprocess,sys,hashlib
from pathlib import Path
root=Path(sys.argv[1]);packages={name:importlib.metadata.version(name) for name in ('owalnuts','nutpie','numpy','scipy','arviz','psutil')}
out=dict(python=sys.version,platform=platform.platform(),packages=packages,cpu=subprocess.check_output(['lscpu'],text=True),compiler=subprocess.check_output(['g++','--version'],text=True),bridgestan='2.9.0',thread_environment={'OPENBLAS_NUM_THREADS':1,'OMP_NUM_THREADS':1,'MKL_NUM_THREADS':1},chains_per_fit=4,cores_per_fit=1,concurrent_jobs=12)
out['sampler_package_hashes']={}
for name in ('owalnuts','nutpie'):
    package=importlib.metadata.distribution(name)
    out['sampler_package_hashes'][name]={str(p):hashlib.sha256(Path(package.locate_file(p)).read_bytes()).hexdigest() for p in package.files if str(p).endswith(('.so','.py','.json')) and Path(package.locate_file(p)).is_file()}
(root/'ENVIRONMENT.json').write_text(json.dumps(out,indent=2)+'\n')
