import hashlib,json,subprocess,sys
from pathlib import Path
study=Path(__file__).resolve().parent;local=study/'local_recovery';dest=local/'nutpie_baseline';venv=local/'nutpie_env'
assert json.loads((local/'localscaled08_archive/VERIFICATION.json').read_text())['passed']
for n in ['ALGEBRA-SUPERVISION.json','MODELS-SUPERVISION.json']:
    sup=json.loads((local/'fisherqr01'/n).read_text());assert sup['group_drained']
receipt=json.loads((dest/'DOWNLOAD.json').read_text(encoding='utf-8-sig'));wheel=dest/receipt['filename']
assert hashlib.sha256(wheel.read_bytes()).hexdigest()==receipt['sha256']
assert not venv.exists();subprocess.run([sys.executable,'-m','venv',str(venv)],check=True)
packages=json.loads((local/'compat01/ENVIRONMENT.json').read_text())['packages']
constraints=dest/'CONSTRAINTS.txt';constraints.write_text('\n'.join(f'{name}=={version}' for name,version in sorted(packages.items()))+'\n')
with (dest/'INSTALL.log').open('w') as log:
    subprocess.run([str(venv/'bin/python'),'-m','pip','install','--no-cache-dir','--report',str(dest/'INSTALL-REPORT.json'),'-c',str(constraints),str(wheel),'bridgestan','stanio','scipy','psutil','mpmath','tbb'],check=True,stdout=log,stderr=subprocess.STDOUT)
print(json.dumps(dict(installed=True,environment=str(venv),wheel_sha256=receipt['sha256'])))
