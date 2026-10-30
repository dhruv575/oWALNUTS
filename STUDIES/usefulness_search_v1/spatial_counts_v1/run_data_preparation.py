import json,sys
from pathlib import Path
base=Path(__file__).resolve().parent;sys.path.insert(0,str(base.parent/'metric_blocks/local_recovery/inputs'))
from resource_monitor import execute
out=base/'data_supervision01';out.mkdir(exist_ok=False)
s=execute([sys.executable,str(base/'prepare_data.py')],str(base),120,base/'data01',2*1024**3,16*1024**2,out/'worker.log',output_scan_interval=2);(out/'SUPERVISION.json').write_text(json.dumps(s,indent=2)+'\n');print(json.dumps(s))
