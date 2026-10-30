import ast,hashlib,json
from pathlib import Path
import numpy as np
p=Path(__file__).resolve().parent;l=p/'local_recovery';r=l/'two_stage_calibrated01';r.mkdir(exist_ok=False)
source=(p/'two_stage_screen.py').read_text();assert hashlib.sha256(source.encode()).hexdigest()==json.loads((l/'two_stage_screen01/SUMMARY.json').read_text())['source_sha256']
for node in ast.parse(source).body:
    if isinstance(node,ast.FunctionDef) and node.name in ['evaluate','integrate']:exec(compile(ast.Module(body=[node],type_ignores=[]),'<frozen-screen-functions>','exec'))
def phase(n,seed,kind,c,d):
    rng=np.random.default_rng(seed);q=rng.normal(size=(n,d));variance=np.ones(d)
    if kind=='banana':q[:,1::2]+=c*(q[:,::2]**2-1);variance[1::2]=1+2*c*c
    else:q[:,0]*=3;q[:,1:]*=np.exp(q[:,0]/2)[:,None];variance[0]=9;variance[1:]=np.exp(4.5)
    mom=rng.normal(size=q.shape);lp,_=evaluate(q,kind,c);return q,mom,variance,-lp+.5*np.sum(mom*mom,axis=1)
def observe(q,mom,variance,initial,h,kind,c,b=None):
    with np.errstate(all='ignore'):
        x,v,lp=integrate(q,mom,h if b is None else 2*h,8 if b is None else 4,kind,c,b);error=-lp+.5*np.sum(v*v,axis=1)-initial;finite=np.isfinite(error)&np.isfinite(x).all(axis=1);accept=np.where(finite,np.exp(np.minimum(0,-error)),0.);jump=np.where(finite,np.sum((x-q)**2/variance,axis=1)/q.shape[1],0.);score=np.where(accept>0,accept*jump,0.)
    assert np.isfinite(score).all();return dict(deltaH=error,finite=finite,accept=accept,score=score)
rows=[];calibration=[]
for ti,(kind,c,d) in enumerate([('banana',2.,24),('banana',5.,24),('funnel',0.,10)]):
    q,mom,var,initial=phase(2048,944300001+ti,kind,c,d);np.savez_compressed(r/f'calibration-input-{ti}.npz',q=q,p=mom,variance=var);curve=[]
    for h in np.geomspace(.001,1.,48):curve.append(dict(h=float(h),accept=float(observe(q,mom,var,initial,h,kind,c)['accept'].mean())))
    crossing=next((i for i in range(1,len(curve)) if curve[i-1]['accept']>=.8 and curve[i]['accept']<.8),None);assert crossing is not None
    low=curve[crossing-1]['h'];high=curve[crossing]['h'];iterations=[]
    for _ in range(12):
        mid=(low+high)/2;a=float(observe(q,mom,var,initial,mid,kind,c)['accept'].mean());iterations.append(dict(h=mid,accept=a))
        if a>=.8:low=mid
        else:high=mid
    h=(low+high)/2;calibration.append(dict(target=kind,curvature=c,selected_h=h,curve=curve,iterations=iterations));(r/'CALIBRATION.json').write_text(json.dumps(calibration,indent=2))
    q,mom,var,initial=phase(16384,944400001+ti,kind,c,d);np.savez_compressed(r/f'validation-input-{ti}.npz',q=q,p=mom,variance=var);scores=[]
    for ai,(arm,b) in enumerate([('leapfrog',None),('bcss',(3-np.sqrt(3))/6),('minimum_norm',.1931833275037836)]):
        data=observe(q,mom,var,initial,h,kind,c,b);np.savez_compressed(r/f'validation-output-{ti}-{ai}.npz',**data);scores.append(data['score']);row=dict(target=kind,curvature=c,h=h,arm=arm,mean_acceptance=float(data['accept'].mean()),mean_accepted_normalized_jump=float(data['score'].mean()),finite_fraction=float(data['finite'].mean()))
        if ai:
            rng=np.random.default_rng(944500001+10*ti+ai);ratios=[]
            for _ in range(20):
                ix=rng.integers(0,16384,(100,16384));ratios.extend((scores[ai][ix].mean(axis=1)/scores[0][ix].mean(axis=1)).tolist())
            row.update(jump_ratio=float(scores[ai].mean()/scores[0].mean()),interval=np.quantile(ratios,[.025,.975]).tolist())
        rows.append(row);print(json.dumps(row),flush=True)
qualified=all(.7<=x['mean_acceptance']<=.9 for x in rows if x['arm']=='leapfrog');primary=rows[4];passed=qualified and primary['interval'][0]>1.05 and rows[1]['interval'][0]>.85 and rows[7]['interval'][0]>.85
(r/'SUMMARY.json').write_text(json.dumps(dict(completed=True,baseline_qualified=qualified,primary_passed=passed,rows=rows,source_hashes={n:hashlib.sha256((p/n).read_bytes()).hexdigest() for n in ['two_stage_screen.py','two_stage_calibrated.py','TWO-STAGE-CALIBRATED-PROTOCOL.md']}),indent=2,allow_nan=False)+'\n')
