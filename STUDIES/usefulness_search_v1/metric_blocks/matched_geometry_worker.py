import hashlib,json,sys,subprocess
from pathlib import Path
import numpy as np,arviz as az,bridgestan as bs
from native_common import LOCAL,STUDY,model_files
model=sys.argv[1];root=Path(sys.argv[2]);prefix=LOCAL/'native_prefix02'/model
ps=json.loads((prefix/'SUMMARY.json').read_text());assert ps['passed']
build=json.loads((LOCAL/'fixed_metric_build02/SUMMARY.json').read_text());binary=Path(build['binary']);assert hashlib.sha256(binary.read_bytes()).hexdigest()==build['binary_sha256']
so,data,source=model_files(model);refs=LOCAL/'localscaled01/REFERENCES.json';ref=json.loads(refs.read_text())[model];assert ref['passed']
with np.load(prefix/'short.npz') as z:short={k:z[k].copy() for k in z.files}
with np.load(prefix/'long.npz') as z:long={k:z[k].copy() for k in z.files}
configs=[];recovery=[]
for c in range(4):
    x=short['sample_stats__unconstrained_draw'][c];z=short['sample_stats__transformed_position'][c];g=short['sample_stats__gradient'][c];gz=short['sample_stats__transformed_gradient'][c]
    design=np.column_stack([z,np.ones(100)]);coef,_,rank,_=np.linalg.lstsq(design[:50],x[:50],rcond=None);A=coef[:-1].T;C=A@A.T
    residual=float(np.max(abs(design[50:]@coef-x[50:]))/(1+np.max(abs(x[50:]))));gr=float(np.max(abs(g@A-gz))/(1+np.max(abs(gz))))
    assert rank==x.shape[1]+1 and np.linalg.cond(design[:50])<1e8 and residual<1e-10 and gr<1e-10 and np.linalg.eigvalsh(C).min()>0
    mass=np.linalg.inv(C);mass=(mass+mass.T)/2;assert np.linalg.norm(C@mass-np.eye(len(C)))<1e-7
    configs.append(dict(start=x[-1].tolist(),mass=mass.ravel().tolist(),step_size=float(short['sample_stats__step_size'][c,-1]),seed=941850001+c))
    recovery.append(dict(chain=c,position_residual=residual,gradient_residual=gr,A=A.tolist(),mu=coef[-1].tolist()))
spec=dict(model=str(so),data=str(data),draws=2000,chains=configs);inp=root/'INPUT.json';out=root/'OUTPUT.json';inp.write_text(json.dumps(spec,indent=2)+'\n')
subprocess.run([str(binary),str(inp),str(out)],check=True,timeout=150);result=json.loads(out.read_text())
target=bs.StanModel(str(so),data=data.read_text(),seed=1)
def cname(n):
    p=n.split('.');return p[0]+'['+','.join(p[1:])+']' if len(p)>1 and all(s.isdigit() for s in p[1:]) else n
names=[cname(n) for n in target.param_names(include_tp=True,include_gq=False)];ix=[names.index(n) for n in ref['names']]
def assess(q,div,calls,workflow):
    assert q.shape[:2]==(4,2000) and np.isfinite(q).all();d=q.shape[-1]
    a=np.asarray([target.param_constrain(v,include_tp=True,include_gq=False)[ix] for v in q.reshape(-1,d)]).reshape(4,2000,-1)
    ds=az.convert_to_dataset({'p':a});mean=a.mean((0,1));sd=a.reshape(-1,a.shape[-1]).std(0,ddof=1);bulk=np.asarray(az.ess(ds,method='bulk').p);tail=np.asarray(az.ess(ds,method='tail').p);rh=np.asarray(az.rhat(ds,method='rank').p);mcse=np.asarray(az.mcse(ds,method='mean').p)
    z=abs(mean-ref['mean'])/np.sqrt(mcse**2+np.asarray(ref['mcse'])**2);delta=abs(mean-ref['mean'])/ref['sd'];se=abs(sd/ref['sd']-1)
    passed=all(np.isfinite(v).all() for v in [mean,sd,bulk,tail,rh,mcse,z,delta,se]) and max(rh)<=1.01 and min(bulk)>=400 and min(tail)>=400 and div==0 and max(z)<=4.5 and max(delta)<=.1 and max(se)<=.1
    return dict(passed=bool(passed),rhat=float(max(rh)),bulk=float(min(bulk)),tail=float(min(tail)),divergences=int(div),max_z=float(max(z)),max_mean_sd=float(max(delta)),max_sd_error=float(max(se)),continuation_calls=calls,workflow_calls=workflow,efficiency=float(min(bulk)/calls),workflow_efficiency=float(min(bulk)/workflow))
native=assess(long['sample_stats__unconstrained_draw'][:,100:],long['sample_stats__diverging'][:,100:].sum(),ps['continuation_gradient_calls'],ps['counts']['2100']['gradient'])
walnuts=assess(np.asarray([r['draws'] for r in result['chains']]),sum(r['retained_divergences'] for r in result['chains']),result['target_calls'],ps['counts']['100']['gradient']+result['target_calls'])
ratio={k:walnuts[k]/native[k] for k in ['efficiency','workflow_efficiency']} if native['passed'] and walnuts['passed'] else None
def clean(v):
    if isinstance(v,float) and not np.isfinite(v):return None
    if isinstance(v,dict):return {k:clean(x) for k,x in v.items()}
    if isinstance(v,list):return [clean(x) for x in v]
    return v
summary=dict(model=model,native=native,walnuts=walnuts,qualified_ratios=ratio,recovery=recovery,inputs={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in [Path(__file__),STUDY/'MATCHED-GEOMETRY-DIAGNOSTIC.md',prefix/'SUMMARY.json',prefix/'short.npz',prefix/'long.npz',refs,binary,so,data,source]})
(root/'SUMMARY.json').write_text(json.dumps(clean(summary),indent=2,allow_nan=False)+'\n');print(json.dumps(dict(model=model,ratios=ratio,native_pass=native['passed'],walnuts_pass=walnuts['passed'])))
