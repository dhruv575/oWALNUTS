"""Deterministic native callback admission; no RNG or sampling."""
import hashlib,json,time
from pathlib import Path
import numpy as np
from price_cell_native import compile_target
from price_cell_sv import target

started=time.monotonic();rows=[];root=Path(__file__).resolve().parent
sources={n:hashlib.sha256((root/n).read_bytes()).hexdigest() for n in ['price_cell_native.py','price_cell_sv.py','price_cells.py','check_price_cell_native.py']}
for n in [1,12,250]:
 lo=np.full(n,-.0005);hi=np.full(n,.0005);native=compile_target(lo,hi)
 for case in range(4):
  q=np.r_[2*np.log(.005)+case,np.log(.2)+.2*case,.0002*case,np.linspace(-1,1,n),np.linspace(-4,4,n)]
  if case==3:q[3+n:]=np.resize([-1000.,1000.,-40.,40.],n)
  a,g=native.value_gradient(q);b,h=target(q,lo,hi,0.)
  np.testing.assert_allclose(a,b,rtol=1e-10,atol=1e-8);np.testing.assert_allclose(g,h,rtol=1e-8,atol=1e-7)
  rows.append(dict(n=n,case=case,dimension=len(q),density_abs_error=abs(a-b),gradient_max_abs_error=float(abs(g-h).max())))
 q=np.r_[2*np.log(.005),np.log(.2),0.,np.zeros(2*n)]
 before=native.value_gradient(q);lo[:]=-10;hi[:]=10;after=native.value_gradient(q)
 assert before[0]==after[0] and np.array_equal(before[1],after[1])
 q[0]=np.nan;value,gradient=native.value_gradient(q)
 assert np.isnan(value) and np.isnan(gradient).all()
out=root/'NATIVE-PARITY.json'
with out.open('x') as f:json.dump(dict(rows=rows,sources=sources,immutable_snapshot=True,nonfinite_rejected=True,elapsed_seconds=time.monotonic()-started),f,indent=2);f.write('\n')
print(out.read_text())
