import json,sys
from pathlib import Path
p=Path(__file__).resolve().parent;l=p/'local_recovery';r=l/'transport_gradient_audit_supervision01';r.mkdir(exist_ok=False);sys.path.insert(0,str(l/'inputs'));from resource_monitor import execute
result=execute([sys.executable,str(p/'audit_transport_gradients.py')],str(p),180,l/'transport_gradient_audit01',2*1024**3,64*1024**2,r/'worker.log',output_scan_interval=2);(r/'SUPERVISION.json').write_text(json.dumps(result,indent=2));assert result['exit_code']==0 and result['group_drained'];print(json.dumps(result))
