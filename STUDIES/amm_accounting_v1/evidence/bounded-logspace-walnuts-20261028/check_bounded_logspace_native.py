"""Deterministic native admission for exact rescaled coordinates."""
import hashlib,json,time
from pathlib import Path
import numpy as np
from bounded_logspace_native import compile_target
from bounded_rescaled_logspace import target

root=Path(__file__).resolve().parent;started=time.monotonic();rows=[]
names=['bounded_scale_native.py','bounded_logspace_native.py','bounded_rescaled_logspace.py','check_bounded_logspace_native.py']
sources={n:hashlib.sha256((root/n).read_bytes()).hexdigest() for n in names}
for cap in [.5,1.,2.]:
 for n in [1,12,250]:
  for tied in [False,True]:
   y=np.zeros(n) if tied else .003*np.sin(.17*np.arange(n))+.001*np.cos(.61*np.arange(n));native=compile_target(y,cap)
   for case,(mu,eta,b) in enumerate([(2*np.log(.005),-1000.,0.),(2*np.log(.005),1000.,.3),(-60.,-5.,.2),(-170.,-10.,-.2)]):
    q=np.r_[mu,eta,b,np.linspace(-1.,1.,n)]
    a,g=native.value_gradient(q);v,h=target(q,y,cap)
    np.testing.assert_allclose(a,v,rtol=1e-10,atol=1e-8);np.testing.assert_allclose(g,h,rtol=1e-8,atol=1e-7)
    rows.append(dict(cap=cap,n=n,tied=tied,case=case,density_error=abs(a-v),max_gradient_error=float(abs(g-h).max())))
   before=native.value_gradient(q);y[:]=42;after=native.value_gradient(q)
   assert before[0]==after[0] and np.array_equal(before[1],after[1])
   q[0]=np.nan;v,g=native.value_gradient(q);assert np.isnan(v) and np.isnan(g).all()
capture=root/'CAPTURE.npz'
with np.load(capture) as f:q=f['capture'][1:];y=f['y']
owner=compile_target(y,.5);a,g=owner.value_gradient(q);v,h=target(q,y,.5)
np.testing.assert_allclose(a,v,rtol=1e-12,atol=.001);np.testing.assert_allclose(g,h,rtol=1e-9,atol=1e-8)
tail=[]
for mu,b in [(2000.,1.),(2000.,-1.),(2000.,0.),(-2000.,.3)]:
 q=np.r_[mu,2.,b,np.zeros(len(y))];a,g=owner.value_gradient(q)
 if mu>0 and b!=0:assert a==-np.inf and np.isnan(g).all()
 else:
  v,h=target(q,y,.5);np.testing.assert_allclose(a,v,rtol=1e-12,atol=1e-8);np.testing.assert_allclose(g,h,rtol=1e-8,atol=1e-7)
 tail.append(dict(mu=mu,b=b,classification='negative_log_density_overflow' if a==-np.inf else 'finite'))
r=dict(capture_sha256=hashlib.sha256(capture.read_bytes()).hexdigest(),capture_passed=True,tail_checks=tail,rows=rows,sources=sources,immutable_snapshot=True,nonfinite_rejected=True,elapsed_seconds=time.monotonic()-started)
with (root/'NATIVE-PARITY.json').open('x') as f:json.dump(r,f,indent=2);f.write('\n')
print(json.dumps(dict(cases=len(rows),max_density_error=max(x['density_error'] for x in rows),max_gradient_error=max(x['max_gradient_error'] for x in rows),elapsed_seconds=r['elapsed_seconds'])))
