"""Reusable SV workflow: per-fit NumPy oracle, no JAX in the public process."""
import argparse,hashlib,json,sys,time,traceback,importlib.util
from contextlib import contextmanager
from pathlib import Path
PROCESS_START=time.perf_counter()
import numpy as np
from target import Target,Priors


def transform(model):
 p=model.priors;mean=np.r_[p.mu_mean,p.log_sigma_mean,np.zeros(model.dimension-2)];sd=np.r_[p.mu_sd,p.log_sigma_sd,np.full(model.p,p.beta_sd),np.full(model.k,p.gamma_sd),np.ones(model.t)]
 return mean,sd,float(np.log(sd).sum())

def verify_parity(model,physical_starts,evaluate):
 mean,sd,jac=transform(model);starts=(np.asarray(physical_starts,dtype=float)-mean)/sd
 if starts.shape!=(4,model.dimension) or not np.isfinite(starts).all():raise ValueError('Four finite physical starts required')
 points=[]
 for q,u in zip(physical_starts,starts):
  expected,g=model.value_gradient(q);expected+=jac;g=g*sd;v,actual=evaluate(u)
  if not np.isfinite(expected) or not np.isfinite(g).all() or not np.isfinite(v) or not np.isfinite(actual).all():raise ValueError('Nonfinite pointwise parity')
  np.testing.assert_allclose(v,expected,rtol=1e-10,atol=1e-9);np.testing.assert_allclose(actual,g,rtol=1e-9,atol=1e-8)
  points.append(dict(value_absolute_error=float(abs(v-expected)),gradient_max_absolute_error=float(np.max(np.abs(actual-g)))))
 return starts,dict(passed=True,oracle='normalized NumPy Target including exact prior-whitening Jacobian',points=points,one_time_jax_qualification='separate adapter/reference test evidence; not performed or charged as per-fit public work')

def jax_state():
 module=sys.modules.get('jax');lazy=module is not None and type(module) is importlib.util._LazyModule
 backend=[n for n in sys.modules if n.startswith('jax.') or n=='jaxlib' or n.startswith('jaxlib.')]
 return {'jax_initialized':bool(backend or (module is not None and not lazy)),'jax_lazy_proxy_registered':lazy,'jax_backend_modules':backend}

def no_jax():
 if jax_state()['jax_initialized']:raise RuntimeError('Public workflow must not initialize JAX')

def admit_public(model,physical_starts):
 no_jax();from whitened import compile_whitened
 tick=time.perf_counter();compiled=compile_whitened(model);compile_seconds=time.perf_counter()-tick;tick=time.perf_counter();u,parity=verify_parity(model,physical_starts,compiled.value_gradient);parity_seconds=time.perf_counter()-tick;no_jax()
 return compiled,u,dict(compile_seconds=compile_seconds,parity_seconds=parity_seconds,parity=parity,snapshot_sha256=compiled.snapshot_sha256,jax_imported=False)

def write(path,value):
 def clean(x):
  if isinstance(x,dict):return {k:clean(v) for k,v in x.items()}
  if isinstance(x,(list,tuple)):return [clean(v) for v in x]
  if hasattr(x,'tolist'):return clean(x.tolist())
  if isinstance(x,float) and not np.isfinite(x):return None
  return x
 path.write_text(json.dumps(clean(value),indent=2,allow_nan=False))

@contextmanager
def phase(record,name):
 tick=time.perf_counter()
 try:yield
 finally:record[name]=time.perf_counter()-tick

