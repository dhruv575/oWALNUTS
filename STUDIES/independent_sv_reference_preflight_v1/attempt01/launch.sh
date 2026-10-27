#!/bin/bash
set -eu
cd /home/ubuntu/lanes/independent-reference-preflight-20261027
/home/ubuntu/venv/bin/python - <<'PY'
import pathlib,json,hashlib,sys
p=pathlib.Path('preflight');m=json.loads((p/'manifest.json').read_text())
assert all(hashlib.sha256((p/k).read_bytes()).hexdigest()==v for k,v in m.items())
assert sys.prefix=='/home/ubuntu/venv'
print('source and shared prefix verified')
PY
nohup taskset -c 0-3 /home/ubuntu/venv/bin/python preflight/supervise.py --root /home/ubuntu/lanes/independent-reference-preflight-20261027/run01 --python /home/ubuntu/venv/bin/python --native-python /home/ubuntu/lanes/resident-predictive-build-20261027/env/bin/python --bridgestan-sdk /home/ubuntu/.bridgestan/bridgestan-2.9.0 > launcher.log 2>&1 </dev/null &
echo $! > supervisor.pid
cat supervisor.pid
date -u +%FT%TZ
