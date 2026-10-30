import json,sys
from pathlib import Path
p=Path(__file__).resolve().parent;l=p/'local_recovery';sys.path.insert(0,str(l/'inputs'))
from resource_monitor import execute
r=l/'gp_intensity_coverage_supervision01';r.mkdir(exist_ok=False)
result=execute([sys.executable,str(p/'audit_gp_intensity_coverage.py')],str(p),300,l/'gp_intensity_coverage01',2*1024**3,64*1024**2,r/'worker.log',output_scan_interval=2)
(r/'SUMMARY.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