def execute(fixture,config,arm,seed,out,*,admission_only=False):
 started=time.perf_counter();out=Path(out);out.mkdir(exist_ok=False);r=dict(arm=arm,status='running',precision_pass=False,attempts=[],seed=seed,coordinates='prior_whitened',qualified=False,predictive_seed=fixture['predictive_seed'])
 def verify():
  for path,h in {**config['bindings'],**config.get('runtime_bindings',{})}.items():
   if hashlib.sha256(Path(path).read_bytes()).hexdigest()!=h:raise ValueError('Source/input binding differs: '+path)
 engine=None
 validation=config.get('validation_counts')
 if validation is not None and not config.get('validation_only'):raise ValueError('Nonproduction counts require validation_only')
 warmup=validation['warmup'] if validation else 1000
 tiers=validation['tiers'] if validation else [1000,2000,4000]
 if type(warmup) is not int or warmup<1 or not tiers or any(type(x) is not int or x<1 for x in tiers) or tiers!=sorted(set(tiers)) or any(x%tiers[0] for x in tiers):raise ValueError('Invalid counts')
 r['settings']={'warmup':warmup,'tiers':tiers,'validation_only':bool(validation)}
 try:
  verify();m=Target(**fixture['data'],priors=Priors(**fixture['priors']));physical=np.asarray(fixture['starts']);mean,sd,jac=transform(m);r['physical_initial_positions']=physical
  if arm=='public':
   import owalnuts,owalnuts._owalnuts as native
   actual={str(Path(x.__file__).resolve()):hashlib.sha256(Path(x.__file__).read_bytes()).hexdigest() for x in (owalnuts,native)}
   if actual!=config['runtime_bindings']:raise ValueError('Actual imported runtime path/hash differs')
   r['runtime_bindings']=actual
   with phase(r,'admission_seconds'):compiled,u,metadata=admit_public(m,physical)
   r.update(metadata)
   if not admission_only:engine=owalnuts.start_session(compiled.target,init=u,chains=4,warmup=warmup,max_draws=tiers[-1],seed=seed,threads=4)
  elif arm=='reference':
   with phase(r,'admission_seconds'):
    import jax,jaxlib,numpyro
    actual={str(Path(v.__file__).resolve()):hashlib.sha256(Path(v.__file__).read_bytes()).hexdigest() for v in (jax,jaxlib,numpyro)}
    if any(config['bindings'].get(p)!=h for p,h in actual.items()):raise ValueError('Actual reference package identity is not bound')
    r['reference_runtime_bindings']=actual
    from reference import make_reference
    from reference_continuation import ContinuedReference
    if jax.local_device_count()!=4 or jax.default_backend()!='cpu':raise ValueError('Four CPU devices required')
    density,_=make_reference(m);white=lambda u:density(mean+sd*u)+jac
    value_grad=jax.jit(jax.value_and_grad(white));tick=time.perf_counter();u,parity=verify_parity(m,physical,value_grad);r.update(parity=parity,parity_seconds=time.perf_counter()-tick)
    if not admission_only:engine=ContinuedReference(lambda u:-white(u),u,seed,warmup,tiers[0],.9,chain_method='parallel')
  else:raise ValueError('Unknown arm')
  r['sampling_initial_positions']=u
  if admission_only:r['status']='admission_passed';return r
  with phase(r,'adapt_seconds'):adapted=engine.adapt()
  if arm=='public':r.update(adapted_metadata=adapted.metadata,warmup_target_calls=adapted.target_calls)
  write(out/'report.json',r);chunks=[];previous=0;divergences=0
  from reporting import summarize
  for tier in tiers:
   attempt=dict(draws=tier);r['attempts'].append(attempt)
   with phase(attempt,'sampling_seconds'):
    if arm=='public':
     chunk=engine.draw(tier-previous)
     if (chunk.retained_start,chunk.retained_end)!=(previous,tier):raise ValueError('Retained prefix mismatch')
     if json.dumps(chunk.metadata,sort_keys=True,default=lambda a:a.tolist())!=json.dumps(adapted.metadata,sort_keys=True,default=lambda a:a.tolist()):raise ValueError('Frozen adaptation changed')
     chunks.append(np.asarray(chunk.samples));u=np.concatenate(chunks,axis=1);divergences+=sum(int(np.count_nonzero(c['divergent'])) for c in chunk.diagnostics);attempt.update(target_calls=chunk.target_calls,cumulative_work=chunk.cumulative_work)
    else:
     while len(engine.chunks)*tiers[0]<tier:engine.append()
     u=engine.samples;divergences=engine.divergences;attempt['checkpoints']=engine.checkpoints.copy()
    q=mean+sd*u
    if q.shape!=(4,tier,m.dimension) or not np.isfinite(q).all():raise ValueError('Canonical draws invalid')
   with phase(attempt,'evaluation_seconds'):evaluation=summarize(q,m,fixture['future'],predictive_seed=fixture['predictive_seed'])
   evaluation['precision_pass'] &= divergences==0;attempt.update(evaluation=evaluation,divergences=divergences)
   with phase(attempt,'serialization_seconds'):np.save(out/f'draws-{tier}.npy',q,allow_pickle=False);np.save(out/f'sampling-u-{tier}.npy',u,allow_pickle=False)
   previous=tier;verify()
   if arm=='public':no_jax()
   write(out/'report.json',r)
   if evaluation['precision_pass']:break
  r.update(status='completed',precision_pass=r['attempts'][-1]['evaluation']['precision_pass'])
 except Exception as exc:r.update(status='failed',precision_pass=False,error=repr(exc),traceback=traceback.format_exc())
 finally:
  if engine is not None and arm=='public':
   try:engine.close()
   except Exception as exc:r['cleanup_error']=repr(exc);r['status']='failed';r['precision_pass']=False
  try:verify()
  except Exception as exc:r.update(status='failed',precision_pass=False,integrity_error=repr(exc))
  r['end_to_end_seconds']=time.perf_counter()-started
  r['process_seconds_since_pre_numpy_import']=time.perf_counter()-PROCESS_START
  if arm=='public':
   r.update(jax_state());r['jax_imported']=r['jax_initialized']
  write(out/'report.json',r)
 return r

def main():
 p=argparse.ArgumentParser();p.add_argument('--fixture',required=True,type=Path);p.add_argument('--config',required=True,type=Path);p.add_argument('--arm',choices=['public','reference'],required=True);p.add_argument('--seed',required=True,type=int);p.add_argument('--out',required=True,type=Path);p.add_argument('--admission-only',action='store_true');a=p.parse_args()
 # Reference engine is reusable study infrastructure, imported only on that arm.
 sys.path.insert(1,str(Path(__file__).resolve().parents[2]/'options_flow_v1'))
 r=execute(json.loads(a.fixture.read_text()),json.loads(a.config.read_text()),a.arm,a.seed,a.out,admission_only=a.admission_only)
 return int(not(r.get('precision_pass') or r['status']=='admission_passed'))
if __name__=='__main__':raise SystemExit(main())
