import hashlib,json,sys
from pathlib import Path
root=Path(__file__).resolve().parent
inputs={str(root/n):hashlib.sha256((root/n).read_bytes()).hexdigest() for n in ['replay_v2.py','move.py','REPLAY-V2-PROTOCOL.md','run_replay_v2.py']}
(root/'REPLAY-V2-INPUTS.json').write_text(json.dumps(inputs,indent=2)+'\n')
sys.path.insert(0,'/home/ubuntu/lanes/pharma-ode-logforecast-20261029/source');from resource_monitor import execute
results=[]
for arm in ['local','ensemble']:
 folder=root/('replay-v2-'+arm+'-supervision');folder.mkdir(exist_ok=False)
 r=execute([sys.executable,str(root/'replay_v2.py'),arm],str(root),600,folder,2*1024**3,64*1024**2,folder/'worker.log',output_scan_interval=2)
 (folder/'SUPERVISION.json').write_text(json.dumps(r,indent=2)+'\n');results.append(dict(arm=arm,**r))
(root/'REPLAY-V2-FINAL.json').write_text(json.dumps(dict(jobs=results,unchanged=all(hashlib.sha256(Path(p).read_bytes()).hexdigest()==h for p,h in inputs.items())),indent=2)+'\n')
