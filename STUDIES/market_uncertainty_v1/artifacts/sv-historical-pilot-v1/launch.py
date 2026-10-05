import hashlib,json,os,shutil,subprocess,sys,time
from pathlib import Path
P=Path(__file__).resolve().parent;R=P.parents[1];S=R/'STUDIES/market_uncertainty_v1/sv_prototype'
def launch(config_path,out):
 config_path=Path(config_path);out=Path(out);config=json.loads(config_path.read_text());identity=hashlib.sha256(config_path.read_bytes()).hexdigest()
 if config.get('status')!='frozen_awaiting_root_launch_authorization':raise ValueError('Only reviewed frozen config can run')
 def verify():
  assert hashlib.sha256(config_path.read_bytes()).hexdigest()==identity
  for f,h in config['bindings'].items():assert hashlib.sha256(Path(f).read_bytes()).hexdigest()==h,f
 verify();out.mkdir(exist_ok=False);records=[dict(**cell,status='unstarted',outer_seconds=0.) for cell in config['cells']];start=time.perf_counter();abort=None
 env=dict(os.environ,PYTHONPATH=config['package'],JAX_PLATFORMS='cpu',XLA_FLAGS='--xla_force_host_platform_device_count=4',OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1',NUMEXPR_NUM_THREADS='1')
 for rec in records:
  if abort:rec['reason']=abort;continue
  tick=time.perf_counter()
  try:
   verify();remaining=21600-(time.perf_counter()-start)
   if remaining<1815:raise RuntimeError('Global budget insufficient for complete next capped fit')
   if shutil.disk_usage(out).free<12*1024**3:raise RuntimeError('Disk free-space admission failed')
   cmd=[sys.executable,str(R/'STUDIES/options_flow_v1/hardware_control.py'),'--cpus','0,1,2,3','--record',str(out/(rec['id']+'-hardware.json')),'--timeout','1800','--',sys.executable,str(S/'workflow.py'),'--fixture',rec['fixture'],'--config',str(config_path),'--arm',rec['arm'],'--seed',str(rec['seed']),'--out',str(out/rec['id'])]
   rec.update(status='running',command=cmd);(out/'execution.json').write_text(json.dumps(dict(records=records,status='running'),indent=2))
   with (out/(rec['id']+'.log')).open('w') as log:proc=subprocess.run(cmd,env=env,stdout=log,stderr=subprocess.STDOUT)
   rec.update(status='terminal',returncode=proc.returncode);verify()
   hw=json.loads((out/(rec['id']+'-hardware.json')).read_text())
   if hw.get('job_active_processes_after_cleanup')!=0 or hw.get('realized_cpus')!=[0,1,2,3] or hw.get('enforced_before_worker_launch') is not True or hw.get('containment',{}).get('assigned_before_worker_execution') is not True or hw.get('returncode')!=proc.returncode:raise RuntimeError('Worker containment/affinity evidence invalid')
  except Exception as exc:abort=repr(exc);rec['error']=abort
  finally:rec['outer_seconds']=time.perf_counter()-tick
 (out/'execution.json').write_text(json.dumps(dict(status='terminal',records=records,outer_seconds=time.perf_counter()-start,admission_abort=abort,config_sha256=identity),indent=2))
if __name__=='__main__':launch(sys.argv[1],sys.argv[2])
