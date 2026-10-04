"""Fixed 18-case integrated target domain check; no sampling or timings claim."""
import argparse,hashlib,json,math,sys,time
from pathlib import Path

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
 p=argparse.ArgumentParser();p.add_argument('--config',required=True);p.add_argument('--out',required=True);a=p.parse_args()
 config=Path(a.config);original=sha(config);c=json.loads(config.read_text());out=Path(a.out)
 if out.exists():raise FileExistsError(out)
 def verify():
  if sha(config)!=original:raise ValueError('Config drift')
  for path,digest in c['bindings'].items():
   if sha(path)!=digest:raise ValueError('Binding drift: '+path)
 verify();sys.path.insert(0,c['study'])
 import numpy as np,owalnuts,pymc,pytensor,numba
 import owalnuts._owalnuts as extension
 def runtime():
  result={}
  for key,module in [('adapter',owalnuts),('extension',extension)]:
   path=Path(module.__file__).resolve();expected=c['runtime_identity'][key]
   if path!=Path(expected['path']).resolve() or sha(path)!=expected['sha256']:raise ValueError('Actual runtime mismatch: '+key)
   result[key]=dict(path=str(path),sha256=sha(path))
  return result
 before=runtime()
 from flow_mixed_coordinates import build_model
 from pymc_workflow import evaluate_cfunc
 rows=[];tick=time.perf_counter()
 for y in c['y_values']:
  data=dict(y=[[y]],x=[[0.]],rho=.95,nu=5.)
  targets={name:owalnuts.from_pymc(build_model(data,32,likelihood_variant=variant),gil_free=True)[0] for name,variant in [('baseline','pymc_student_t'),('candidate','shared_logvol_student_t_v1')]}
  for h in c['h_values']:
   q=np.array([0.,-1.,h,-10.,0.,0.,0.])
   def normal(x,m,s):return -.5*((x-m)/s)**2-math.log(s)-.5*math.log(2*math.pi)
   prior=sum(normal(x,m,s) for x,m,s in zip(q[:4],[0.,-1.,-1.,-1.5],[.5,.5,1.,.5]))+normal(0,0,1)+normal(0,0,math.exp(-1))+normal(0,0,1)
   # Stable scalar log(1+exp(z)); avoids squaring tiny residuals or exp(-h).
   log_ratio=-math.inf if y==0 else 2*math.log(abs(y))-h-math.log(5)
   softplus=max(log_ratio,0)+math.log1p(math.exp(-abs(log_ratio)))
   oracle=prior+math.lgamma(3)-math.lgamma(2.5)-.5*math.log(5*math.pi)-h/2-3*softplus
   row=dict(y=y,h=h,scalar_normalized_value=oracle)
   for name,target in targets.items():
    v,g=evaluate_cfunc(target,q);vf=bool(np.isfinite(v));gf=bool(np.isfinite(g).all())
    row[name]=dict(finite=vf and gf,value_finite=vf,gradient_finite=gf,value=float(v) if vf else None,gradient=np.asarray(g).tolist() if gf else None,value_error=abs(float(v)-oracle) if vf else None)
   row['new_rejection']=row['baseline']['finite'] and not row['candidate']['finite'];rows.append(row)
 verify();after=runtime()
 if after!=before:raise ValueError('Runtime changed')
 result=dict(qualified=False,scope='Fixed 18 numerical-domain cases only; rejection is nonfinite value or gradient. No sampling, speed or global-domain claim.',config_sha256=original,bindings=c['bindings'],runtime_identity=after,software=dict(python=sys.version,numpy=np.__version__,pymc=pymc.__version__,pytensor=pytensor.__version__,numba=numba.__version__),rows=rows,new_rejections=sum(r['new_rejection'] for r in rows),both_reject=sum(not r['baseline']['finite'] and not r['candidate']['finite'] for r in rows),elapsed_seconds=time.perf_counter()-tick)
 with out.open('x') as f:json.dump(result,f,indent=2,allow_nan=False)
 print(json.dumps(dict(cases=len(rows),new_rejections=result['new_rejections'],both_reject=result['both_reject'])))
if __name__=='__main__':main()
