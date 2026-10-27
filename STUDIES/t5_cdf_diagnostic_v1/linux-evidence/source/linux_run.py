"""Fixed arithmetic-only Linux replay. External supervisor provides hard cap."""
import os
for key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):os.environ[key]='1'
import hashlib,json,sys,time,platform,importlib.metadata as metadata
from pathlib import Path
from datetime import datetime,timezone
START=time.perf_counter();H=Path(__file__).resolve().parent;ROOT=H.parent
OUT=ROOT/'result.json'
if OUT.exists():raise SystemExit('Refuse overwrite')
manifest=json.loads((H/'linux-manifest.json').read_text())
r=dict(status='running',started_utc=datetime.now(timezone.utc).isoformat(),planned_calls=24,rows=[],phase='imports')
def save():
    p=ROOT/'result.partial';p.write_text(json.dumps(r,indent=2));p.replace(OUT)
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def integrity():
    for name,want in manifest['sources'].items():assert sha(H/name)==want, name
    for name,want in manifest['inputs'].items():assert sha(ROOT/'data'/name)==want,name
save()
try:
    integrity()
    assert sys.prefix==manifest['prefix'],sys.prefix
    for name,want in manifest['packages'].items():assert metadata.version(name)==want,name
    for name,want in manifest['native_files'].items():assert sha(name)==want,name
    import numpy as np, scipy
    from scipy.special import stdtr
    from scipy.integrate import quad
    import processor_snapshot as processor
    t=time.perf_counter();import t5
    r['t5_import_jit_seconds']=time.perf_counter()-t
    r['imports_preflight_seconds']=time.perf_counter()-START
    r['runtime']=dict(executable=sys.executable,prefix=sys.prefix,python=sys.version,platform=platform.platform(),packages={k:metadata.version(k) for k in manifest['packages']},affinity=sorted(os.sched_getaffinity(0)),cpuinfo=Path('/proc/cpuinfo').read_text().split('\n\n')[0],native_files=manifest['native_files'])
    assert r['runtime']['affinity']==[0,1,2,3]
    r['phase']='tests';save();t=time.perf_counter()
    b=np.array([t5.SQRT5,4*t5.SQRT5]);b=np.r_[b,np.nextafter(b,0),np.nextafter(b,np.inf)]
    a=np.unique(np.sort(np.r_[np.linspace(-100,100,200001),np.logspace(-15,60,20001),-np.logspace(-15,60,20001),np.logspace(60,308,2001),-np.logspace(60,308,2001),b,-b,0,np.nextafter(0.,1.),-np.nextafter(0.,1.),np.finfo(float).max,-np.finfo(float).max]))
    f=t5.cdf(a);s=t5.sf(a);ref=stdtr(5,a);rs=stdtr(5,-a);q=t5.sf(abs(a));rq=stdtr(5,-abs(a));mask=rq>=1e-300
    tests=dict(grid_count=len(a),max_abs=float(max(np.max(abs(f-ref)),np.max(abs(s-rs)))),max_rel_tail=float(np.max(abs(q[mask]-rq[mask])/rq[mask])),cdf_decreases=int(np.sum(np.diff(f)<0)),sf_increases=int(np.sum(np.diff(s)>0)),symmetry=float(np.max(abs(f+s-1))),bounds=bool(np.all((f>=0)&(f<=1)&(s>=0)&(s<=1))))
    tests['special']=bool(t5.cdf(-np.inf)==0 and t5.cdf(np.inf)==1 and np.isnan(t5.cdf(np.nan)) and t5.cdf(0.)==.5 and t5.cdf(-0.)==.5)
    tests['known_error']=float(abs(t5.cdf(t5.SQRT5)-(.75+2/(3*np.pi))))
    tests['quad']=[]
    for x in [-100,-20,-8,-4,-1,-.1,0,.1,1,4,8,20,100]:
        ax=abs(x)
        if ax>=t5.SQRT5:q0,e=quad(lambda z:8/(3*np.pi)*z**4/(1+z*z)**3,0,t5.SQRT5/ax,epsabs=1e-15,epsrel=1e-13)
        else:
            val,e=quad(lambda z:8/(3*np.pi*np.sqrt(5))*(1+z*z/5)**-3,0,ax,epsabs=1e-15,epsrel=1e-13);q0=.5-val
        tests['quad'].append(dict(x=x,error=abs(float(t5.sf(ax))-q0),quad_error=e))
    tests['passed']=bool(tests['max_abs']<=5e-15 and tests['max_rel_tail']<=5e-12 and tests['cdf_decreases']==0 and tests['sf_increases']==0 and tests['symmetry']<=5e-15 and tests['bounds'] and tests['special'] and tests['known_error']<=5e-15 and all(x['error']<=5e-15 and x['quad_error']<=5e-15 for x in tests['quad']))
    r.update(tests=tests,tests_seconds=time.perf_counter()-t);save();assert tests['passed']
    arrays={i:np.load(ROOT/'data'/f'tick-{i:03d}.npy',allow_pickle=False) for i in range(1,5)}
    for a in arrays.values():assert a.shape==(4,400,4) and np.isfinite(a).all()
    for rep,ticks in enumerate(([4,3,2,1],[1,2,3,4],[4,3,2,1])):
        for tick in ticks:
            a=arrays[tick].reshape(-1,4);m=a[:,0]+.95*(a[:,3]-a[:,0]);sigma=np.exp(a[:,1]);beta=a[:,2]
            for name in (['exact','scipy'] if (rep+tick)%2==0 else ['scipy','exact']):
                call=f'{rep}:{tick}:{name}';r.update(phase='arithmetic',in_progress=call);save()
                row=dict(call=call,repetition=rep,tick=tick,implementation=name,status='failed');t=time.perf_counter()
                try:
                    processor.stdtr=stdtr if name=='scipy' else t5.stdtr5
                    cdfs=[processor.ReturnCDF(m,sigma,beta,5,n,START+180,64*1024*1024,512) for n in [64,128]]
                    rules=[c.quantiles() for c in cdfs]
                    discrepancy=max(abs(cdfs[0](q)-p) for p,q in zip(processor.PS,rules[1]['quantiles']))
                    width=rules[1]['quantiles'][2]-rules[1]['quantiles'][0]
                    endpoint=max(abs(x-y)/width for x,y in zip(rules[0]['quantiles'],rules[1]['quantiles']))
                    assert discrepancy<=1e-6 and endpoint<=1e-6
                    row.update(status='ok',rules=rules,cdf_discrepancy=discrepancy,normalized_endpoint_difference=endpoint)
                except Exception as exc:row['error']=repr(exc)
                row['seconds']=time.perf_counter()-t;r['rows'].append(row);r['in_progress']=None;save()
                if row['status']!='ok':raise RuntimeError('arithmetic call failed')
    integrity();r['postrun_integrity']=True;r['status']='complete'
except Exception as exc:r.update(status='failed',error=repr(exc))
finally:
    r.update(elapsed_seconds=time.perf_counter()-START,ended_utc=datetime.now(timezone.utc).isoformat());save()
