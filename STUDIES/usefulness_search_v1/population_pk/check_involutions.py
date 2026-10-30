import json
from pathlib import Path
import numpy as np
from involutions import global_exchange,local_exchange,move
from native import Native,ROOT
b=Native();mode=np.array(json.loads((ROOT/'PREPARED.json').read_text())['mode']);rng=np.random.default_rng(931000001);rows=[]
for rep in range(4):
 x=mode+.1*rng.normal(size=43)
 for label,T in [('global',global_exchange)]+[(str(i),lambda q,i=i:local_exchange(q,i)) for i in range(12)]:
  y=T(x);error=float(np.max(abs(T(y)-x)));h=1e-5;J=np.empty((43,43))
  for j in range(43):
   e=np.zeros(43);e[j]=h;J[:,j]=(T(x+e)-T(x-e))/(2*h)
  sign,logdet=np.linalg.slogdet(J);lp=b.density(x);lq=b.density(y)
  assert error<1e-10 and abs(logdet)<1e-7 and sign!=0
  assert abs((lp+min(0.,lq-lp))-(lq+min(0.,lp-lq)))<1e-10
  rows.append(dict(rep=rep,transform=label,involution_error=error,log_abs_det=float(logdet)))
# Known unequal-weight mixture: random-walk MH composed with reflection MH.
# This distribution has mode mass .8 at +4, .2 at -4; both variance one.
def logp(x):return float(np.logaddexp(np.log(.8)-.5*(x[0]-4)**2,np.log(.2)-.5*(x[0]+4)**2))
occupancy=[];means=[]
for chain in range(4):
 x=np.array([(-4 if chain%2 else 4)],dtype=float);samples=[]
 for i in range(11000):
  proposal=x+rng.normal(size=1)
  if np.log(rng.random())<min(0,logp(proposal)-logp(x)):x=proposal
  x,_,_=move(x,logp,lambda z:-z,rng)
  if i>=1000:samples.append(float(x[0]))
 occupancy.append(float(np.mean(np.array(samples)>0)));means.append(float(np.mean(samples)))
assert max(abs(np.array(occupancy)-.8))<.03 and max(abs(np.array(means)-2.4))<.15
(ROOT/'INVOLUTION-CHECK.json').write_text(json.dumps(dict(rows=rows,known_mixture_positive_mass=occupancy,known_mixture_means=means),indent=2)+'\n')
b.close();print(json.dumps(dict(transforms_checked=len(rows),max_roundtrip=max(r['involution_error'] for r in rows),max_logdet=max(abs(r['log_abs_det']) for r in rows),known_mixture_positive_mass=occupancy,known_mixture_means=means)))
