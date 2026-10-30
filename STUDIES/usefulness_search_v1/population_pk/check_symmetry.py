import json
from pathlib import Path
import numpy as np
from scipy.optimize import minimize
from native import Native,ROOT
prep=json.loads((ROOT/'PREPARED.json').read_text());x=np.array(prep['mode']);b=Native()
y=x.copy();y[0],y[1]=x[1],x[0];y[2]=x[2]+x[1]-x[0];y[3],y[4]=x[4],x[3]
z=x[6:-1].reshape(12,3);zz=z.copy();zz[:,0],zz[:,1]=z[:,1],z[:,0]
zz[:,2]=(np.exp(x[5])*z[:,2]+np.exp(x[4])*z[:,1]-np.exp(x[3])*z[:,0])/np.exp(x[5]);y[6:-1]=zz.ravel()
differences=abs(b.model.predict(x)-b.model.predict(y));zero=np.array([v.data['c0']==0 for v in b.model.backends]);predict_error=float(differences.max());zero_error=float(differences[zero].max());assert zero_error<1e-7
before=b.value(x)[0];flipped=b.value(y)[0];errors=[]
def obj(q):
 try:v,g=b.value(q);return -v,-g
 except ValueError:
  errors.append('invalid evaluation');return 1e100,np.zeros(43)
r=minimize(obj,y,jac=True,method='L-BFGS-B',bounds=[(-8,8)]*3+[(-6,2)]*3+[(-8,8)]*36+[(-8,2)],options=dict(maxiter=500,ftol=1e-12,gtol=1e-6,maxls=30))
v,g=b.value(r.x)
result=dict(symmetry_log_prediction_error=predict_error,zero_baseline_error=zero_error,zero_baseline_subjects=int(zero.sum()),original_log_density=before,flipped_log_density=flipped,optimized_log_density=v,optimizer_success=bool(r.success),gradient_max=float(abs(g).max()),iterations=int(r.nit),errors=len(errors),original_population_mean=x[:3].tolist(),flipped_optimized_population_mean=r.x[:3].tolist(),flipped_start=y.tolist(),optimized_q=r.x.tolist(),not_a_mode_probability=True)
(ROOT/'SYMMETRY.json').write_text(json.dumps(result,indent=2)+'\n');b.close();print(json.dumps({k:v for k,v in result.items() if k not in ('flipped_start','optimized_q')}))
