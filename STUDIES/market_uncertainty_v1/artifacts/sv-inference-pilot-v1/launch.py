import os,sys,json,time,subprocess,hashlib,shutil
from pathlib import Path
p=Path(__file__).resolve().parent;r=p.parents[1];c=json.loads((p/'config.json').read_text());out=p/'run-v1';out.mkdir(exist_ok=False)
def verify():
 for f,h in c['bindings'].items():assert hashlib.sha256(Path(f).read_bytes()).hexdigest()==h,f
records=[];start=time.perf_counter();env=dict(os.environ,PYTHONPATH=c['package'],XLA_FLAGS='--xla_force_host_platform_device_count=4',JAX_PLATFORMS='cpu',OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1')
for pair,seed,arm in [(0,6201,'public'),(0,6201,'reference'),(1,6301,'reference'),(1,6301,'public')]:
 verify();assert shutil.disk_usage(p).free>=12*1024**3
 name=f'pair{pair}-{arm}';cmd=[sys.executable,str(r/'STUDIES/options_flow_v1/hardware_control.py'),'--cpus','0,1,2,3','--record',str(out/(name+'-hardware.json')),'--timeout','1800','--',sys.executable,str(p/'worker.py'),'--arm',arm,'--seed',str(seed),'--out',str(out/name)]
 rec=dict(pair=pair,seed=seed,arm=arm,status='running',command=cmd);records.append(rec);(out/'execution.json').write_text(json.dumps(dict(records=records),indent=2));t=time.perf_counter()
 with (out/(name+'.log')).open('w') as log:process=subprocess.run(cmd,env=env,stdout=log,stderr=subprocess.STDOUT)
 rec.update(status='terminal',returncode=process.returncode,outer_seconds=time.perf_counter()-t);verify()
(out/'execution.json').write_text(json.dumps(dict(status='terminal',records=records,outer_seconds=time.perf_counter()-start),indent=2))
