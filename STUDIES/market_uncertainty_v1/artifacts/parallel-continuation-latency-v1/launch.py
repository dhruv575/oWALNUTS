import hashlib,json,os,subprocess,sys,time,zipfile,shutil
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1];STUDY=ROOT/'STUDIES/options_flow_v1'
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(p,v):p.write_text(json.dumps(v,indent=2))
def main():
 cfg=json.loads((HERE/'config.json').read_text());identity=sha(HERE/'config.json')
 def verify():
  assert sha(HERE/'config.json')==identity
  for p,h in cfg['bindings'].items():assert sha(p)==h,p
 verify();out=HERE/'run-v1';out.mkdir(exist_ok=False)
 env=dict(os.environ,PYTHONPATH=cfg['package']+os.pathsep+str(STUDY),OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1',NUMEXPR_NUM_THREADS='1')
 records=[];start=time.perf_counter()
 for pair,seed,threads in [(0,4101,1),(0,4101,4),(1,4201,4),(1,4201,1)]:
  verify();assert shutil.disk_usage(HERE).free>=12*1024**3, 'Disk floor';name=f'pair{pair}-threads{threads}';dest=out/name
  command=[sys.executable,str(HERE/'runtime_guard.py'),'--fixture',cfg['fixture'],'--out',str(dest),'--seed',str(seed),'--warmup','1000','--chains','4','--tiers','1000','2000','4000','8000','--threads',str(threads),'--model','flow','--block-size','32','--coordinates','mixed_slopes','--expected-cpus','0,1,2,3']
  wrapped=[sys.executable,str(STUDY/'hardware_control.py'),'--cpus','0,1,2,3','--record',str(out/(name+'-hardware.json')),'--timeout','1800','--',*command]
  tick=time.perf_counter();record=dict(pair=pair,seed=seed,threads=threads,command=wrapped,status='running');records.append(record);write(out/'execution.json',dict(records=records,status='running'))
  with (out/(name+'.log')).open('w') as log:r=subprocess.run(wrapped,env=env,stdout=log,stderr=subprocess.STDOUT)
  record.update(returncode=r.returncode,outer_seconds=time.perf_counter()-tick,status='terminal');verify();write(out/'execution.json',dict(records=records,status='running'))
 write(out/'execution.json',dict(records=records,status='terminal',outer_seconds=time.perf_counter()-start,config_sha256=identity))
if __name__=='__main__':main()

