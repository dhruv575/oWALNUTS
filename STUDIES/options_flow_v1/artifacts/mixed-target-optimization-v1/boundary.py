"""Numerical-domain comparison, not a target-speed benchmark."""
import sys,json,math,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];OUT=Path(__file__).resolve().parent;sys.path.insert(0,str(ROOT/'STUDIES/options_flow_v1'))
import numpy as np,owalnuts
from algebra import build_model
from flow_mixed_coordinates import build_model as baseline
from pymc_workflow import evaluate_cfunc
rows=[]
for y in [0.,1e-160,1e-150]:
 data=dict(y=[[y]],x=[[0.]],rho=.95,nu=5.)
 targets={name:owalnuts.from_pymc(builder(data,32),gil_free=True)[0] for name,builder in [('baseline',baseline),('candidate',build_model)]}
 for h in [-740.,-710.,-690.,690.,710.,740.]:
  q=np.array([0.,-1.,h,-10.,0.,0.,0.]);row=dict(y=y,h=h)
  # Independent scalar normalized value oracle for the exactly zero path/slopes.
  def normal(x,m,s):return -.5*((x-m)/s)**2-math.log(s)-.5*math.log(2*math.pi)
  prior=sum(normal(x,m,s) for x,m,s in zip(q[:4],[0.,-1.,-1.,-1.5],[.5,.5,1.,.5]))+normal(0,0,1)+normal(0,0,math.exp(-1))+normal(0,0,1)
  z=y*math.exp(-h/2);like=math.lgamma(3)-math.lgamma(2.5)-.5*math.log(5*math.pi)-h/2-3*math.log1p(z*z/5)
  row['scalar_normalized_value']=prior+like
  for name,target in targets.items():
   v,g=evaluate_cfunc(target,q);finite=bool(np.isfinite(v) and np.isfinite(g).all());row[name]=dict(finite=finite,value=float(v) if math.isfinite(v) else None,gradient=np.asarray(g).tolist() if np.isfinite(g).all() else None,value_error=abs(v-row['scalar_normalized_value']) if math.isfinite(v) else None)
  row['new_rejection']=row['baseline']['finite'] and not row['candidate']['finite'];rows.append(row)
result=dict(phase='posthoc-numerical-domain-check',qualified=False,rows=rows,new_rejections=sum(r['new_rejection'] for r in rows),both_reject=sum(not r['baseline']['finite'] and not r['candidate']['finite'] for r in rows),sources={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in [Path(__file__),OUT/'algebra.py']})
with (OUT/'boundary-result.json').open('x') as f:json.dump(result,f,indent=2,allow_nan=False)
print(json.dumps({k:v for k,v in result.items() if k not in ('rows','sources')}))
