import hashlib,json,os,shutil,subprocess,sys,time
from pathlib import Path
p=Path(__file__).resolve().parent;s=p.parents[1]/'STUDIES/options_flow_v1';c=json.loads((p/'config.json').read_text());out=p/'run-v1';out.mkdir(exist_ok=False)
sha=lambda f:hashlib.sha256(Path(f).read_bytes()).hexdigest()
identity=sha(p/'config.json')
def verify():
 assert sha(p/'config.json')==identity
 for f,h in c['bindings'].items():assert sha(f)==h,f
records=[];started=time.perf_counter()
env=dict(os.environ,PYTHONPATH=str(s),JAX_PLATFORMS='cpu',XLA_FLAGS='--xla_force_host_platform_device_count=4',OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1',NUMEXPR_NUM_THREADS='1')
for pair,seed in enumerate([4101,4201]):
 verify();assert shutil.disk_usage(p).free>=12*1024**3
 name=f'pair{pair}-parallel-reference'
 inner=[sys.executable,str(p/'guard.py'),'--fixture',c['fixture'],'--out',str(out/name),'--seed',str(seed),'--warmup','1000','--chains','4','--tiers','1000','2000','4000','8000','--batch','1000','--target-accept','.9','--implementation','associative','--chain-method','parallel']
 cmd=[sys.executable,str(s/'hardware_control.py'),'--cpus','0,1,2,3','--record',str(out/(name+'-hardware.json')),'--timeout','1800','--',*inner]
 r=dict(pair=pair,seed=seed,status='running',command=cmd);records.append(r);(out/'execution.json').write_text(json.dumps(dict(status='running',records=records),indent=2));t=time.perf_counter()
 with (out/(name+'.log')).open('w') as f:proc=subprocess.run(cmd,env=env,stdout=f,stderr=subprocess.STDOUT)
 r.update(status='terminal',returncode=proc.returncode,outer_seconds=time.perf_counter()-t);verify()
(out/'execution.json').write_text(json.dumps(dict(status='terminal',records=records,outer_seconds=time.perf_counter()-started,config_sha256=identity),indent=2))
