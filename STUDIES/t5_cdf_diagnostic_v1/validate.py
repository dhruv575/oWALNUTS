"""Fixed-plan validation; writes results even on threshold failure."""
import hashlib,json,math,platform,sys,time
from pathlib import Path
import numpy as np,scipy,numba,mpmath as mp
from scipy.special import stdtr
from scipy.integrate import quad
import t5
H=Path(__file__).resolve().parent
out=H/'validation.json'
if out.exists():raise SystemExit('Refuse overwrite')
start=time.perf_counter();mp.mp.dps=90
bounds=np.array([t5.SQRT5,4*t5.SQRT5])
b=np.concatenate([bounds,np.nextafter(bounds,0),np.nextafter(bounds,np.inf)])
a=np.r_[np.linspace(-100,100,200001),np.logspace(-15,60,20001),-np.logspace(-15,60,20001),np.logspace(60,308,2001),-np.logspace(60,308,2001),b,-b,0,np.nextafter(0.,1.),-np.nextafter(0.,1.),np.finfo(float).max,-np.finfo(float).max]
a=np.unique(np.sort(a));f=t5.cdf(a);s=t5.sf(a);ref=stdtr(5,a);rs=stdtr(5,-a)
q=t5.sf(np.abs(a));rq=stdtr(5,-np.abs(a));mask=rq>=1e-300
r=dict(grid_count=len(a),max_abs_cdf=float(np.max(abs(f-ref))),max_abs_sf=float(np.max(abs(s-rs))),max_rel_small_tail=float(np.max(abs(q[mask]-rq[mask])/rq[mask])),cdf_decreases=int(np.sum(np.diff(f)<0)),sf_increases=int(np.sum(np.diff(s)>0)),bounds_ok=bool(np.all((f>=0)&(f<=1)&(s>=0)&(s<=1))),max_symmetry_error=float(np.max(abs(f+s-1))),underflow_tail_count=int(np.sum(q==0)),relative_excluded_count=int(np.sum(~mask)))
r['special']=dict(negative_infinity=float(t5.cdf(-np.inf)),positive_infinity=float(t5.cdf(np.inf)),nan_preserved=bool(np.isnan(t5.cdf(np.nan))),zero=float(t5.cdf(0.)),negative_zero=float(t5.cdf(-0.)))
r['known_sqrt5_error']=float(abs(t5.cdf(t5.SQRT5)-(.75+2/(3*math.pi))))
r['quadrature']=[]
for x in [-100,-20,-8,-4,-1,-.1,0,.1,1,4,8,20,100]:
    ax=abs(x)
    if ax>=t5.SQRT5:
        q0,e=quad(lambda t:8/(3*math.pi)*t**4/(1+t*t)**3,0,t5.SQRT5/ax,epsabs=1e-15,epsrel=1e-13)
    else:
        v,e=quad(lambda z:8/(3*math.pi*math.sqrt(5))*(1+z*z/5)**-3,0,ax,epsabs=1e-15,epsrel=1e-13);q0=.5-v
    r['quadrature'].append(dict(x=x,abs_error=abs(float(t5.sf(ax))-q0),quad_error=e))
r['high_precision']=[]
for raw in ['.1','1',str(t5.SQRT5),str(4*t5.SQRT5),'20','100','1e4','1e20','1e50']:
    x=mp.mpf(raw);t=mp.sqrt(5)/x
    # Scale reciprocal integral to [0,1], including extremely small tails.
    exact=8/(3*mp.pi)*t**5*mp.quad(lambda u:u**4/(1+t*t*u*u)**3,[0,1])
    actual=mp.mpf(float(t5.sf(float(x))))
    r['high_precision'].append(dict(x=raw,tail=str(exact),relative_error=float(abs(actual-exact)/exact),absolute_error=float(abs(actual-exact))))
r['passed']=bool(r['max_abs_cdf']<=5e-15 and r['max_abs_sf']<=5e-15 and r['max_rel_small_tail']<=5e-12 and r['cdf_decreases']==0 and r['sf_increases']==0 and r['bounds_ok'] and all(x['relative_error']<=5e-12 for x in r['high_precision']) and all(x['abs_error']<=5e-15 for x in r['quadrature']))
r.update(elapsed_seconds=time.perf_counter()-start,python=sys.version,platform=platform.platform(),versions=dict(numpy=np.__version__,scipy=scipy.__version__,numba=numba.__version__,mpmath=mp.__version__),sources={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in [H/'PLAN.md',H/'t5.py',Path(__file__)]})
out.write_text(json.dumps(r,indent=2));print(json.dumps(r,indent=2));sys.exit(0 if r['passed'] else 1)
