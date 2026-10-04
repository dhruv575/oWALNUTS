"""Paired automatic-gradient target calls only; requires scheduled quiet window."""
import argparse,ctypes,hashlib,json,sys,time,traceback
from pathlib import Path
START=time.perf_counter()
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()
def save(p,v):
 with Path(p).open('x') as f:json.dump(v,f,indent=2,allow_nan=False)
def run(args):
 config_bytes=Path(args.config).read_bytes();config_sha256=hashlib.sha256(config_bytes).hexdigest();c=json.loads(config_bytes);sys.path.insert(0,c['study'])
 from reference_bank_allocation import memory_limit
 guard=memory_limit(c['memory_bytes'])
 from hardware_control import get_affinity
 if get_affinity()!=[0]:raise ValueError('CPU0 required')
 for p,h in c['bindings'].items():
  if sha(p)!=h:raise ValueError('Input/source drift: '+p)
 import numpy as np,owalnuts,pymc,pytensor,numba
 import owalnuts._owalnuts as extension
 from algebra import build_model as candidate
 from flow_mixed_coordinates import build_model as baseline
 from pymc_workflow import evaluate_cfunc
 fixture=json.loads(Path(c['fixture']).read_text());data=fixture['data'];profile=json.loads(Path(c['profile']).read_text());validation=json.loads(Path(c['validation']).read_text());boundary=json.loads(Path(c['boundary']).read_text())
 if validation['status']!='passed' or validation['normalized_parity']['passed'] is not True:raise ValueError('Prior normalized parity missing')
 if boundary['new_rejections']!=0:raise ValueError('Known candidate-only numerical rejection')
 points=[np.ascontiguousarray(row['sampling_position'],dtype=np.float64) for row in profile['points']]
 targets={};compilation={};builders={'baseline':baseline,'candidate':candidate}
 order=['baseline','candidate'] if args.order=='AB' else ['candidate','baseline']
 for name in order:
  t=time.perf_counter();targets[name]=owalnuts.from_pymc(builders[name](data,32),gil_free=True)[0];compilation[name]=time.perf_counter()-t
 checks=[]
 for row,q in zip(profile['points'],points):
  for name,target in targets.items():
   v,g=evaluate_cfunc(target,q)
   if not np.isfinite(v) or not np.isfinite(g).all():raise ValueError('Nonfinite saved point')
   np.testing.assert_allclose(v,row['value'],rtol=1e-10,atol=1e-8);np.testing.assert_allclose(g,row['gradient'],rtol=1e-9,atol=1e-8)
   checks.append(dict(id=row['id'],implementation=name,value_error=abs(v-row['value']),gradient_max_error=float(np.max(np.abs(g-row['gradient'])))))
 # Stress parity before timing, same four deterministic regimes as validated artifact.
 for mu,ls,lt in [(-40.,-10.,-8.),(40.,-10.,2.),(-8.,-2.,-4.),(8.,0.,1.)]:
  q=points[0].copy();q[2]=mu;q[3]=ls;q[1]=lt;v,g=evaluate_cfunc(targets['baseline'],q);w,h=evaluate_cfunc(targets['candidate'],q)
  np.testing.assert_allclose(v,w,rtol=1e-10,atol=1e-8);np.testing.assert_allclose(g,h,rtol=1e-9,atol=1e-8)
 ptr=ctypes.POINTER(ctypes.c_double);abi=ctypes.CFUNCTYPE(ctypes.c_double,ctypes.c_ssize_t,ptr,ptr,ctypes.c_void_p);callers={n:abi(t.address) for n,t in targets.items()}
 gradients={n:[np.empty_like(q) for q in points] for n in targets};ip=[q.ctypes.data_as(ptr) for q in points];gp={n:[g.ctypes.data_as(ptr) for g in gradients[n]] for n in targets};dimension=points[0].size
 blocks=[];checksum=0.
 for block in range(c['blocks']):
  block_order=order if block%2==0 else order[::-1]
  for name in block_order:
   fn=callers[name];op=gp[name];cpu=time.process_time();tick=time.perf_counter()
   for j in range(c['calls_per_block']):
    index=j%len(points);checksum+=fn(dimension,ip[index],op[index],None)
   elapsed=time.perf_counter()-tick;cpu_elapsed=time.process_time()-cpu
   if any(not np.isfinite(g).all() for g in gradients[name]):raise ValueError('Nonfinite timed gradient')
   blocks.append(dict(block=block,implementation=name,calls=c['calls_per_block'],seconds=elapsed,cpu_seconds=cpu_elapsed,seconds_per_call=elapsed/c['calls_per_block']))
 for p,h in c['bindings'].items():
  if sha(p)!=h:raise ValueError('Postbenchmark drift: '+p)
 if get_affinity()!=[0]:raise ValueError('Affinity drift')
 if sha(args.config)!=config_sha256:raise ValueError('Configuration changed during benchmark')
 return dict(status='completed',qualified=False,order=args.order,config_sha256=config_sha256,compile_seconds=compilation,checks=checks,blocks=blocks,checksum=checksum,elapsed_seconds=time.perf_counter()-START,runtime=dict(python=sys.version,numpy=np.__version__,pymc=pymc.__version__,pytensor=pytensor.__version__,numba=numba.__version__,extension_sha256=sha(extension.__file__),adapter_sha256=sha(owalnuts.__file__)),scope='Two compiled targets, identical buffers/positions/ctypes loops; automatic gradients only. Warm disk/compiler caches uncontrolled. Target microbenchmark, not sampler workflow evidence; known shared extreme-domain rejections remain unresolved.')
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--config',required=True);p.add_argument('--order',choices=['AB','BA'],required=True);p.add_argument('--out',required=True);a=p.parse_args()
 if Path(a.out).exists() or Path(a.out+'.failure.json').exists():raise FileExistsError('No overwrite')
 try:save(a.out,run(a))
 except Exception as exc:
  save(a.out+'.failure.json',dict(error=str(exc),traceback=traceback.format_exc()));raise
