"""Prepared target-only diagnosis. Execute only after timing clearance."""
import argparse,ctypes,hashlib,json,sys,time,os
from pathlib import Path
START=time.perf_counter()
def sha(path):
 h=hashlib.sha256()
 with Path(path).open('rb') as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()
def save(path,value):
 with Path(path).open('x') as f:json.dump(value,f,indent=2,allow_nan=False)
def main():
 a=argparse.ArgumentParser();a.add_argument('--config',required=True);a.add_argument('--mode',choices=['profile','parity'],required=True);a.add_argument('--out',required=True);a.add_argument('--profile');args=a.parse_args()
 config=json.loads(Path(args.config).read_text());out=Path(args.out)
 if out.exists():raise FileExistsError(out)
 sys.path.insert(0,config['study'])
 from reference_bank_allocation import memory_limit
 memory_guard=memory_limit(config['memory_bytes'])
 from hardware_control import get_affinity
 if get_affinity()!=[0]:raise ValueError('CPU0 wrapper required')
 for p,h in config['bindings'].items():
  if sha(p)!=h:raise ValueError('Bound input changed: '+p)
 fixture=json.loads(Path(config['fixture']).read_text());data=fixture['data']
 import numpy as np
 if args.mode=='parity':
  if not args.profile:raise ValueError('Profile result required')
  measured=json.loads(Path(args.profile).read_text())
  if measured['config_sha256']!=sha(args.config):raise ValueError('Profile/config mismatch')
  import jax
  jax.config.update('jax_enable_x64',True)
  import jax.numpy as jnp
  from jax.scipy.special import gammaln
  from model import log_density
  from flow_mixed_coordinates import jax_log_density,jax_to_canonical,log_jacobian
  direct=jax.jit(jax.value_and_grad(lambda u:jax_log_density(u,data)))
  canonical=jax.jit(jax.value_and_grad(lambda u:log_density(jax_to_canonical(u,data),data,jnp,gammaln)+log_jacobian(u,data,jnp)))
  checks=[]
  for row in measured['points']:
   u=jnp.asarray(row['sampling_position']);v,g=direct(u);cv,cg=canonical(u)
   for value,gradient in [(v,g),(cv,cg)]:
    np.testing.assert_allclose(row['value'],value,rtol=1e-10,atol=1e-8);np.testing.assert_allclose(row['gradient'],gradient,rtol=1e-9,atol=1e-8)
   checks.append(dict(id=row['id'],value_error=abs(float(v)-row['value']),gradient_max_error=float(np.max(np.abs(np.asarray(g)-row['gradient']))),canonical_gradient_max_error=float(np.max(np.abs(np.asarray(cg)-row['gradient'])))))
  result=dict(mode='separate-normalized-JAX-parity',passed=True,checks=checks,profile_sha256=sha(args.profile),jax_version=jax.__version__)
 else:
  import owalnuts,pymc,pytensor,numba
  import owalnuts._owalnuts as extension
  from collections import Counter
  from unittest.mock import patch
  from flow_mixed_coordinates import to_mixed
  from pymc_flow_continuation_workflow import compile_target
  raw=json.loads(Path(config['raw']).read_text());q=np.asarray(raw['canonical_draws'],dtype=np.float64);starts=np.asarray(data['initial_positions']);positions=[]
  for spec in config['positions']:
   v=starts[spec['chain']] if spec['kind']=='start' else q[spec['chain'],spec['draw']]
   positions.append(dict(id=spec['id'],canonical_position=v.tolist(),sampling_position=np.ascontiguousarray(to_mixed(v,data)).tolist()))
  del raw,q
  graphs=[];original=pymc.Model.logp_dlogp_function
  def capture(self,*args,**kwargs):
   fn=original(self,*args,**kwargs);graph=fn._pytensor_function.maker.fgraph;nodes=graph.toposort();graphs.append(dict(nodes=len(nodes),ops=dict(Counter(type(n.op).__name__ for n in nodes)),scans=[dict(name=getattr(n.op,'name',None),inner_nodes=len(n.op.fgraph.toposort()),ops=dict(Counter(type(x.op).__name__ for x in n.op.fgraph.toposort()))) for n in nodes if type(n.op).__name__=='Scan']));return fn
  ts=time.perf_counter()
  with patch.object(pymc.Model,'logp_dlogp_function',capture):target,compilation=compile_target(data,'flow',32,'mixed_slopes')
  compile_seconds=time.perf_counter()-ts
  pointer=ctypes.POINTER(ctypes.c_double);abi=ctypes.CFUNCTYPE(ctypes.c_double,ctypes.c_ssize_t,pointer,pointer,ctypes.c_void_p);caller=abi(target.address)
  signature=numba.types.float64(numba.types.intp,numba.types.CPointer(numba.types.float64),numba.types.CPointer(numba.types.float64),numba.types.voidptr)
  @numba.cfunc(signature)
  def noop(n,q,g,ctx):return q[0]
  @numba.cfunc(signature)
  def zero_gradient(n,q,g,ctx):
   for i in range(n):g[i]=0.
   return q[0]
  controls={'ctypes_noop':abi(noop.address),'ctypes_zero_gradient':abi(zero_gradient.address),'target':caller}
  inputs=[np.asarray(p['sampling_position'],dtype=np.float64) for p in positions];grads=[np.empty_like(q) for q in inputs];ip=[q.ctypes.data_as(pointer) for q in inputs];gp=[g.ctypes.data_as(pointer) for g in grads];dim=len(inputs[0]);first=[]
  for i,row in enumerate(positions):
   ts=time.perf_counter();v=caller(dim,ip[i],gp[i],None);first.append(time.perf_counter()-ts)
   if not np.isfinite(v) or not np.isfinite(grads[i]).all():raise ValueError('Nonfinite target')
   row.update(value=v,gradient=grads[i].tolist())
  blocks=[];checksum=0.
  for block in range(config['blocks']):
   order=['ctypes_noop','target','ctypes_zero_gradient'] if block%2==0 else ['ctypes_zero_gradient','target','ctypes_noop']
   for name in order:
    function=controls[name];cpu=time.process_time();ts=time.perf_counter()
    for j in range(config['calls_per_block']):
     i=j%len(ip);checksum+=function(dim,ip[i],gp[i],None)
    elapsed=time.perf_counter()-ts;blocks.append(dict(block=block,kind=name,calls=config['calls_per_block'],seconds=elapsed,cpu_seconds=time.process_time()-cpu,seconds_per_call=elapsed/config['calls_per_block']))
  result=dict(mode='target-only-exploratory',qualified=False,points=positions,compile_seconds=compile_seconds,compilation=compilation,graphs=graphs,first_call_seconds=first,blocks=blocks,checksum=checksum,runtime=dict(python=sys.version,numpy=np.__version__,pymc=pymc.__version__,pytensor=pytensor.__version__,numba=numba.__version__,extension=str(extension.__file__),extension_sha256=sha(extension.__file__),adapter=str(owalnuts.__file__),adapter_sha256=sha(owalnuts.__file__)),scope='No MCMC. ctypes dispatch controls include loop/index overhead; target minus control is descriptive, not proof of Rust trajectory overhead. Existing compiler caches retained; parity runs separately.')
 for p,h in config['bindings'].items():
  if sha(p)!=h:raise ValueError('Postprofile drift: '+p)
 result.update(config_sha256=sha(args.config),affinity=get_affinity(),elapsed_seconds=time.perf_counter()-START)
 save(out,result)
if __name__=='__main__':main()
