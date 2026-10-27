#!/bin/bash
set -eu
cd /home/ubuntu/lanes/unified-readiness-20261027
/home/ubuntu/venv/bin/python - <<'PY'
from pathlib import Path
import hashlib
assert hashlib.sha256(Path('prep-source.tar.gz').read_bytes()).hexdigest()=='3e0b20567ccc2c4a07e27ca3b262a162914d9366d676e9d9823dc9b6cfd38ef1'
PY
tar -xzf prep-source.tar.gz
nohup taskset -c 0-3 /home/ubuntu/venv/bin/python prep/supervise_prepare.py --root /home/ubuntu/lanes/unified-readiness-20261027/installation --monitor /home/ubuntu/lanes/unified-readiness-20261027/deps/resource_monitor.py --monitor-sha256 9550b2650db2aa467a1b5317b4cab19714359301a560392cb3536b17cf9fc622 --requirements /home/ubuntu/lanes/unified-readiness-20261027/deps/requirements-unified.txt --requirements-sha256 c1f678edadeeb3ab612006660a9bd384631ab48c507e456fe747e3d723abb534 > prep-launcher.log 2>&1 </dev/null &
echo $! > prep-supervisor.pid
cat prep-supervisor.pid
date -u +%FT%TZ
