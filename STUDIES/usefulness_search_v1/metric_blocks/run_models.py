import hashlib,json,shutil,sys,time,traceback,zipfile
from pathlib import Path
import numpy as np
import arviz as az
import bridgestan as bs
from selector import select
root=Path(__file__).resolve().parent
binary=root/'source/STUDIES/metric_autoselect_confirmation_v1/target/release/online'
models=Path('/home/ubuntu/lanes/metric_autoselect_confirmation_v1/models')
pdb=Path('/home/ubuntu/infra/posteriordb/posterior_database')
out=root/'runs';out.mkdir(exist_ok=False)
durable=Path('/home/ubuntu/lanes/metric-blocks-recovery-20261030/evidence/model01');durable.mkdir(exist_ok=False)
sys.path.insert(0,'/home/ubuntu/lanes/pharma-ode-logforecast-20261029/source')
from resource_monitor import execute
inputs={};rows=[];refs={};dependencies=root/'dependencies';dependencies.mkdir()
def record(path):
    inputs[str(path)]=hashlib.sha256(path.read_bytes()).hexdigest()
def persist(name,data):
    (root/name).write_text(json.dumps(data,indent=2,allow_nan=False)+'\n')
    shutil.copy2(root/name,durable/name)
for path in [binary,root/'run_models.py',root/'selector.py',root/'MODEL-SCREEN.md',root/'online.rs']:record(path)
assert json.loads((root/'BUILD.json').read_text())['exit_code']==0
def stats(a):
    ds=az.convert_to_dataset({'p':a})
    return dict(mean=a.mean(axis=(0,1)),sd=a.reshape(-1,a.shape[-1]).std(axis=0,ddof=1),
        bulk=np.asarray(az.ess(ds,method='bulk').p),tail=np.asarray(az.ess(ds,method='tail').p),
        rhat=np.asarray(az.rhat(ds,method='rank').p),mcse=np.asarray(az.mcse(ds,method='mean').p))
def good(s):
    return bool(all(np.isfinite(x).all() for x in s.values()) and s['rhat'].max()<=1.01 and min(s['bulk'].min(),s['tail'].min())>=400)
def job(name,inp):
    folder=out/name;folder.mkdir();(folder/'INPUT.json').write_text(json.dumps(inp,indent=2)+'\n')
    r=execute([str(binary),str(folder/'INPUT.json'),str(folder/'RESULT.json')],str(root),180,
        folder,2*1024**3,64*1024**2,folder/'worker.log',output_scan_interval=2)
    (folder/'SUPERVISION.json').write_text(json.dumps(r,indent=2)+'\n');shutil.copytree(folder,durable/name)
    if r['exit_code']!=0 or not r['group_drained']:return None
    return json.loads((folder/'RESULT.json').read_text())
def cname(n):
    parts=n.split('.');return parts[0]+'['+','.join(parts[1:])+']' if len(parts)>1 and all(p.isdigit() for p in parts[1:]) else n
