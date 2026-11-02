import os
for k in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS']:os.environ[k]='1'
from reference import *
from scipy.special import erf
import warnings
with warnings.catch_warnings():
    warnings.simplefilter('ignore',RuntimeWarning)
    result=integrate(dict(n=[0]*12,y=[0]*12),(72,64,64),(-20,3.5),1.25)
mean=np.array(result['mean']);sd=np.array(result['sd'])
checks=dict(mu_mean=abs(mean[0]),mu_sd=abs(sd[0]-2),tau_mean=abs(mean[1]-np.sqrt(2/np.pi)),tau_sd=abs(sd[1]-np.sqrt(1-2/np.pi)),theta_mean=float(max(abs(mean[2:14]))),theta_sd=float(max(abs(sd[2:14]-np.sqrt(5)))),probability_symmetry=float(max(abs(mean[14:26]-.5))),pooling_probability=float(max(abs(mean[26:]-erf(np.array([.1,.5])/np.sqrt(2))))))
assert max(checks.values())<1e-5,checks
(BASE/'REFERENCE-PRIOR-AUDIT.json').write_text(json.dumps(dict(passed=True,errors=checks,reference=result),indent=2));print(json.dumps(checks))
