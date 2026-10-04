"""Correctness/graph comparison only. No timing claims or MCMC."""
import sys,json,hashlib,time
from pathlib import Path
from unittest.mock import patch
from collections import Counter
ROOT=Path(__file__).resolve().parents[2];OUT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'STUDIES/options_flow_v1'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def run():
 import numpy as np,pymc,owalnuts
 from algebra import build_model
 from flow_mixed_coordinates import build_model as baseline_model,normalized_parity
 from pymc_workflow import evaluate_cfunc
 profile_path=ROOT/'target/mixed-target-profile-v1/profile-result.json';profile=json.loads(profile_path.read_text());config_path=ROOT/'target/mixed-target-profile-v1/config.json';config=json.loads(config_path.read_text());fixture_path=Path(config['fixture']);fixture=json.loads(fixture_path.read_text());data=fixture['data']
 points=[np.asarray(r['sampling_position'],dtype=np.float64) for r in profile['points']];ids=[r['id'] for r in profile['points']]
 # Fixed stress regimes chosen before results, no RNG. All preserve coordinate dimension.
 for i,(mu,ls,lt) in enumerate([(-40.,-10.,-8.),(40.,-10.,2.),(-8.,-2.,-4.),(8.,0.,1.)]):
  q=points[0].copy();q[2]=mu;q[3]=ls;q[1]=lt;points.append(q);ids.append('fixed-stress-'+str(i))
 graphs={};targets={};compile_seconds={};original=pymc.Model.logp_dlogp_function
 for name,builder in [('baseline',baseline_model),('shared_logvol',build_model)]:
  captured=[]
  def capture(self,*args,**kwargs):
   fn=original(self,*args,**kwargs);graph=fn._pytensor_function.maker.fgraph;nodes=graph.toposort();captured.append(dict(nodes=len(nodes),ops=dict(Counter(type(n.op).__name__ for n in nodes)),node_descriptions=[str(n.op) for n in nodes]));return fn
  tick=time.perf_counter()
  with patch.object(pymc.Model,'logp_dlogp_function',capture):targets[name]=owalnuts.from_pymc(builder(data,32),gil_free=True)[0]
  compile_seconds[name]=time.perf_counter()-tick;graphs[name]=captured
 rows=[]
 for identity,q in zip(ids,points):
  baseline,gb=evaluate_cfunc(targets['baseline'],q);candidate,gc=evaluate_cfunc(targets['shared_logvol'],q)
  if not np.isfinite(baseline) or not np.isfinite(gb).all() or not np.isfinite(candidate) or not np.isfinite(gc).all():raise ValueError('Nonfinite valid regime: '+identity)
  np.testing.assert_allclose(candidate,baseline,rtol=1e-10,atol=1e-8);np.testing.assert_allclose(gc,gb,rtol=1e-9,atol=1e-8)
  rows.append(dict(id=identity,value_error=abs(candidate-baseline),gradient_max_error=float(np.max(np.abs(gc-gb)))))
 parity=normalized_parity(data,points,targets['shared_logvol'])
 result=dict(status='passed',qualified=False,scope='Correctness and graph evidence only; no timed target benchmark',rows=rows,normalized_parity=parity,graphs=graphs,graphs_differ=graphs['baseline']!=graphs['shared_logvol'],compile_seconds_descriptive=compile_seconds,bindings={str(p):sha(p) for p in [Path(__file__),OUT/'algebra.py',profile_path,config_path,fixture_path]},runtime=dict(python=sys.version,numpy=np.__version__,pymc=pymc.__version__,adapter_sha256=sha(owalnuts.__file__)))
 with (OUT/'validation-result.json').open('x') as f:json.dump(result,f,indent=2,allow_nan=False)
 return result
if __name__=='__main__':
 if (OUT/'validation-result.json').exists() or (OUT/'validation-failure.json').exists():raise FileExistsError('No overwrite')
 try:run()
 except Exception as e:
  import traceback
  with (OUT/'validation-failure.json').open('x') as f:json.dump(dict(error=str(e),traceback=traceback.format_exc()),f,indent=2)
  raise