begin=time.monotonic()
for model in ['earnings-logearn_interaction','kidiq-kidscore_momhsiq','garch-garch11','gp_pois_regr-gp_pois_regr']:
    so=models/(model+'_model.so');data=models/(model+'.data.json')
    info=pdb/'posteriors'/f'{model}.json';record(info)
    refpath=pdb/'reference_posteriors/draws/draws'/(json.loads(info.read_text())['reference_posterior_name']+'.json.zip')
    for path in [so,data,models/(model+'.stan'),info,refpath]:
        record(path);shutil.copy2(path,dependencies/(str(len(list(dependencies.iterdir())))+'-'+path.name))
    with zipfile.ZipFile(refpath) as z:ref=json.loads(z.read(z.namelist()[0]))
    names=list(ref[0]);a=np.asarray([[c[n] for n in names] for c in ref]).transpose(0,2,1);rs=stats(a)
    target=bs.StanModel(str(so),data=data.read_text(),seed=1)
    cn=[cname(n) for n in target.param_names(include_tp=True,include_gq=False)];ix=[cn.index(n) for n in names]
    d=len(target.param_unc_names())
    refs[model]=dict(names=names,passed=good(rs),**{k:v.tolist() for k,v in rs.items()})
    persist('REFERENCES.json',refs)
    def analyze(result,seed,arm,calls,seconds,selection=None):
        if result is None:return dict(model=model,seed=seed,arm=arm,passed=False,error='job_failed')
        q=np.array(result['draws']);flat=q.reshape(-1,d)
        a=np.array([target.param_constrain(x,include_tp=True,include_gq=False)[ix] for x in flat]).reshape(*q.shape[:2],-1)
        s=stats(a);z=np.abs(s['mean']-rs['mean'])/np.sqrt(s['mcse']**2+rs['mcse']**2)
        delta=np.abs(s['mean']-rs['mean'])/rs['sd'];sd_error=np.abs(s['sd']/rs['sd']-1)
        passed=good(rs) and good(s) and result['retained_divergences']==0 and z.max()<=4.5 and delta.max()<=.1 and sd_error.max()<=.1
        return dict(model=model,seed=seed,arm=arm,passed=bool(passed),reference_passed=good(rs),
            rhat=float(s['rhat'].max()),bulk=float(s['bulk'].min()),tail=float(s['tail'].min()),
            divergences=result['retained_divergences'],max_z=float(z.max()),max_mean_sd=float(delta.max()),
            max_sd_error=float(sd_error.max()),calls=calls,seconds=seconds,selection=selection,
            efficiency=float(s['bulk'].min()/calls),functionals={k:v.tolist() for k,v in s.items()},
            mean_z=z.tolist(),mean_error_sd=delta.tolist(),sd_error=sd_error.tolist())
    for seed in range(928400001,928400005):
        prefix=f'{model}-{seed}';starts=np.random.default_rng(seed).uniform(-2,2,(4,d)).tolist()
        base=dict(model=str(so),data=str(data),starts=starts,seed=seed,warmup=1100,draws=2000)
        pilot=job(prefix+'-pilot',dict(base,warmup=250,draws=100,arm='diag'))
        try:
            if pilot is None:raise RuntimeError('pilot failed')
            x=np.array(pilot['draws']);v=np.maximum(x.var(axis=1,ddof=1).mean(0),1e-8)
            coarse=[];fine=[];calls=0;probe_start=time.monotonic()
            for chain in x:
                for q in chain[[0,24,49,99]]:
                    matrices=[]
                    for step in [1e-4,5e-5]:
                        h=np.empty((d,d))
                        for j in range(d):
                            delta=np.eye(d)[j]*step*(1+abs(q[j]))
                            _,gp=target.log_density_gradient(q+delta);_,gm=target.log_density_gradient(q-delta);calls+=2
                            h[:,j]=-(np.asarray(gp)-np.asarray(gm))/(2*delta[j])
                        matrices.append(h)
                    coarse.append(matrices[0]);fine.append(matrices[1])
            c,selection=select(coarse,fine,v);mass=np.linalg.inv(c);probe_seconds=time.monotonic()-probe_start
            detail=dict(variances=v.tolist(),coarse=np.array(coarse).tolist(),fine=np.array(fine).tolist(),
                covariance=c.tolist(),mass=mass.tolist(),selection=selection,probe_calls=calls,probe_seconds=probe_seconds)
            persist(prefix+'-SELECTION.json',detail)
            arm='fixed_dense' if selection['blocks'] else 'fixed_diag'
            candidate=job(prefix+'-candidate',dict(base,starts=x[:,-1,:].tolist(),seed=seed+100000,warmup=750,
                arm=arm,mass=mass.ravel().tolist() if selection['blocks'] else np.diag(mass).tolist()))
            rows.append(analyze(candidate,seed,'candidate',pilot['target_calls']+calls+(candidate or {}).get('target_calls',0),
                pilot['seconds']+probe_seconds+(candidate or {}).get('seconds',0),selection))
        except Exception:
            rows.append(dict(model=model,seed=seed,arm='candidate',passed=False,error=traceback.format_exc()))
        for arm in ['diag','dense','auto']:
            r=job(prefix+'-'+arm,dict(base,arm=arm))
            rows.append(analyze(r,seed,arm,(r or {}).get('target_calls',0),(r or {}).get('seconds',0)))
        persist('PROGRESS.json',rows)
persist('SUMMARY.json',dict(rows=rows,seconds=time.monotonic()-begin,inputs=inputs,
    unchanged=all(hashlib.sha256(Path(p).read_bytes()).hexdigest()==h for p,h in inputs.items())))
print(json.dumps([dict(model=r['model'],seed=r['seed'],arm=r['arm'],passed=r['passed'],selection=r.get('selection')) for r in rows]))
