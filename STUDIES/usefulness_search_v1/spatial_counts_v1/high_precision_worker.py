import hashlib,json,sys,time
from pathlib import Path
import numpy as np,mpmath as mp,bridgestan as bs
base=Path(__file__).resolve().parent;i=int(sys.argv[1]);out=base/'results'/str(i);cfg=json.loads((base/'GP-TRAIN.json').read_text());q=np.random.default_rng(952100001).normal(scale=.25,size=(8,205))[i];so=base/'spatial_gp_model.so';hashes=json.loads((base/'INPUT-HASHES.json').read_text());assert all(hashlib.sha256(Path(n).read_bytes()).hexdigest()==h for n,h in hashes.items());target=bs.StanModel(str(so),data=json.dumps(cfg),seed=1);value,gradient=target.log_density_gradient(q);start=time.perf_counter()
def evaluate(point,digits):
    with mp.workdps(digits):
        z=list(map(mp.mpf,point));rho,alpha=mp.exp(z[0]),mp.exp(z[1]);coords=[[mp.mpf(v) for v in row] for row in cfg['x']];n=cfg['N'];K=mp.matrix(n)
        for a in range(n):
            for b in range(a+1):
                distance=sum((u-v)**2 for u,v in zip(coords[a],coords[b]));v=alpha**2*mp.exp(-distance/(2*rho**2))+(mp.mpf('1e-10') if a==b else 0);K[a,b]=K[b,a]=v
        L=mp.cholesky(K);f=[]
        for a in range(n):f.append(sum(mp.mpf(cfg['design'][a][j])*mp.mpf(cfg['coef_scale'][j])*z[2+j] for j in range(3))+sum(L[a,j]*z[5+j] for j in range(a+1)))
        exposure=mp.mpf(cfg['exposure']);v=2*z[0]-rho+z[1]-alpha**2/8-sum(t*t for t in z[2:])/2+sum(mp.mpf(k)*(mp.log(exposure)+f[a])-exposure*mp.exp(f[a]) for a,k in enumerate(cfg['y']))
        return +v,[+x for x in f]
rows=[]
for coordinate in [0,1]:
    estimates=[]
    for digits,step in [(60,'0.00001'),(80,'0.000005')]:
        with mp.workdps(digits):
            h=mp.mpf(step);plus=list(map(mp.mpf,q));minus=list(map(mp.mpf,q));plus[coordinate]+=h;minus[coordinate]-=h;hi,_=evaluate(plus,digits);lo,_=evaluate(minus,digits);est=(hi-lo)/(2*h);estimates.append(dict(digits=digits,step=step,derivative=mp.nstr(est,digits),value=float(est)))
    fine=estimates[1]['value'];scale=max(1,abs(fine));convergence=abs(fine-estimates[0]['value'])/scale;aderror=abs(gradient[coordinate]-fine)/scale;rows.append(dict(coordinate=coordinate,estimates=estimates,compiled_ad=float(gradient[coordinate]),precision_step_agreement=convergence,ad_scaled_error=aderror))
truth,f=evaluate(q,80);names=target.param_names(include_tp=True,include_gq=False);ix=[names.index(f'f.{j}') for j in range(1,201)];actual=np.asarray(target.param_constrain(q,include_tp=True,include_gq=False))[ix];fe=float(max(abs(actual-np.array(list(map(float,f))))));ve=float(abs(value-float(truth)));checks=dict(derivatives=all(r['precision_step_agreement']<=1e-5 and r['ad_scaled_error']<=1e-3 for r in rows),functionals=fe<=1e-5,density=ve<=1e-5,finite=bool(np.isfinite(gradient).all() and np.isfinite(value)));result=dict(point=i,passed=bool(all(checks.values())),checks=checks,rows=rows,f_error=fe,density_error=ve,compiled_value=float(value),high_precision_value=mp.nstr(truth,80),seconds=time.perf_counter()-start,mpmath_version=mp.__version__,point_values=q.tolist());(out/'SUMMARY.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(dict(point=i,passed=result['passed'],seconds=result['seconds'])),flush=True)
