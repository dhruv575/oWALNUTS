import importlib.metadata,json,platform,subprocess,sys
from pathlib import Path
root=Path(sys.argv[1]);packages={name:importlib.metadata.version(name) for name in ('owalnuts','nutpie','numpy','scipy','arviz','psutil')}
out=dict(python=sys.version,platform=platform.platform(),packages=packages,cpu=subprocess.check_output(['lscpu'],text=True),compiler=subprocess.check_output(['g++','--version'],text=True),bridgestan='2.9.0',thread_environment={'OPENBLAS_NUM_THREADS':1,'OMP_NUM_THREADS':1,'MKL_NUM_THREADS':1},chains_per_fit=4,cores_per_fit=1,concurrent_jobs=12)
(root/'ENVIRONMENT.json').write_text(json.dumps(out,indent=2)+'\n')
