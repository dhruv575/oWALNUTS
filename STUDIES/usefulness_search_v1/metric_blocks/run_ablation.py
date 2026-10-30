import gzip,hashlib,json,sys,time,traceback
from pathlib import Path
import numpy as np
import arviz as az
import bridgestan as bs
from selector import select
root=Path(__file__).resolve().parent;old=root.parent/'model01'
binary=old/'source/STUDIES/metric_autoselect_confirmation_v1/target/release/online'
model='earnings-logearn_interaction';models=Path('/home/ubuntu/lanes/metric_autoselect_confirmation_v1/models')
so=models/(model+'_model.so');data=models/(model+'.data.json');rp=old/'REFERENCES.json'
ref=json.loads(rp.read_text())[model];assert ref['passed']
target=bs.StanModel(str(so),data=data.read_text(),seed=1);d=5
assert target.param_unc_names()==['beta.1','beta.2','beta.3','beta.4','sigma']
out=root/'runs';out.mkdir(exist_ok=False)
durable=Path('/home/ubuntu/lanes/metric-blocks-recovery-20261030/evidence/ablation01');durable.mkdir(exist_ok=False)
paths=[binary,so,data,rp,root/'run_ablation.py',root/'selector.py',root/'ABLATION-PROTOCOL.md']
inputs={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths};rows=[]
(root/'INPUTS.json').write_text(json.dumps(inputs,indent=2)+'\n')
sys.path.insert(0,'/home/ubuntu/lanes/pharma-ode-logforecast-20261029/source')
from resource_monitor import execute
def job(name,inp):
    folder=out/name;folder.mkdir();(folder/'INPUT.json').write_text(json.dumps(inp,indent=2)+'\n')
    r=execute([str(binary),str(folder/'INPUT.json'),str(folder/'RESULT.json')],str(root),180,folder,
        2*1024**3,64*1024**2,folder/'worker.log',output_scan_interval=2)
    (folder/'SUPERVISION.json').write_text(json.dumps(r,indent=2)+'\n')
    dest=durable/name;dest.mkdir();manifest={}
    for p in folder.iterdir():
        if p.is_file():
            raw=p.read_bytes();compressed=gzip.compress(raw,mtime=0);(dest/(p.name+'.gz')).write_bytes(compressed)
            manifest[p.name]=dict(bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest(),gzip_sha256=hashlib.sha256(compressed).hexdigest())
    (dest/'MANIFEST.json').write_text(json.dumps(manifest,indent=2)+'\n')
    if r['exit_code']!=0 or not r['group_drained']:return None
    return json.loads((folder/'RESULT.json').read_text())
def analyze(r,seed,arm,calls,seconds):
    if r is None:return dict(seed=seed,arm=arm,passed=False,error='job_failed')
    a=np.array(r['draws']);a[:,:,-1]=np.exp(a[:,:,-1]);ds=az.convert_to_dataset({'p':a})
    mean=a.mean((0,1));sd=a.reshape(-1,d).std(0,ddof=1)
    rh=np.asarray(az.rhat(ds,method='rank').p);bulk=np.asarray(az.ess(ds,method='bulk').p);tail=np.asarray(az.ess(ds,method='tail').p);mcse=np.asarray(az.mcse(ds,method='mean').p)
    z=np.abs(mean-ref['mean'])/np.sqrt(mcse**2+np.array(ref['mcse'])**2);delta=np.abs(mean-ref['mean'])/ref['sd'];se=np.abs(sd/ref['sd']-1)
    passed=rh.max()<=1.01 and min(bulk.min(),tail.min())>=400 and r['retained_divergences']==0 and z.max()<=4.5 and delta.max()<=.1 and se.max()<=.1
    return dict(seed=seed,arm=arm,passed=bool(passed),calls=calls,seconds=seconds,efficiency=float(bulk.min()/calls),
        rhat=float(rh.max()),bulk=float(bulk.min()),tail=float(tail.min()),divergences=r['retained_divergences'],
        max_z=float(z.max()),max_mean_sd=float(delta.max()),max_sd_error=float(se.max()),
        functionals=dict(mean=mean.tolist(),sd=sd.tolist(),rhat=rh.tolist(),bulk=bulk.tolist(),tail=tail.tolist(),mcse=mcse.tolist()))
