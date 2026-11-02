import sys,json,hashlib
from pathlib import Path
from resource_monitor import execute
BASE=Path(__file__).resolve().parent
if __name__=='__main__':
    stage=sys.argv[1];supervision=BASE/(stage+'-supervision');supervision.mkdir(exist_ok=False)
    result=execute(['/home/ubuntu/venv/bin/python',str(BASE/(stage+'_worker.py'))],BASE,900,BASE,2*1024**3,64*1024**2,supervision/'worker.log',output_scan_interval=2.)
    (supervision/'SUPERVISION.json').write_text(json.dumps(result,indent=2))
