"""Deterministic callback parity admission, including ties and eta extremes."""
import hashlib,json,time
from pathlib import Path
import numpy as np
from bounded_scale_native import compile_target
from bounded_scale_sv import target

root=Path(__file__).resolve().parent;start=time.monotonic();rows=[]
sources={n:hashlib.sha256((root/n).read_bytes()).hexdigest() for n in ['bounded_scale_native.py','bounded_scale_sv.py','check_bounded_scale_native.py']}
for cap in [.5,1.,2.]:
 for n in [1,12,250]:
  for tied in [False,True]:
   y=np.zeros(n) if tied else .003*np.sin(.17*np.arange(n))+.001*np.cos(.61*np.arange(n))
   native=compile_target(y,cap)
   for eta in [-1000.,-20.,0.,2.,20.,1000.]:
    q=np.r_[2*np.log(.005),eta,0.,np.linspace(-1,1,n)]
    a,g=native.value_gradient(q);b,h=target(q,y,cap)
    np.testing.assert_allclose(a,b,rtol=1e-10,atol=1e-8)
    np.testing.assert_allclose(g,h,rtol=1e-8,atol=1e-7)
    rows.append(dict(cap=cap,n=n,tied=tied,eta=eta,density_abs_error=abs(a-b),gradient_max_abs_error=float(abs(g-h).max())))
   before=native.value_gradient(q);y[:]=42;after=native.value_gradient(q)
   assert before[0]==after[0] and np.array_equal(before[1],after[1])
   q[0]=np.nan;v,g=native.value_gradient(q);assert np.isnan(v) and np.isnan(g).all()
report=dict(rows=rows,sources=sources,immutable_snapshot=True,nonfinite_rejected=True,elapsed_seconds=time.monotonic()-start)
with (root/'NATIVE-PARITY.json').open('x') as f:json.dump(report,f,indent=2);f.write('\n')
print(json.dumps(dict(cases=len(rows),max_density_error=max(r['density_abs_error'] for r in rows),max_gradient_error=max(r['gradient_max_abs_error'] for r in rows),elapsed_seconds=report['elapsed_seconds'])))
