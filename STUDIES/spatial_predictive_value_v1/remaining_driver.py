import sys,json
from pathlib import Path
sys.path.insert(0,'/home/ubuntu/lanes/spatial-predictive-value-20261101')
from resource_monitor import execute
ROOT=Path(__file__).resolve().parent
if __name__=='__main__':
    result=execute(['/home/ubuntu/venv/bin/python',str(ROOT/'remaining_worker.py'),sys.argv[1]],ROOT,900,ROOT,2*1024**3,32*1024**2,ROOT/'worker.log',output_scan_interval=2.)
    (ROOT/'SUPERVISION.json').write_text(json.dumps(result,indent=2))
