"""Independent autodiff check of bounded-scale point-return candidate."""
import hashlib,json,time
from pathlib import Path
import numpy as np
import bridgestan as bs
from bounded_scale_sv import target

root=Path(__file__).resolve().parent;out=root/'STAN-COMPARISON.json'
if out.exists():raise FileExistsError(out)
started=time.monotonic();names=['bounded_scale_sv.py','bounded_scale_sv.stan','compare_bounded_scale_stan.py']
sources={n:hashlib.sha256((root/n).read_bytes()).hexdigest() for n in names}
lib=bs.compile_model(root/'bounded_scale_sv.stan',make_args=['-j4']);rows=[]
for cap in (.5,1.,2.):
 for n in (1,4,12,250):
  for case in range(4):
    y=np.zeros(n) if case<2 else .003*np.sin(np.arange(n)*.17)
    q=np.r_[2*np.log(.005),[-20.,0.,2.,20.][case],0. if case==0 else .0002,np.linspace(-1.,1.,n)]
    model=bs.StanModel(lib,data=dict(n=n,y=y.tolist(),cap=cap,rho=.95))
    expected,eg=model.log_density_gradient(q,propto=False,jacobian=True)
    actual,ag=target(q,y,cap)
    np.testing.assert_allclose(actual,expected,rtol=1e-10,atol=1e-8)
    np.testing.assert_allclose(ag,eg,rtol=1e-8,atol=1e-7)
    rows.append(dict(cap=cap,n=n,case=case,density_error=abs(actual-expected),max_gradient_error=float(abs(ag-eg).max())))
assert sources=={n:hashlib.sha256((root/n).read_bytes()).hexdigest() for n in names}
r=dict(rows=rows,sources=sources,library_sha256=hashlib.sha256(Path(lib).read_bytes()).hexdigest(),elapsed_seconds=time.monotonic()-started,scope='48 deterministic target checks including exact ties; no posterior or market validation')
out.write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r))
