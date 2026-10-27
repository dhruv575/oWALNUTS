#!/bin/bash
set -eu
cd /home/ubuntu/lanes/unified-readiness-20261027
installation02/work/env/bin/python - <<'PY'
from pathlib import Path
import hashlib,json,sys
assert hashlib.sha256(Path('smoke-source.tar.gz').read_bytes()).hexdigest()=='c90c9a1c495adaaf15a8e6d1ad718a56fde435fda8d73df0183f6dd87f5bec49'
s=json.loads(Path('installation02/supervisor.json').read_text());assert s['preparation_complete'] and s['group_drained']
p=Path('installation02/work');r=json.loads((p/'preparation.json').read_text());assert r['status']=='complete'
assert hashlib.sha256((p/'runtime-identity.json').read_bytes()).hexdigest()==r['runtime_identity_sha256']
i=json.loads((p/'runtime-identity.json').read_text());assert sys.prefix==i['prefix']
assert all(hashlib.sha256(Path(path).read_bytes()).hexdigest()==digest for path,digest in i['native_modules'].items())
print('prepared runtime identity admitted')
PY
mkdir smoke-source
tar -xzf smoke-source.tar.gz -C smoke-source
nohup taskset -c 0-3 installation02/work/env/bin/python smoke-source/STUDIES/independent_sv_reference_preflight_v1/unified-readiness/supervise_smoke.py --bundle /home/ubuntu/lanes/unified-readiness-20261027/smoke-source --preparation /home/ubuntu/lanes/unified-readiness-20261027/installation02/work --root /home/ubuntu/lanes/unified-readiness-20261027/smoke01 > smoke-launcher.log 2>&1 </dev/null &
echo $! > smoke-supervisor.pid
cat smoke-supervisor.pid
date -u +%FT%TZ
