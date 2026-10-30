import json,sys
from pathlib import Path
base=Path(__file__).resolve().parent;sys.path.insert(0,str(base.parent/'metric_blocks/local_recovery/inputs'))
from resource_monitor import execute
out=base/'proposal_preflight_supervision01';out.mkdir(exist_ok=False)
s=execute([sys.executable,str(base/'check_proposal.py')],str(base),180,base/'proposal_preflight01',3*1024**3,32*1024**2,out/'worker.log',output_scan_interval=2)
(out/'SUPERVISION.json').write_text(json.dumps(s,indent=2)+'\n');print(json.dumps(s))
