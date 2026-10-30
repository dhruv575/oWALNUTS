import ast,hashlib,json
from pathlib import Path
import numpy as np
p=Path(__file__).resolve().parent;l=p/'local_recovery';r=l/'rknf_leaf_screen01';r.mkdir(exist_ok=False);source=(p/'two_stage_screen.py').read_text();assert hashlib.sha256(source.encode()).hexdigest()==json.loads((l/'two_stage_screen01/SUMMARY.json').read_text())['source_sha256']
for node in ast.parse(source).body:
    if isinstance(node,ast.FunctionDef) and node.name=='evaluate':exec(compile(ast.Module(body=[node],type_ignores=[]),'<verified-target>','exec'))
def attempt(q,p0,g0,lp0,h,n,kind,c,mode,delta):
    q=q.copy();mom=p0.copy();g=g0.copy();lp=lp0.copy();initial=-lp0+.5*np.sum(p0*p0,axis=1);active=np.ones(len(q),bool);work=np.zeros(len(q),int);error=np.zeros(len(q));eps=h/n
    with np.errstate(all='ignore'):
        for _ in range(n):
            ix=np.flatnonzero(active)
            if not len(ix):break
            a=q[ix];v=mom[ix];ga=g[ix];b=a+eps*v+.5*eps*eps*ga;lb,gb=evaluate(b,kind,c);w=v+.5*eps*(ga+gb);work[ix]+=1;finite=np.isfinite(lb)&np.isfinite(gb).all(1)&np.isfinite(w).all(1)
            if mode=='RKNF':
                mid=.5*(a+b)+eps/8*(v-w);_,gm=evaluate(mid,kind,c);work[ix]+=1
                bf=a+eps*v+eps*eps*(ga/3+gb/6);wf=v+eps*(ga/6+2*gm/3+gb/6);ab=b-eps*w+eps*eps*(gb/3+ga/6);vb=-w+eps*(gb/6+2*gm/3+ga/6)
                e=np.max(np.concatenate([abs(b-bf),abs(w-wf),abs(a-ab),abs(-v-vb)],axis=1),axis=1);error[ix]=np.maximum(error[ix],e);finite &= np.isfinite(e)&(e<delta)
            q[ix]=b;mom[ix]=w;g[ix]=gb;lp[ix]=lb;active[ix]=finite
        if mode=='H':error=np.abs(-lp+.5*np.sum(mom*mom,axis=1)-initial);active &= np.isfinite(error)&(error<delta)
    return q,mom,g,lp,error,active,work
def leaf(q,p0,h,kind,c,mode,delta):
    lp0,g0=evaluate(q,kind,c);n=len(q);work=np.ones(n,int);levels=np.full(n,-1,int);endpoint=q.copy();momentum=p0.copy();ge=g0.copy();lpe=lp0.copy();pending=np.ones(n,bool)
    for level in range(8):
        ix=np.flatnonzero(pending)
        if not len(ix):break
        a,b,g,lp,err,ok,calls=attempt(q[ix],p0[ix],g0[ix],lp0[ix],h,2**level,kind,c,mode,delta);work[ix]+=calls;take=ix[ok];endpoint[take]=a[ok];momentum[take]=b[ok];ge[take]=g[ok];lpe[take]=lp[ok];levels[take]=level;pending[take]=False
    rejected=np.zeros(n,bool)
    for lower in range(7):
        ix=np.flatnonzero((levels>lower)&~rejected)
        if not len(ix):break
        *_,ok,calls=attempt(endpoint[ix],-momentum[ix],ge[ix],lpe[ix],h,2**lower,kind,c,mode,delta);work[ix]+=calls;rejected[ix[ok]]=True
    valid=(levels>=0)&~rejected;error=-lpe+.5*np.sum(momentum*momentum,axis=1)+lp0-.5*np.sum(p0*p0,axis=1)
    return dict(q=endpoint,p=momentum,level=levels,work=work,reverse_rejected=rejected,valid=valid,deltaH=error)
def phase(n,seed,kind,c,d):
    rng=np.random.default_rng(seed);q=rng.normal(size=(n,d));var=np.ones(d)
    if kind=='banana':q[:,1::2]+=c*(q[:,::2]**2-1);var[1::2]=1+2*c*c
    if kind=='funnel':q[:,0]*=3;q[:,1:]*=np.exp(q[:,0]/2)[:,None];var[0]=9;var[1:]=np.exp(4.5)
    return q,rng.normal(size=q.shape),var
