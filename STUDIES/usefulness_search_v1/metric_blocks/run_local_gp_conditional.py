import json,sys
from pathlib import Path
p=Path(__file__).resolve().parent;l=p/'local_recovery';sys.path.insert(0,str(l/'inputs'))
from resource_monitor import execute
out=l/'gp_conditional_local_supervision01';out.mkdir(exist_ok=False);r=l/'gp_conditional_local01'
result=execute([sys.executable,str(r/'prepare_conditional_v3.py')],str(r),180,r,2*1024**3,64*1024**2,out/'worker.log',output_scan_interval=2)
(out/'SUMMARY.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
