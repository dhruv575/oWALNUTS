import sys,json,os
from pathlib import Path
sys.path.insert(0,"/home/ubuntu/lanes/funnel-application-20261101")
from resource_monitor import execute
p=Path(__file__).resolve().parent
rows=[]
for seed in range(956500021,956500029):
 out=p/str(seed);out.mkdir()
 r=execute(["/home/ubuntu/venv/bin/python",str(p/"budget_worker.py"),"mixed","nuts","noncentered",".999",str(seed),"budget_4000",str(out/"artifact")],p,900,p,2*1024**3,64*1024**2,out/"worker.log",output_scan_interval=2.)
 (out/"SUPERVISION.json").write_text(json.dumps(r,indent=2))
 rows.append(json.loads((out/"artifact/SUMMARY.json").read_text()) if r["exit_code"]==0 else r)
(p/"STATUS.json").write_text(json.dumps(dict(status="completed",results=rows),indent=2))
