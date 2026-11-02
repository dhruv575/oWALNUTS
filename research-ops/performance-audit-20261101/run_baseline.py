"""Build the same benchmark against the pre-change Git checkpoint in isolation."""
import io
import json
from pathlib import Path
import os
import shutil
import subprocess
import tarfile
import tempfile

root=Path(__file__).resolve().parents[2]
artifacts=Path(__file__).parent
cache=Path.home()/'.cache/owalnuts'
cache.mkdir(parents=True,exist_ok=True)
baseline=Path(tempfile.mkdtemp(prefix='perf-baseline-',dir=cache))
archive=subprocess.check_output(['git','archive','acea9c8a','Cargo.toml','Cargo.lock','src','examples','README.md'],cwd=root)
with tarfile.open(fileobj=io.BytesIO(archive)) as tar:
    tar.extractall(baseline,filter='data')
shutil.copyfile(root/'examples/performance_suite.rs',baseline/'examples/performance_suite.rs')
environment=dict(os.environ,CARGO_BUILD_JOBS='1')
with (artifacts/'performance-suite-before.txt').open('w') as log:
    subprocess.run(['cargo','run','--release','--features','research','--example','performance_suite'],cwd=baseline,env=environment,stdout=log,stderr=subprocess.STDOUT,check=True)
(artifacts/'baseline-build.json').write_text(json.dumps({'source':'acea9c8a','directory':str(baseline),'benchmark':'examples/performance_suite.rs'},indent=2)+'\n')
