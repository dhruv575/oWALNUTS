import hashlib,json,shutil,sys,time,traceback
from pathlib import Path
import numpy as np
import arviz as az
import bridgestan as bs
root=Path(__file__).resolve().parent;old=root.parent/'model01'
original=json.loads((old/'SUMMARY.json').read_text());assert original['unchanged']
refs=json.loads((old/'REFERENCES.json').read_text())
binary=old/'source/STUDIES/metric_autoselect_confirmation_v1/target/release/online'
out=root/'runs';out.mkdir(exist_ok=False)
durable=Path('/home/ubuntu/lanes/metric-blocks-recovery-20261030/evidence/model02');durable.mkdir(exist_ok=False)
sys.path.insert(0,'/home/ubuntu/lanes/pharma-ode-logforecast-20261029/source')
from resource_monitor import execute
inputs={};rows=[dict(r,provenance='reused original control; not independent replication') for r in original['rows'] if r['arm']!='candidate']
def record(p):inputs[str(p)]=hashlib.sha256(p.read_bytes()).hexdigest()
for p in [binary,old/'SUMMARY.json',old/'REFERENCES.json',root/'repair_models.py',root/'MASS-SYMMETRY-REPAIR.md']:record(p)
def cname(n):
    p=n.split('.');return p[0]+'['+','.join(p[1:])+']' if len(p)>1 and all(x.isdigit() for x in p[1:]) else n
begin=time.monotonic()
for cell in [r for r in original['rows'] if r['arm']=='candidate']:
    model=cell['model'];seed=cell['seed'];prefix=f'{model}-{seed}';folder=out/(prefix+'-candidate');folder.mkdir()
    try:
        ip=old/'runs'/(prefix+'-candidate')/'INPUT.json';sp=old/(prefix+'-SELECTION.json');pp=old/'runs'/(prefix+'-pilot')/'RESULT.json'
        for p in [ip,sp,pp]:record(p)
        inp=json.loads(ip.read_text());sel=json.loads(sp.read_text());pilot=json.loads(pp.read_text());c=np.array(sel['covariance'])
        m=np.array(sel['mass']);asym=float(np.linalg.norm(m-m.T)/np.linalg.norm(m));repaired=(m+m.T)/2
        residual=float(np.linalg.norm(c@repaired-np.eye(len(c))))
        audit=dict(original_mass=m.tolist(),repaired_mass=repaired.tolist(),relative_asymmetry=asym,
                   inverse_residual=residual,min_eigenvalue=float(np.linalg.eigvalsh(repaired).min()))
        (folder/'REPAIR.json').write_text(json.dumps(audit,indent=2)+'\n')
        assert asym<=1e-10 and residual<=1e-7 and np.isfinite(repaired).all() and audit['min_eigenvalue']>0
        if inp['arm']=='fixed_dense':inp['mass']=repaired.ravel().tolist()
        (folder/'INPUT.json').write_text(json.dumps(inp,indent=2)+'\n')
        r=execute([str(binary),str(folder/'INPUT.json'),str(folder/'RESULT.json')],str(root),180,folder,
            2*1024**3,64*1024**2,folder/'worker.log',output_scan_interval=2)
        (folder/'SUPERVISION.json').write_text(json.dumps(r,indent=2)+'\n')
        assert r['exit_code']==0 and r['group_drained'],r
        result=json.loads((folder/'RESULT.json').read_text());q=np.array(result['draws']);d=q.shape[-1]
        target=bs.StanModel(inp['model'],data=Path(inp['data']).read_text(),seed=1)
        for p in [Path(inp['model']),Path(inp['data'])]:record(p)
        names=[cname(n) for n in target.param_names(include_tp=True,include_gq=False)];rs=refs[model];ix=[names.index(n) for n in rs['names']]
        a=np.array([target.param_constrain(x,include_tp=True,include_gq=False)[ix] for x in q.reshape(-1,d)]).reshape(*q.shape[:2],-1)
        ds=az.convert_to_dataset({'p':a});mean=a.mean((0,1));sd=a.reshape(-1,len(ix)).std(0,ddof=1)
        rh=np.asarray(az.rhat(ds,method='rank').p);bulk=np.asarray(az.ess(ds,method='bulk').p);tail=np.asarray(az.ess(ds,method='tail').p);mcse=np.asarray(az.mcse(ds,method='mean').p)
        z=np.abs(mean-rs['mean'])/np.sqrt(mcse**2+np.array(rs['mcse'])**2)
        delta=np.abs(mean-rs['mean'])/rs['sd'];se=np.abs(sd/rs['sd']-1)
        calls=pilot['target_calls']+sel['probe_calls']+result['target_calls']
        passed=rs['passed'] and rh.max()<=1.01 and min(bulk.min(),tail.min())>=400 and result['retained_divergences']==0 and z.max()<=4.5 and delta.max()<=.1 and se.max()<=.1
        row=dict(model=model,seed=seed,arm='candidate',passed=bool(passed),reference_passed=rs['passed'],
            rhat=float(rh.max()),bulk=float(bulk.min()),tail=float(tail.min()),max_z=float(z.max()),
            max_mean_sd=float(delta.max()),max_sd_error=float(se.max()),divergences=result['retained_divergences'],calls=calls,
            efficiency=float(bulk.min()/calls),seconds=pilot['seconds']+sel['probe_seconds']+result['seconds'],
            selection=sel['selection'],repair=audit,functionals=dict(mean=mean.tolist(),sd=sd.tolist(),bulk=bulk.tolist(),tail=tail.tolist(),rhat=rh.tolist(),mcse=mcse.tolist()),mean_z=z.tolist(),mean_error_sd=delta.tolist(),sd_error=se.tolist())
    except Exception:row=dict(model=model,seed=seed,arm='candidate',passed=False,error=traceback.format_exc())
    rows.append(row);shutil.copytree(folder,durable/folder.name)
    (root/'PROGRESS.json').write_text(json.dumps(rows,indent=2)+'\n')
summary=dict(rows=rows,inputs=inputs,unchanged=all(hashlib.sha256(Path(p).read_bytes()).hexdigest()==h for p,h in inputs.items()),seconds=time.monotonic()-begin)
(root/'SUMMARY.json').write_text(json.dumps(summary,indent=2)+'\n');shutil.copy2(root/'SUMMARY.json',durable/'SUMMARY.json')
print(json.dumps([dict(model=r['model'],seed=r['seed'],passed=r['passed'],error=r.get('error')) for r in rows if r['arm']=='candidate']))
