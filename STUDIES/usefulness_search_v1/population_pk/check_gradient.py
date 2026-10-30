import json,time
from pathlib import Path
import numpy as np
from model import Population
rows=[]
for kind in ['linear','nonlinear']:
 m=Population(kind)
 for rep in range(2):
  x=m.start()+rep*.05*np.sin(np.arange(m.dim));lp,g=m.value(x);h=1e-5;fd=np.zeros(m.dim)
  for j in range(m.dim):
   e=np.zeros(m.dim);e[j]=h;fd[j]=(m.value(x+e)[0]-m.value(x-e)[0])/(2*h)
  err=float(np.max(np.abs(g-fd)/(1+np.abs(g))));rows.append(dict(kind=kind,rep=rep,dimension=m.dim,max_scaled_gradient_error=err));print(json.dumps(rows[-1]),flush=True)
  if err>=1e-4:
   j=int(np.argmax(np.abs(g-fd)/(1+np.abs(g))));print(dict(index=j,analytic=float(g[j]),finite_difference=float(fd[j])),flush=True)
  assert err<1e-4
 m.close()
Path('GRADIENT-CHECK.json').write_text(json.dumps(rows,indent=2)+'\n');print(json.dumps(rows))
