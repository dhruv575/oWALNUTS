"""Independent autodiff admission of an exact coordinate change."""
import hashlib,json,time
from pathlib import Path
import numpy as np
import bridgestan as bs
from bounded_rescaled_logspace import target

root=Path(__file__).resolve().parent;out=root/'STAN-COMPARISON.json'
if out.exists():raise FileExistsError(out)
started=time.monotonic()
names=['bounded_rescaled_logspace.py','bounded_scale_rescaled.stan','compare_bounded_logspace_stan.py']
sources={n:hashlib.sha256((root/n).read_bytes()).hexdigest() for n in names}
lib=bs.compile_model(root/'bounded_scale_rescaled.stan',make_args=['-j4']);rows=[]
for cap in [.5,1.,2.]:
 for n in [1,12,250]:
  for tied in [False,True]:
   y=np.zeros(n) if tied else .003*np.sin(.17*np.arange(n))+.001*np.cos(.61*np.arange(n))
   model=bs.StanModel(lib,data=dict(n=n,y=y.tolist(),cap=cap,rho=.95))
   for case,(mu,eta,b) in enumerate([(2*np.log(.005),-20.,0.),(2*np.log(.005),2.,.3),(-60.,-5.,.2),(-170.,-10.,-.2)]):
    q=np.r_[mu,eta,b,np.linspace(-1.,1.,n)]
    v,g=model.log_density_gradient(q,propto=False,jacobian=True)
    a,h=target(q,y,cap)
    np.testing.assert_allclose(a,v,rtol=1e-10,atol=1e-8)
    np.testing.assert_allclose(h,g,rtol=1e-8,atol=1e-7)
    rows.append(dict(cap=cap,n=n,tied=tied,case=case,density_error=abs(a-v),max_gradient_error=float(abs(h-g).max())))
assert sources=={n:hashlib.sha256((root/n).read_bytes()).hexdigest() for n in names}
r=dict(rows=rows,sources=sources,library_sha256=hashlib.sha256(Path(lib).read_bytes()).hexdigest(),elapsed_seconds=time.monotonic()-started,scope='72 deterministic coordinate-change checks; no sampling qualification')
out.write_text(json.dumps(r,indent=2)+'\n')
print(json.dumps(dict(cases=len(rows),max_density_error=max(x['density_error'] for x in rows),max_gradient_error=max(x['max_gradient_error'] for x in rows),elapsed_seconds=r['elapsed_seconds'])))
