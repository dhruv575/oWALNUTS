#!/bin/bash
set -eu
cd /home/ubuntu/lanes/unified-readiness-20261027
installation02/work/env/bin/python - <<'PY'
from pathlib import Path
import hashlib,json,sys
assert hashlib.sha256(Path('smoke-source02.tar.gz').read_bytes()).hexdigest()=='83d7b1849f6e15d163d7d6cf0a2f6592d0491db2f229d4090610e4ebca0620e9'
s=json.loads(Path('installation02/supervisor.json').read_text());assert s['preparation_complete'] and s['group_drained']
p=Path('installation02/work');r=json.loads((p/'preparation.json').read_text());assert r['status']=='complete'
assert hashlib.sha256((p/'runtime-identity.json').read_bytes()).hexdigest()==r['runtime_identity_sha256']
i=json.loads((p/'runtime-identity.json').read_text());assert sys.prefix==i['prefix']
assert all(hashlib.sha256(Path(path).read_bytes()).hexdigest()==digest for path,digest in i['native_modules'].items())
print('prepared runtime identity admitted')
PY
mkdir smoke-source02
tar -xzf smoke-source02.tar.gz -C smoke-source02
nohup taskset -c 0-3 installation02/work/env/bin/python smoke-source02/STUDIES/independent_sv_reference_preflight_v1/unified-readiness/supervise_smoke.py --bundle /home/ubuntu/lanes/unified-readiness-20261027/smoke-source02 --preparation /home/ubuntu/lanes/unified-readiness-20261027/installation02/work --root /home/ubuntu/lanes/unified-readiness-20261027/smoke02 > smoke-launcher02.log 2>&1 </dev/null &
echo $! > smoke-supervisor02.pid
cat smoke-supervisor02.pid
date -u +%FT%TZ
