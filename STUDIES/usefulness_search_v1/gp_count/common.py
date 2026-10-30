import numpy as np,bridgestan
from pathlib import Path
ROOT=Path(__file__).resolve().parent
MODELS=Path('/home/ubuntu/lanes/metric_autoselect_confirmation_v1/models');NAME='gp_pois_regr-gp_pois_regr'
class Target:
 def __init__(self):
  self.model=bridgestan.StanModel(str(MODELS/(NAME+'_model.so')),data=str(MODELS/(NAME+'.data.json')),seed=1);self.grad_calls=0;self.value_calls=0;self.errors=0
  self.names=self.model.param_names(include_tp=True,include_gq=False);self.indices=[self.names.index(n) for n in ['rho','alpha']+[f'f.{i}' for i in range(1,12)]]
 def gradient(self,q):
  self.grad_calls+=1
  try:return self.model.log_density_gradient(q)
  except RuntimeError:self.errors+=1;return -np.inf,np.zeros(13)
 def value(self,q):
  self.value_calls+=1
  try:return float(self.model.log_density(q))
  except RuntimeError:self.errors+=1;return -np.inf
 def transform(self,q):
  a=np.asarray(self.model.param_constrain(q,include_tp=True,include_gq=False))[self.indices]
  return np.r_[a,np.exp(a[2:])]
 def counts(self):return dict(gradient=self.grad_calls,value=self.value_calls,errors=self.errors)
