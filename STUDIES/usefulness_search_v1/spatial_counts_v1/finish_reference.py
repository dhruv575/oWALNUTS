"""Finite terminal watcher; performs no sampler retries."""
import hashlib
import json
import os
import sys
import time
from pathlib import Path
from resource_monitor import execute
base=Path(__file__).resolve().parent
repair=Path('/home/ubuntu/lanes/spatial-counts-reference-20261031-v2')
deadline=json.loads((repair/'LAUNCH.json').read_text())['launched']+2700
os.environ['XDG_CACHE_HOME']=str(base/'cache')
hashes={str(base/n):hashlib.sha256((base/n).read_bytes()).hexdigest() for n in
        ['finish_reference.py','audit_spatial_reference.py','resource_monitor.py','REFERENCE-AUDIT-PROTOCOL.md']}
(base/'INPUT-HASHES.json').write_text(json.dumps(hashes,indent=2))
with (base/'WATCHER.jsonl').open('x') as log:
    while time.time()<deadline:
        status=json.loads((repair/'STATUS.json').read_text())
        log.write(json.dumps(dict(unix_seconds=time.time(),reference_status=status['status']))+'\n');log.flush()
        if status['status']!='running':break
        time.sleep(30)
    else:
        (base/'STATUS.json').write_text(json.dumps(dict(status='watch_deadline',audit_passed=False)))
        raise SystemExit(1)
s=execute([sys.executable,str(base/'audit_spatial_reference.py')],str(base),600,base,
          4*1024**3,16*1024**2,base/'audit.log',output_scan_interval=2)
(base/'SUPERVISION.json').write_text(json.dumps(s,indent=2)+'\n')
intact=all(hashlib.sha256(Path(n).read_bytes()).hexdigest()==h for n,h in hashes.items())
ok=s['status']=='exited' and s['exit_code']==0 and s['group_drained'] and intact
(base/'STATUS.json').write_text(json.dumps(dict(status='completed' if ok else 'failed',source_hashes_intact=intact,
    audit_passed=ok,finished=time.time()),indent=2)+'\n')
if not ok:(base/'RESULT.md').write_text('# Spatial reference audit incomplete\n\nRead SUPERVISION.json and audit.log; no reference qualification accepted.\n')
