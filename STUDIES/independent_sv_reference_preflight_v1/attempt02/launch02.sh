#!/bin/bash
set -eu
cd /home/ubuntu/lanes/independent-reference-preflight-20261027
mkdir corrected
tar -xzf source02.tar.gz -C corrected
/home/ubuntu/venv/bin/python - <<'PY'
import pathlib,json,hashlib
assert hashlib.sha256(pathlib.Path('source02.tar.gz').read_bytes()).hexdigest()=='a56c5483b0069fdd740e7fa31a3e8609cea9d596a9646d3d6a97697784d2d4cc'
p=pathlib.Path('corrected/preflight');m=json.loads((p/'manifest.json').read_text());assert all(hashlib.sha256((p/k).read_bytes()).hexdigest()==v for k,v in m.items())
print('corrected bundle/source verified')
PY
nohup taskset -c 0-3 /home/ubuntu/venv/bin/python corrected/preflight/supervise.py --root /home/ubuntu/lanes/independent-reference-preflight-20261027/run02 --python /home/ubuntu/venv/bin/python --native-python /home/ubuntu/lanes/resident-predictive-build-20261027/env/bin/python --bridgestan-sdk /home/ubuntu/.bridgestan/bridgestan-2.9.0 > launcher02.log 2>&1 </dev/null &
echo $! > supervisor02.pid
cat supervisor02.pid
date -u +%FT%TZ