q=np.array([[.2,-.3,.1,.4]]);mom=np.array([[.1,.3,-.4,.2]]);lp,g=evaluate(q,'banana',5.);a=attempt(q,mom,g,lp,.01,1,'banana',5.,'RKNF',np.inf);b=attempt(a[0],-a[1],a[2],a[3],.01,1,'banana',5.,'RKNF',np.inf);assert np.max(abs(b[0]-q))<1e-10 and np.max(abs(b[1]+mom))<1e-10 and np.max(abs(a[4]-b[4]))<1e-10;rows=[];verification_calls=0
for ti,(kind,c,d,h) in enumerate([('gaussian',0.,24,1.),('banana',5.,24,.1),('funnel',0.,10,.5)]):
    cq,cp,_=phase(2048,947100001+ti,kind,c,d);lp,g=evaluate(cq,kind,c);ha=attempt(cq,cp,g,lp,h,1,kind,c,'H',1.);ra=attempt(cq,cp,g,lp,h,1,kind,c,'RKNF',np.inf);fraction=float(ha[5].mean());assert .05<=fraction<=.95;delta=float(np.quantile(ra[4],fraction));assert np.isfinite(delta) and delta>0;np.savez_compressed(r/f'calibration-{ti}.npz',q=cq,p=cp,herror=ha[4],rerror=ra[4]);q,mom,var=phase(8192,947200001+ti,kind,c,d);np.savez_compressed(r/f'input-{ti}.npz',q=q,p=mom,variance=var);arms=[]
    for mode,tol in [('H',1.),('RKNF',delta)]:
        result=leaf(q,mom,h,kind,c,mode,tol)
        with np.errstate(all='ignore'):score=np.where(result['valid'],np.exp(np.minimum(0,-result['deltaH']))*np.mean((result['q']-q)**2/var,axis=1),0.)
        assert np.isfinite(score).all();result['score']=score;np.savez_compressed(r/f'output-{ti}-{mode}.npz',**result);ix=np.flatnonzero(result['valid'])[:256];back=leaf(result['q'][ix],-result['p'][ix],h,kind,c,mode,tol);verification_calls+=int(back['work'].sum());assert back['valid'].all() and np.array_equal(back['level'],result['level'][ix]);assert np.max(abs(back['q']-q[ix]))<1e-7 and np.max(abs(back['p']+mom[ix]))<1e-7;arms.append(result)
    ratio=float((arms[1]['score'].mean()/arms[1]['work'].mean())/(arms[0]['score'].mean()/arms[0]['work'].mean()));rng=np.random.default_rng(947300001+ti);ratios=[]
    for _ in range(20):
        ix=rng.integers(0,8192,(100,8192));ratios.extend(((arms[1]['score'][ix].mean(1)/arms[1]['work'][ix].mean(1))/(arms[0]['score'][ix].mean(1)/arms[0]['work'][ix].mean(1))).tolist())
    row=dict(target=kind,curvature=c,h=h,calibration_h_level0_pass_fraction=fraction,rknf_delta=delta,score_per_call_ratio=ratio,interval=np.quantile(ratios,[.025,.975]).tolist(),arms={mode:dict(mean_calls=float(a['work'].mean()),valid_fraction=float(a['valid'].mean()),exhaustion_fraction=float((a['level']<0).mean()),reverse_rejection_fraction=float(a['reverse_rejected'].mean()),mean_score=float(a['score'].mean())) for mode,a in zip(['H','RKNF'],arms)});rows.append(row);print(json.dumps(row),flush=True)
passed=rows[1]['interval'][0]>1.1 and rows[1]['arms']['RKNF']['reverse_rejection_fraction']<rows[1]['arms']['H']['reverse_rejection_fraction'] and rows[2]['score_per_call_ratio']>=.9
(r/'SUMMARY.json').write_text(json.dumps(dict(completed=True,screen_passed=passed,rows=rows,verification_gradient_calls=verification_calls,source_hashes={n:hashlib.sha256((p/n).read_bytes()).hexdigest() for n in ['rknf_leaf_screen.py','RKNF-LEAF-PROTOCOL.md','two_stage_screen.py']}),indent=2,allow_nan=False)+'\n')
