import hashlib,json,sys,time,shutil
from pathlib import Path
import numpy as np
import arviz as az
from selector_full_shape import select
root=Path(__file__).resolve().parent;work=root.parent;out=root/'runs';out.mkdir(exist_ok=False)
sys.path.insert(0,'/home/ubuntu/lanes/pharma-ode-logforecast-20261029/source')
from resource_monitor import execute
binary=work/'model01/source/STUDIES/metric_autoselect_confirmation_v1/target/release/online'
refs=json.loads((work/'broad01/REFERENCES.json').read_text());ref=refs['sblrc-blr'];assert ref['passed']
inputs={};rows=[]
def read(p):
    raw=p.read_bytes();inputs[str(p)]=hashlib.sha256(raw).hexdigest();return json.loads(raw)
for seed in [929300005,929300008,929300009]:
    parent=work/f'hybrid0{(seed-929300001)//4+1}';prefix=f'sblrc-blr-{seed}'
    pilot=read(parent/'runs'/(prefix+'-pilot')/'RESULT.json');fit=read(parent/'runs'/(prefix+'-fit')/'RESULT.json');original=read(parent/'SUMMARY.json')
    assert fit['branch']=='v4' and fit['selection']['blocks']
    fc=np.linalg.inv(fit['fisher_mass']);c,info=select(fit['coarse'],fit['fine'],np.diag(fc));assert info['blocks']==fit['selection']['blocks']
    mass=np.linalg.inv(c);mass=(mass+mass.T)/2;assert min(np.linalg.eigvalsh(mass))>0 and np.linalg.norm(c@mass-np.eye(len(c)))<=1e-7
    folder=out/str(seed);folder.mkdir();args=read(parent/'runs'/(prefix+'-v4')/'INPUT.json');args['mass']=mass.ravel().tolist()
    (folder/'INPUT.json').write_text(json.dumps(args,indent=2)+'\n');(folder/'METRIC.json').write_text(json.dumps(dict(covariance=c.tolist(),mass=mass.tolist(),selection=info),indent=2)+'\n')
    sup=execute([str(binary),str(folder/'INPUT.json'),str(folder/'RESULT.json')],str(root),180,folder,2*1024**3,64*1024**2,folder/'worker.log',output_scan_interval=2)
    (folder/'SUPERVISION.json').write_text(json.dumps(sup,indent=2)+'\n')
    row=dict(seed=seed,passed=False)
    if sup['exit_code']==0 and sup['group_drained']:
        r=json.loads((folder/'RESULT.json').read_text());a=np.array(r['draws']);a[:,:,-1]=np.exp(a[:,:,-1]);ds=az.convert_to_dataset({'p':a})
        mean=a.mean((0,1));sd=a.reshape(-1,6).std(0,ddof=1);mcse=np.asarray(az.mcse(ds,method='mean').p)
        rh=np.asarray(az.rhat(ds,method='rank').p);bulk=np.asarray(az.ess(ds,method='bulk').p);tail=np.asarray(az.ess(ds,method='tail').p)
        z=np.abs(mean-ref['mean'])/np.sqrt(mcse**2+np.array(ref['mcse'])**2);delta=np.abs(mean-ref['mean'])/ref['sd'];se=np.abs(sd/ref['sd']-1)
        passed=max(rh)<=1.01 and min(bulk)>=400 and min(tail)>=400 and r['retained_divergences']==0 and max(z)<=4.5 and max(delta)<=.1 and max(se)<=.1
        calls=pilot['target_calls']+fit['score_calls']+fit['probe_calls']+r['target_calls'];eff=float(min(bulk)/calls)
        controls={a:next(v for v in original['rows'] if v['model']=='sblrc-blr' and v['seed']==seed and v['arm']==a) for a in ['fisher','hybrid','v4']}
        assert all(v['passed'] for v in controls.values())
        row.update(passed=bool(passed),rhat=float(max(rh)),bulk=float(min(bulk)),tail=float(min(tail)),divergences=r['retained_divergences'],
            max_z=float(max(z)),max_mean_sd=float(max(delta)),max_sd_error=float(max(se)),calls=calls,efficiency=eff,
            ratios={a:eff/v['efficiency'] for a,v in controls.items()},mean=mean.tolist(),sd=sd.tolist(),mcse=mcse.tolist())
    rows.append(row)
    shutil.copytree(folder,Path('/home/ubuntu/lanes/metric-blocks-recovery-20261030/evidence/scalerepair01')/str(seed))
result=dict(rows=rows,mechanism_gate=all(r['passed'] and r.get('ratios',{}).get('fisher',0)>=.9 for r in rows),inputs=inputs,
    unchanged=all(hashlib.sha256(Path(p).read_bytes()).hexdigest()==h for p,h in inputs.items()),exposed_repair_only=True)
(root/'SUMMARY.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
