"""Bounded deterministic independent-target comparison; no posterior sampling."""
import hashlib,json,time
from pathlib import Path
import numpy as np
import bridgestan as bs
from price_cell_sv import target

root=Path(__file__).resolve().parent
started=time.monotonic()
sources={name:hashlib.sha256((root/name).read_bytes()).hexdigest() for name in
         ['price_cells.py','price_cell_sv.py','price_cell_sv.stan','compare_price_cell_stan.py']}
out=root/'STAN-COMPARISON.json'
if out.exists():raise FileExistsError(out)
lib=bs.compile_model(root/'price_cell_sv.stan',make_args=['-j4'])
rows=[]
for n in [1,4,12,250]:
 for case in range(4):
    lower=np.full(n,-.0005);upper=np.full(n,.0005)
    if case==1:upper+=np.linspace(0,.002,n)
    if case==2:lower=np.linspace(-.1,.1,n);upper=lower+1e-6
    mu=2*np.log(.005)+case-1
    q=np.r_[mu,np.log(.2)+.4*case,.0003*(case-1),np.linspace(-2,2,n),np.linspace(-5,5,n)]
    if case==3:q[3+n:]=np.resize([-40.,40.,-1000.,1000.],n)
    data=dict(n=n,lower_cell=lower.tolist(),upper_cell=upper.tolist(),initial=0.,rho=.95)
    model=bs.StanModel(lib,data=data)
    expected,eg=model.log_density_gradient(q,propto=False,jacobian=True)
    actual,ag=target(q,lower,upper,0.)
    np.testing.assert_allclose(actual,expected,atol=1e-8,rtol=1e-10)
    np.testing.assert_allclose(ag,eg,atol=1e-7,rtol=1e-8)
    rows.append(dict(n=n,case=case,dimensions=len(q),density_abs_error=abs(actual-expected),gradient_max_abs_error=float(np.max(np.abs(ag-eg)))))
assert sources=={name:hashlib.sha256((root/name).read_bytes()).hexdigest() for name in sources}
result=dict(scope='Deterministic finite fixtures only; not posterior fidelity or market-model validation',sources=sources,library_sha256=hashlib.sha256(Path(lib).read_bytes()).hexdigest(),rows=rows,elapsed_seconds=time.monotonic()-started)
with out.open('x') as f:json.dump(result,f,indent=2);f.write('\n')
print(json.dumps(result))
