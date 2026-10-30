import hashlib,json,shutil,sys,time
from pathlib import Path
root=Path('/dev/shm/ensemble-moves-20261030');out=root/'canonical';out.mkdir(exist_ok=False)
for name in ['move.py','validate.py','check_integration.py','PROTOCOL.md','DESIGN.md']:shutil.copy2(root/name,out/name)
inputs={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in out.iterdir()};(out/'INPUTS.json').write_text(json.dumps(inputs,indent=2)+'\n')
sys.path.insert(0,'/home/ubuntu/lanes/pharma-ode-logforecast-20261029/source');from resource_monitor import execute
results=[]
for name in ['validate','check_integration']:
 folder=out/(name+'-supervision');folder.mkdir();r=execute([sys.executable,str(out/(name+'.py'))],str(out),180,folder,2*1024**3,16*1024**2,folder/'worker.log',output_scan_interval=2);(folder/'SUPERVISION.json').write_text(json.dumps(r,indent=2)+'\n');results.append(dict(name=name,**r))
 if r['exit_code']!=0:break
(out/'FINAL.json').write_text(json.dumps(dict(jobs=results,unchanged=all(hashlib.sha256(Path(p).read_bytes()).hexdigest()==h for p,h in inputs.items())),indent=2)+'\n');print(json.dumps(results))
