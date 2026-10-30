import hashlib,json
from pathlib import Path
import numpy as np
p=Path(__file__).resolve().parent;r=p/'local_recovery/two_stage_screen01';r.mkdir(exist_ok=False)
def evaluate(q,kind,c=0.):
    if kind=='gaussian':return -.5*np.sum(q*q,axis=-1),-q
    if kind=='banana':
        a=q[...,::2];b=q[...,1::2]-c*(a*a-1);g=np.empty_like(q);g[...,::2]=-a+2*c*a*b;g[...,1::2]=-b
        return -.5*np.sum(a*a+b*b,axis=-1),g
    v=np.exp(-q[...,0]);s=np.sum(q[...,1:]**2,axis=-1);g=np.empty_like(q);g[...,0]=-q[...,0]/9-.5*(q.shape[-1]-1)+.5*v*s;g[...,1:]=-q[...,1:]*v[...,None]
    return -.5*q[...,0]**2/9-.5*(q.shape[-1]-1)*q[...,0]-.5*v*s,g
def integrate(q,p0,h,n,kind,c=0.,b=None):
    q=q.copy();v=p0.copy();lp,g=evaluate(q,kind,c)
    for _ in range(n):
        if b is None:
            v+=.5*h*g;q+=h*v;lp,g=evaluate(q,kind,c);v+=.5*h*g
        else:
            v+=b*h*g;q+=.5*h*v;lp,g=evaluate(q,kind,c);v+=(1-2*b)*h*g;q+=.5*h*v;lp,g=evaluate(q,kind,c);v+=b*h*g
    return q,v,lp
checks=[]
for kind,c in [('gaussian',0.),('banana',2.),('funnel',0.)]:
    q=np.array([[.2,-.3]]);mom=np.array([[.4,.1]]);lp,g=evaluate(q,kind,c);fd=[]
    for j in range(2):
        d=np.zeros_like(q);d[0,j]=1e-6;fd.append(float((evaluate(q+d,kind,c)[0]-evaluate(q-d,kind,c)[0])[0]/2e-6))
    assert np.max(np.abs(g[0]-fd))<1e-5
    for b in [None,.25,(3-np.sqrt(3))/6,.1931833275037836]:
        x,v,_=integrate(q,mom,.01,4,kind,c,b);z,w,_=integrate(x,v,-.01,4,kind,c,b);error=max(np.max(abs(z-q)),np.max(abs(w-mom)));assert error<1e-8
        def mapping(a):
            x,v,_=integrate(a[:2][None,:],a[2:][None,:],.01,4,kind,c,b);return np.r_[x[0],v[0]]
        init=np.r_[q[0],mom[0]];jac=np.column_stack([(mapping(init+np.eye(4)[j]*1e-6)-mapping(init-np.eye(4)[j]*1e-6))/2e-6 for j in range(4)]);det=float(np.linalg.det(jac));assert abs(det-1)<1e-5;checks.append(dict(target=kind,b=b,reversal_error=float(error),determinant=det))
    a=integrate(q,mom,.01,8,kind,c);b=integrate(q,mom,.02,4,kind,c,.25);assert all(np.allclose(x,y,rtol=0,atol=1e-13) for x,y in zip(a,b))
(r/'CHECKS.json').write_text(json.dumps(checks,indent=2));rows=[];coefficients=[None,(3-np.sqrt(3))/6,.1931833275037836];names=['leapfrog','bcss','minimum_norm']
for ti,(kind,c,d) in enumerate([('gaussian',0.,24),('banana',2.,24),('banana',5.,24),('funnel',0.,10)]):
    rng=np.random.default_rng(944100001+ti);q=rng.normal(size=(8192,d));variance=np.ones(d)
    if kind=='banana':q[:,1::2]+=c*(q[:,::2]**2-1);variance[1::2]=1+2*c*c
    if kind=='funnel':q[:,0]*=3;q[:,1:]*=np.exp(q[:,0]/2)[:,None];variance[0]=9;variance[1:]=np.exp(4.5)
    mom=rng.normal(size=q.shape);lp,_=evaluate(q,kind,c);initial=-lp+.5*np.sum(mom*mom,axis=1);np.savez_compressed(r/f'inputs-{ti}.npz',q=q,p=mom,variance=variance)
    for si,h in enumerate([.25,.5,1.,1.5] if kind=='gaussian' else [.01,.03,.1,.3]):
        observations=[]
        for ai,b in enumerate(coefficients):
            with np.errstate(over='ignore',invalid='ignore',divide='ignore',under='ignore'):
                x,v,lp=integrate(q,mom,h if b is None else 2*h,8 if b is None else 4,kind,c,b);error=-lp+.5*np.sum(v*v,axis=1)-initial;finite=np.isfinite(error)&np.isfinite(x).all(axis=1);accept=np.where(finite,np.exp(np.minimum(0,-error)),0.);jump=np.where(finite,np.sum((x-q)**2/variance,axis=1)/d,0.);score=np.where(accept>0,accept*jump,0.)
            assert np.isfinite(score).all();np.savez_compressed(r/f'outputs-{ti}-{si}-{ai}.npz',deltaH=error,finite=finite,accept=accept,score=score);observations.append(score)
            row=dict(target=kind,curvature=c,h=h,arm=names[ai],mean_acceptance=float(accept.mean()),finite_fraction=float(finite.mean()),mean_accepted_normalized_jump=float(score.mean()),finite_absolute_energy_quantiles=np.quantile(abs(error[finite]),[.5,.9,.99]).tolist() if finite.any() else None)
            if ai:
                bootrng=np.random.default_rng(944200001+100*ti+10*si+ai);ratios=[]
                for _ in range(20):
                    ix=bootrng.integers(0,8192,(100,8192));ratios.extend((score[ix].mean(axis=1)/observations[0][ix].mean(axis=1)).tolist())
                row.update(jump_ratio=float(score.mean()/observations[0].mean()),interval=np.quantile(ratios,[.025,.975]).tolist())
            rows.append(row);print(json.dumps(row),flush=True)
eligible=[]
for arm in names[1:]:
    comparisons=[]
    for row in rows:
        if row['arm']!=arm or row['target']=='gaussian':continue
        base=next(x for x in rows if x['arm']=='leapfrog' and all(x[k]==row[k] for k in ['target','curvature','h']))
        if .5<=base['mean_acceptance']<=.95:comparisons.append(row)
    if any(x['interval'][0]>1.05 for x in comparisons) and not any(x['interval'][1]<.85 for x in comparisons):eligible.append(arm)
(r/'SUMMARY.json').write_text(json.dumps(dict(completed=True,eligible_for_rust_followup=eligible,rows=rows,source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),protocol_sha256=hashlib.sha256((p/'TWO-STAGE-PROTOCOL.md').read_bytes()).hexdigest()),indent=2)+'\n')
