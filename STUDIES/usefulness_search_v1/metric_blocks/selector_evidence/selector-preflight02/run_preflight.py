import hashlib
import json
import shutil
import sys
from pathlib import Path

root = Path(__file__).resolve().parent
out = root/'monitor'
out.mkdir(exist_ok=False)
paths = [root/p for p in ['selector.py', 'preflight.py', 'SELECTOR-PREFLIGHT.md', 'RAW.json', 'run_preflight.py']]
before = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
sys.path.insert(0, '/home/ubuntu/lanes/pharma-ode-logforecast-20261029/source')
from resource_monitor import execute
result = execute([sys.executable, str(root/'preflight.py')], str(root), 180,
                 out, 2*1024**3, 64*1024**2, out/'worker.log', output_scan_interval=2)
result['inputs'] = before
result['unchanged'] = all(hashlib.sha256(Path(p).read_bytes()).hexdigest() == h for p, h in before.items())
(root/'SUPERVISION.json').write_text(json.dumps(result, indent=2)+'\n')
durable = Path('/home/ubuntu/lanes/metric-blocks-recovery-20261030/evidence/selector-preflight02')
shutil.copytree(root, durable)
print(json.dumps(result))

