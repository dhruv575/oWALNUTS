import hashlib,json
from pathlib import Path
import numpy as np
from scipy.integrate import quad
from scipy.stats import gamma,poisson
from exact_controls import log_evidence,predictive_logpmf,fit_controls
p=Path(__file__).resolve().parent;checks=[]
for counts in [[],[0],[1,2,0],[4,0,2,1]]:
 value,error=quad(lambda rate:np.exp(-rate)*np.prod(poisson.pmf(counts,rate)),0,np.inf,epsabs=1e-12,epsrel=1e-10);expected=np.exp(log_evidence(counts));assert np.isclose(value,expected,rtol=1e-9,atol=1e-12);checks.append(dict(counts=counts,numeric=value,exact=float(expected),quadrature_error=error))
for shape,rate in [(1,1),(4,2),(20,8)]:
 for k in [0,1,7]:
  numeric,error=quad(lambda value:gamma.pdf(value,a=shape,scale=1/rate)*poisson.pmf(k,value),0,np.inf,epsabs=1e-12,epsrel=1e-10);exact=float(np.exp(predictive_logpmf(k,shape,rate)));assert np.isclose(numeric,exact,rtol=1e-9,atol=1e-12)
 assert abs(np.exp(predictive_logpmf(np.arange(1000),shape,rate)).sum()-1)<1e-12
rows=json.loads((p/'data01/TRAIN.json').read_text());assert min(x['year'] for x in rows)==1851 and max(x['year'] for x in rows)==1930;result=fit_controls(rows);assert result['training_observed']==79 and len(result['changepoint']['components'])==80
last=result['changepoint']['components'][-1];assert last['late_shape']==last['late_rate']==1
for component in result['changepoint']['components']:
 assert abs(np.exp(predictive_logpmf(np.arange(1000),component['late_shape'],component['late_rate'])).sum()-1)<1e-12
out=p/'exact_controls01';out.mkdir(exist_ok=False);(out/'POSTERIOR.json').write_text(json.dumps(result,indent=2)+'\n');audit=dict(passed=True,evidence_quadrature=checks,predictive_integrals_checked=9,missing_counts_excluded=True,empty_late_regime_preserved=True,heldout_scores_computed=False,inputs={str(f.relative_to(p)):hashlib.sha256(f.read_bytes()).hexdigest() for f in [p/'exact_controls.py',Path(__file__),p/'data01/TRAIN.json',p/'DATA-AND-CONTROLS-PROTOCOL.md']});(out/'VERIFICATION.json').write_text(json.dumps(audit,indent=2)+'\n');print(json.dumps(dict(passed=True,training_observed=79,changepoints=80,heldout_scores_computed=False)))
