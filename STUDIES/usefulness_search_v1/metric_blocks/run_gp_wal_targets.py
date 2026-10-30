import json,sys
from pathlib import Path
p=Path(__file__).resolve().parent;l=p/'local_recovery';r=l/'gp_wal_target_supervision01';r.mkdir(exist_ok=False);sys.path.insert(0,str(l/'inputs'))
from resource_monitor import execute
result=execute([sys.executable,str(p/'check_gp_wal_targets.py')],str(p),180,l/'gp_wal_target01',2*1024**3,64*1024**2,r/'worker.log',output_scan_interval=2)
(r/'SUMMARY.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
