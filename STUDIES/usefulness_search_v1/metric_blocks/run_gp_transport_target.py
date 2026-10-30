import json,sys,shutil
from pathlib import Path
p=Path(__file__).resolve().parent;l=p/'local_recovery';r=l/'gp_transport_target_supervision01';r.mkdir(exist_ok=False);sys.path.insert(0,str(l/'inputs'));from resource_monitor import execute
assert shutil.disk_usage(r).free>2*1024**3
result=execute([sys.executable,str(p/'build_gp_transport_target.py')],str(p),300,Path('/home/dhruv/.cache/owalnuts/gp-transport-target01'),4*1024**3,1024**3,r/'worker.log',output_scan_interval=2);(r/'SUPERVISION.json').write_text(json.dumps(result,indent=2));assert result['exit_code']==0 and result['group_drained'];print(json.dumps(result))
