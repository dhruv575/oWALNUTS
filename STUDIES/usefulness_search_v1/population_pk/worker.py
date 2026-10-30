import json,sys,time
from pathlib import Path
import numpy as np
from scipy.optimize import minimize
from model import Population
kind,rep,out=sys.argv[1:];rep=int(rep);out=Path(out);out.mkdir(exist_ok=False);start=time.monotonic();model=Population(kind);d=model.d
starts=[model.start()]+[model.start()+.2*np.random.default_rng(928100001+i).normal(size=model.dim) for i in range(3)]
errors=[]
def objective(x):
 try:v,g=model.value(x);return -v,-g
 except ValueError as e:
  if len(errors)<20:errors.append(str(e))
  return 1e100,np.zeros(model.dim)
bounds=[(-8,8)]*d+[(-6,2)]*d+[(-8,8)]*(12*d)+[(-8,2)]
r=minimize(objective,starts[rep],jac=True,method='L-BFGS-B',bounds=bounds,options=dict(maxiter=500,ftol=1e-12,gtol=1e-6,maxls=30))
lp,g=model.value(r.x);boundary=any(min(abs(x-a),abs(x-b))<1e-5 for x,(a,b) in zip(r.x,bounds))
result=dict(kind=kind,rep=rep,seconds=time.monotonic()-start,optimizer_success=bool(r.success),message=str(r.message),iterations=int(r.nit),evaluations=int(r.nfev),lp=lp,q=r.x.tolist(),gradient_max=float(abs(g).max()),boundary=boundary,qualified=bool(r.success and abs(g).max()<.01 and not boundary),errors=errors)
(out/'RESULT.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n');model.close();print(json.dumps({k:v for k,v in result.items() if k!='q'}))
