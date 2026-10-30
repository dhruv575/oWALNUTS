import hashlib,json
from pathlib import Path
import numpy as np
from model import Population
ROOT=Path(__file__).resolve().parent;run=ROOT/'run01';out=ROOT/'analysis01';out.mkdir(exist_ok=False)
manifest=json.loads((run/'MANIFEST.json').read_text());final=json.loads((run/'FINAL.json').read_text());assert final['dependencies_unchanged'] and all(j['group_drained'] and j['exit_code']==0 for j in final['jobs'])
inputs={};rows=[]
for p in sorted(run.glob('*/result/RESULT.json')):
 inputs[str(p)]=hashlib.sha256(p.read_bytes()).hexdigest();rows.append(json.loads(p.read_text()))
results={}
for kind in ('linear','nonlinear'):
 fits=[r for r in rows if r['kind']==kind];qualified=[r for r in fits if r['qualified']];assert qualified
 selected=max(qualified,key=lambda r:r['lp']);x=np.array(selected['q']);m=Population(kind);base,g=m.value(x);pred=m.predict(x);checks=[]
 for solver in (0,1):
  tight=Population(kind,tol=1e-12,solver=solver);v,gg=tight.value(x);pp=tight.predict(x);checks.append(dict(solver=solver,log_density_difference=abs(v-base),max_scaled_gradient_difference=float(np.max(abs(g-gg)/(1+abs(g)))),max_log_prediction_difference=float(np.max(abs(pred-pp)))));tight.close()
 numerical_pass=all(c['max_scaled_gradient_difference']<=.001 and c['max_log_prediction_difference']<=.003 for c in checks)
 sigma=float(np.exp(x[-1]));y=m.holdout;mu=pred[:,-2:];error=mu-np.log(y);lpd=-np.log(y)-np.log(sigma)-.5*np.log(2*np.pi)-.5*(error/sigma)**2
 results[kind]=dict(qualified_starts=len(qualified),attempts=len(fits),selected_rep=selected['rep'],gradient_max=selected['gradient_max'],numerical_pass=numerical_pass,numerical_checks=checks,shared_sigma=sigma,heldout_log_rmse=float(np.sqrt(np.mean(error**2))),subject_log_rmse=np.sqrt(np.mean(error**2,axis=1)).tolist(),subject_plugin_log_predictive_density=lpd.sum(axis=1).tolist(),parameter_uncertainty_included=False)
 m.close()
inputs[str(Path(__file__))]=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
for n,d in [('SUMMARY',results),('INPUT-HASHES',inputs)]: (out/(n+'.json')).write_text(json.dumps(d,indent=2,allow_nan=False)+'\n')
print(json.dumps(results,indent=2))