begin=time.monotonic()
for seed in range(928600001,928600017):
    base=dict(model=str(so),data=str(data),starts=np.random.default_rng(seed).uniform(-2,2,(4,d)).tolist(),seed=seed,warmup=250,draws=100,arm='diag')
    pilot=job(f'{seed}-pilot',base)
    if pilot is None:
        rows.extend(dict(seed=seed,arm=arm,passed=False,error='pilot_failed') for arm in ['fixed_diag','empirical','curvature','dense','auto']);continue
    x=np.array(pilot['draws']);t=time.monotonic();emp=np.mean([np.cov(chain,rowvar=False,ddof=1) for chain in x],axis=0)
    v=np.maximum(np.diag(emp),1e-8);emp=400/405*emp+(.001*5/405)*np.eye(d);emp_time=time.monotonic()-t
    t=time.monotonic();coarse=[];fine=[];calls=0
    for chain in x:
        for q in chain[[0,24,49,99]]:
            hs=[]
            for step in [1e-4,5e-5]:
                h=np.empty((d,d))
                for j in range(d):
                    delta=np.eye(d)[j]*step*(1+abs(q[j]));_,gp=target.log_density_gradient(q+delta);_,gm=target.log_density_gradient(q-delta);calls+=2
                    h[:,j]=-(np.asarray(gp)-np.asarray(gm))/(2*delta[j])
                hs.append(h)
            coarse.append(hs[0]);fine.append(hs[1])
    cur,selection=select(coarse,fine,v);probe_time=time.monotonic()-t
    detail=dict(variances=v.tolist(),empirical=emp.tolist(),curvature=cur.tolist(),selection=selection,
        coarse=np.array(coarse).tolist(),fine=np.array(fine).tolist(),probe_calls=calls,probe_seconds=probe_time,empirical_seconds=emp_time)
    (root/f'{seed}-MATRICES.json').write_text(json.dumps(detail,indent=2)+'\n')
    for arm in ['fixed_diag','empirical','curvature','dense','auto']:
        try:
            inp=dict(base,starts=x[:,-1,:].tolist(),seed=seed+100000,warmup=750,draws=2000,arm=arm)
            setup=0.;extra=0
            if arm=='fixed_diag':inp['mass']=(1/v).tolist()
            if arm in ['empirical','curvature']:
                c=emp if arm=='empirical' else cur;m=np.linalg.inv(c);m=(m+m.T)/2
                assert np.isfinite(m).all() and np.linalg.eigvalsh(m).min()>0 and np.linalg.norm(c@m-np.eye(d))<=1e-7
                inp.update(arm='fixed_dense',mass=m.ravel().tolist());setup=emp_time if arm=='empirical' else probe_time;extra=0 if arm=='empirical' else calls
            r=job(f'{seed}-{arm}',inp)
            rows.append(analyze(r,seed,arm,pilot['target_calls']+extra+(r or {}).get('target_calls',0),pilot['seconds']+setup+(r or {}).get('seconds',0)))
        except Exception:rows.append(dict(seed=seed,arm=arm,passed=False,error=traceback.format_exc()))
    (root/'PROGRESS.json').write_text(json.dumps(rows,indent=2)+'\n')
result=dict(rows=rows,seconds=time.monotonic()-begin,inputs=inputs,
    unchanged=all(hashlib.sha256(Path(p).read_bytes()).hexdigest()==h for p,h in inputs.items()))
(root/'SUMMARY.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps([dict(seed=r['seed'],arm=r['arm'],passed=r['passed']) for r in rows]))
