"""Optional normalized Student-t algebra; automatic PyTensor gradients only."""
import math
import numpy as np

def build_model(data, block_size=32):
 import pymc as pm
 import pytensor.tensor as pt
 from model import validate
 from flow_starts import canonical_starts
 from flow_mixed_coordinates import to_mixed
 from pymc_flow_workflow import ar_path
 y,x=validate(data);t,g=y.shape;k=4+2*g;nu=float(data['nu'])
 if block_size!=32:raise ValueError('Single prospective block32 candidate, no tuning sweep')
 chains=len(data['initial_positions']) if 'initial_positions' in data else 1
 initial=to_mixed(canonical_starts(data,chains),data)[0]
 constant=math.lgamma((nu+1)/2)-math.lgamma(nu/2)-.5*math.log(nu*math.pi)
 with pm.Model() as model:
  u=pm.Flat('q',shape=k+t,initval=initial)
  lp=pt.sum(pm.logp(pm.Normal.dist(mu=np.array([0.,-1.,-1.,-1.5]),sigma=np.array([.5,.5,1.,.5])),u[:4]))
  lp+=pt.sum(pm.logp(pm.Normal.dist(mu=np.float64(0),sigma=np.float64(1)),u[4:4+g]))
  lp+=pt.sum(pm.logp(pm.Normal.dist(mu=u[0],sigma=pt.exp(u[1])),u[4+g:k]))
  lp+=pt.sum(pm.logp(pm.Normal.dist(mu=np.float64(0),sigma=np.float64(1)),u[k:]))
  h=ar_path(u[k:],u[2],pt.exp(u[3]),np.float64(data['rho']),t,block_size)
  location=np.float64(.3)*u[4:4+g]+u[4+g:k]*np.array(x,copy=True)
  residual=np.array(y,copy=True)-location
  # Shared volatility term computed once per time, not broadcast over groups.
  likelihood=np.float64(t*g*constant)-np.float64(g/2)*pt.sum(h)
  likelihood-=np.float64((nu+1)/2)*pt.sum(pt.log1p(residual**2*pt.exp(-h[:,None])/np.float64(nu)))
  pm.Potential('normalized_mixed_flow',lp+likelihood)
 return model
