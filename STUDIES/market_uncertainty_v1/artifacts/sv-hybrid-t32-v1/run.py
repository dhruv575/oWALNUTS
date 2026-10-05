import hashlib,json,os,subprocess,sys,time
from pathlib import Path
R=Path(__file__).resolve().parents[2];S=R/'STUDIES/market_uncertainty_v1/sv_prototype';H=R/'STUDIES/market_uncertainty_v1/sv_hybrid';D=Path(__file__).resolve().parent
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(p,v):
 def clean(v):
  if isinstance(v,dict):return {k:clean(x) for k,x in v.items()}
  if isinstance(v,(list,tuple)):return [clean(x) for x in v]
  if hasattr(v,'tolist'):return clean(v.tolist())
  if isinstance(v,float) and not __import__('math').isfinite(v):return None
  return v
 with Path(p).open('w') as f:json.dump(clean(v),f,indent=2,allow_nan=False)
def verify(plan):
 for p,h in plan['bindings'].items():
  if sha(p)!=h:raise ValueError('Binding drift '+p)
def worker(arm):
 start=time.perf_counter();plan=json.loads((D/'plan.json').read_text());verify(plan)
 sys.path.insert(0,str(S));sys.path.insert(1,str(H));sys.path.insert(2,str(R/'STUDIES/options_flow_v1'))
 import numpy as np
 from target import Target,Priors
 from reporting import summarize
 f=json.loads((D/'fixture.json').read_text());m=Target(**f['data'],priors=Priors(**f['priors']))
 result=dict(arm=arm,status='running',qualified=False,completed_sweeps=[],precision_pass=False);out=D/arm;out.mkdir(exist_ok=False);budget=None
 try:
  if arm=='hybrid':
   from hybrid import sweep,EvaluationBudget
   budget=EvaluationBudget(2000000);chains=[]
   for chain,q0 in enumerate(f['starts']):
    rng=np.random.default_rng(np.random.SeedSequence(991804,spawn_key=(chain,)));q=np.array(q0);draws=[];result['completed_sweeps'].append(0)
    for iteration in range(3000):
     q,_=sweep(m,q,rng,budget=budget);result['completed_sweeps'][chain]=iteration+1
     if iteration>=1000:draws.append(q.copy())
     if iteration%100==0:
      result.update(density_calls=budget.calls,elapsed_seconds=time.perf_counter()-start);write(out/'report.json',result)
    chains.append(draws);np.save(out/f'chain-{chain}.npy',np.array(draws))
   q=np.asarray(chains);result['density_calls']=budget.calls
  else:
   import jax,jaxlib,numpyro
   from reference import make_reference
   from reference_continuation import ContinuedReference
   from workflow import transform,verify_parity
   actual={str(Path(x.__file__).resolve()):sha(x.__file__) for x in (jax,jaxlib,numpyro)}
   if any(plan['bindings'].get(p)!=h for p,h in actual.items()):raise ValueError('Reference runtime differs')
   mean,sd,jac=transform(m);density,_=make_reference(m);white=lambda u:density(mean+sd*u)+jac
   starts,parity=verify_parity(m,f['starts'],jax.jit(jax.value_and_grad(white)));result['parity']=parity
   engine=ContinuedReference(lambda u:-white(u),starts,991805,1000,2000,.9,chain_method='parallel');engine.adapt();engine.append();q=mean+sd*engine.samples
   result.update(divergences=engine.divergences,checkpoints=engine.checkpoints)
  np.save(out/'draws.npy',q);evaluation=summarize(q,m,f['future'],predictive_seed=991806)
  evaluation['precision_pass'] &= result.get('divergences',0)==0
  result.update(status='completed',evaluation=evaluation,precision_pass=evaluation['precision_pass'])
 except Exception as e:result.update(status='failed',error=repr(e))
 finally:
  if budget:result.update(density_calls=budget.calls,budget_exhausted=budget.exhausted)
  try:verify(plan)
  except Exception as e:result.update(status='failed',precision_pass=False,integrity_error=repr(e))
  result['elapsed_seconds']=time.perf_counter()-start;write(out/'report.json',result)
 return 0 if result['status']=='completed' else 1

def prepare():
 if (D/'plan.json').exists():raise FileExistsError('No regeneration')
 # Persist role intent before numerical fixture generation.
 intent=dict(seeds=dict(fixture=991801,mask=991802,starts=991803,hybrid=991804,reference=991805,predictive=991806),T=32,arms=['hybrid','reference'],warmup=1000,retained=2000,timeout=300,hybrid_density_cap=2000000,qualified=False)
 write(D/'intent.json',intent)
 sys.path.insert(0,str(S));import numpy as np
 from synthetic import simulate,ILLUSTRATIVE_PRIORS,covariates
 from target import Target
 from workflow import transform
 mask=np.random.default_rng(991802).uniform(size=32)>=.1;f=simulate(32,991801,'both',priors=ILLUSTRATIVE_PRIORS,observed=mask)
 m=Target(**f['data'],priors=ILLUSTRATIVE_PRIORS);mean,sd,_=transform(m);f['starts']=mean+.25*sd*np.random.default_rng(991803).normal(size=(4,m.dimension))
 # Missing outcomes serialized null; Target casts null toNaN and sanitizes mask.
 x,w=covariates(33,'both');f['future']=dict(x=x[-1],w=w[-1]);write(D/'fixture.json',f)
 import importlib.util
 files=[Path(__file__),D/'intent.json',D/'fixture.json',Path(sys.executable),*S.glob('*.py'),*H.glob('*.py'),* (R/'STUDIES/options_flow_v1').glob('*.py')]
 for name in ('jax','jaxlib','numpyro'):
  root=Path(importlib.util.find_spec(name).origin).parent;files.extend(root.rglob('*.py'));files.extend(root.rglob('*.pyd'))
 write(D/'plan.json',dict(intent=intent,bindings={str(p.resolve()):sha(p) for p in files}))

def launch():
 plan=json.loads((D/'plan.json').read_text());verify(plan);records=[];env=dict(os.environ,JAX_PLATFORMS='cpu',XLA_FLAGS='--xla_force_host_platform_device_count=4',OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1')
 for arm in plan['intent']['arms']:
  t=time.perf_counter();cmd=[sys.executable,str(R/'STUDIES/options_flow_v1/hardware_control.py'),'--cpus','0,1,2,3','--record',str(D/(arm+'-hardware.json')),'--timeout','300','--',sys.executable,str(Path(__file__)),'worker',arm]
  with (D/(arm+'.log')).open('x') as log:p=subprocess.run(cmd,env=env,stdout=log,stderr=subprocess.STDOUT)
  records.append(dict(arm=arm,returncode=p.returncode,outer_seconds=time.perf_counter()-t,command=cmd));write(D/'execution.json',records);verify(plan)
if __name__=='__main__':
 if sys.argv[1]=='prepare':prepare()
 elif sys.argv[1]=='worker':raise SystemExit(worker(sys.argv[2]))
 elif sys.argv[1]=='launch':launch()
