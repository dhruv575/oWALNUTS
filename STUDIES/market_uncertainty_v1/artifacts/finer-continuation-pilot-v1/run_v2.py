"""Unlaunched development pilot; no sampler/source changes."""
from pathlib import Path
import argparse,hashlib,json,os,shutil,subprocess,sys,time
ROOT=Path(__file__).resolve().parents[2];STUDY=ROOT/'STUDIES/options_flow_v1';HERE=Path(__file__).resolve().parent
TIERS=[1000,2000,2500,3000,4000]
def command(arm,seed,out,fixture):
 common=['--fixture',str(fixture),'--out',str(out),'--seed',str(seed),'--warmup','1000','--chains','4','--tiers',*map(str,TIERS)]
 if arm=='public':return [sys.executable,str(STUDY/'pymc_flow_continuation_workflow.py'),*common,'--threads','4','--model','flow','--block-size','32','--coordinates','mixed_slopes','--expected-cpus','0,1,2,3']
 if arm=='reference':return [sys.executable,str(STUDY/'mixed_flow_reference.py'),*common,'--batch','500','--target-accept','.9','--implementation','associative','--chain-method','parallel']
 raise ValueError('Unknown arm')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
 parser=argparse.ArgumentParser();parser.add_argument('--config',type=Path,required=True);parser.add_argument('--out',type=Path,required=True);a=parser.parse_args()
 c=json.loads(a.config.read_text());configsha=sha(a.config)
 def verify():
  assert sha(a.config)==configsha
  for f,h in c['bindings'].items():assert sha(f)==h,f
 verify();a.out.mkdir(exist_ok=False);records=[];started=time.perf_counter()
 env=dict(os.environ,PYTHONPATH=c['package']+os.pathsep+str(STUDY),JAX_PLATFORMS='cpu',XLA_FLAGS='--xla_force_host_platform_device_count=4',OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1',NUMEXPR_NUM_THREADS='1')
 for pair,seed,arm in [(0,4101,'public'),(0,4101,'reference'),(1,4201,'reference'),(1,4201,'public')]:
  name=f'pair{pair}-{arm}';record=dict(pair=pair,seed=seed,arm=arm,status='unstarted');records.append(record)
  try:
   verify()
   if shutil.disk_usage(a.out).free<12*1024**3:raise RuntimeError('12GiB free-space floor')
   inner=command(arm,seed,a.out/name,c['fixture']);inner=[sys.executable,str(HERE/'guard_v2.py'),'--config',str(a.config),'--arm',arm,'--',*inner[1:]]
   cmd=[sys.executable,str(STUDY/'hardware_control.py'),'--cpus','0,1,2,3','--record',str(a.out/(name+'-hardware.json')),'--timeout','1800','--',*inner]
   record.update(command=cmd,status='running');tick=time.perf_counter()
   with (a.out/(name+'.log')).open('w') as log:proc=subprocess.run(cmd,env=env,stdout=log,stderr=subprocess.STDOUT)
   record.update(status='terminal',returncode=proc.returncode,outer_seconds=time.perf_counter()-tick);verify()
  except Exception as exc:record['error']=str(exc)
  (a.out/'execution.json').write_text(json.dumps(dict(records=records,outer_seconds=time.perf_counter()-started),indent=2))
if __name__=='__main__':main()

