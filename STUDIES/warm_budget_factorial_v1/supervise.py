import json,sys
from pathlib import Path
from resource_monitor import execute
base=Path(__file__).resolve().parent
result=execute([sys.executable,str(base/'campaign.py')],str(base),10000,str(base),22*1024**3,6*1024**3,str(base/'campaign.log'),ownership_env='OWALNUTS_E72_OUTER_TOKEN',output_scan_interval=5,utilization_path=str(base/'outer-utilization.jsonl'),phase_reserved_cores={'startup':16})
with (base/'SUPERVISION.json').open('x') as f:json.dump(result,f,indent=2)
print(json.dumps(result))
