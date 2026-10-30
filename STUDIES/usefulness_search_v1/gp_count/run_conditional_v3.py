import concurrent.futures,hashlib,json,shutil,sys,time
from pathlib import Path
import psutil
root=Path(__file__).resolve().parent;out=root/'conditional03';out.mkdir(exist_ok=False)
assert shutil.disk_usage('/').free>=1024**3 and shutil.disk_usage('/dev/shm').free>=2*1024**3 and psutil.virtual_memory().available>=10*1024**3
sys.path.insert(0,'/home/ubuntu/lanes/pharma-ode-logforecast-20261029/source');from resource_monitor import execute
from common import MODELS,NAME
paths=[root/n for n in ['CONDITIONAL-PROTOCOL.md','common.py','conditional_v3.py','prepare_conditional_v3.py','sample_conditional_v3.py','run_conditional_v3.py','REFERENCE.json']]+[MODELS/(NAME+s) for s in ['_model.so','.data.json','.stan']]
inputs={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths};(out/'INPUTS.json').write_text(json.dumps(inputs,indent=2)+'\n')
folder=out/'preparation';folder.mkdir();r=execute([sys.executable,str(root/'prepare_conditional_v3.py')],str(root),180,folder,2*1024**3,64*1024**2,folder/'worker.log',output_scan_interval=2);(folder/'SUPERVISION.json').write_text(json.dumps(r,indent=2)+'\n');assert r['exit_code']==0 and r['group_drained']
inputs[str(root/'conditional-grid.npz')]=hashlib.sha256((root/'conditional-grid.npz').read_bytes()).hexdigest();(out/'SAMPLING-INPUTS.json').write_text(json.dumps(inputs,indent=2)+'\n')
def run(seed):
 p=out/str(seed);p.mkdir();r=execute([sys.executable,str(root/'sample_conditional_v3.py'),str(seed),str(p)],str(root),600,p,2*1024**3,64*1024**2,p/'worker.log',output_scan_interval=2);(p/'SUPERVISION.json').write_text(json.dumps(r,indent=2)+'\n');return dict(seed=seed,**r)
t=time.monotonic()
with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:results=list(pool.map(run,range(944100001,944100005)))
(out/'FINAL.json').write_text(json.dumps(dict(results=results,seconds=time.monotonic()-t,unchanged=all(hashlib.sha256(Path(p).read_bytes()).hexdigest()==h for p,h in inputs.items())),indent=2)+'\n')
