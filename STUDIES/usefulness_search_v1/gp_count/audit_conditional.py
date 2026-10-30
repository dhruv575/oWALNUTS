import json
import numpy as np
from conditional import *
from common import ROOT
rng=np.random.default_rng(944000001)
for point in range(40):
 h=np.log([rng.uniform(2,10),rng.uniform(.5,4)]);rng.normal(size=D);L=kernel(h);z=np.zeros(D);history=[]
 for iteration in range(100):
  v,rate=objective(z,L);g=L.T@(K-rate)-z;H=np.eye(D)+(L.T*rate)@L
  if np.max(np.abs(g))<1e-7:break
  step=np.linalg.solve(H,g);slope=float(g@step);scale=1.
  for backtracks in range(40):
   candidate=z+scale*step;nv,_=objective(candidate,L)
   if np.isfinite(nv) and nv>=v+1e-4*scale*slope:z=candidate;break
   scale*=.5
  history.append(dict(iteration=iteration,value=v,gradient=float(np.max(np.abs(g))),step=float(np.max(np.abs(step))),newton_decrement=slope,backtracks=backtracks,scale=scale,difference=nv-v))
 else:
  r=dict(point=point,h=h.tolist(),history=history);(ROOT/'CONDITIONAL-FAILURE-AUDIT.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(dict(point=point,h=h.tolist(),last=history[-5:])));break
 rng.normal(size=D)
