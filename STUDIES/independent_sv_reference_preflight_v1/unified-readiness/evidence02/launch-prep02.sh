#!/bin/bash
set -eu
cd /home/ubuntu/lanes/unified-readiness-20261027
/home/ubuntu/venv/bin/python - <<'PY'
from pathlib import Path
import hashlib
assert hashlib.sha256(Path('prep-source02.tar.gz').read_bytes()).hexdigest()=='e99c0c1a48e78665a52091863e932b87e0f340db4c86116aa6d932900b60630d'
PY
mkdir corrected-prep
tar -xzf prep-source02.tar.gz -C corrected-prep
nohup taskset -c 0-3 /home/ubuntu/venv/bin/python corrected-prep/prep/supervise_prepare.py --root /home/ubuntu/lanes/unified-readiness-20261027/installation02 --monitor /home/ubuntu/lanes/unified-readiness-20261027/corrected-prep/prep/bootstrap_monitor.py --monitor-sha256 4988f09972f4898609b0bf2d0b12811021cdd71ad9808b9ca7b4759ed0c9f326 --requirements /home/ubuntu/lanes/unified-readiness-20261027/corrected-prep/deps/requirements-unified.txt --requirements-sha256 c1f678edadeeb3ab612006660a9bd384631ab48c507e456fe747e3d723abb534 > prep-launcher02.log 2>&1 </dev/null &
echo $! > prep-supervisor02.pid
cat prep-supervisor02.pid
date -u +%FT%TZ
