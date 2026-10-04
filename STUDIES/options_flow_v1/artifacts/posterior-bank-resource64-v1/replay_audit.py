"""Read-only replay of frozen computational-resource evidence; no worker launch."""
from pathlib import Path
import hashlib,json,zipfile
r=Path(__file__).resolve().parent
load=lambda n:json.loads((r/n).read_text())
sha=lambda b:hashlib.sha256(b).hexdigest()
c=load('config.json');result=load('result.json');h=load('hardware.json')
assert sha((r/'config.json').read_bytes())==result['config_sha256']
assert result['parameter_batch_calls']==40 and result['full_30000_bootstrap_rows_produced']==30000
assert result['resources']['peak_committed_bytes']<=c['memory_bytes']
assert h['status']=='completed' and h['returncode']==0 and h['job_active_processes_after_cleanup']==0 and h['realized_cpus']==[0]
with zipfile.ZipFile(r/'executed-sources.zip') as z:
 for name,digest in c['bindings'].items():
  if Path(name).suffix=='.py':assert sha(z.read(Path(name).name))==digest
 assert z.read('config.json')==(r/'config.json').read_bytes()
print(json.dumps(dict(status='passed',scope='Archived computational resource checks; original input compact hashes are in config, not reproduced as independent draws',qualified=False)))
