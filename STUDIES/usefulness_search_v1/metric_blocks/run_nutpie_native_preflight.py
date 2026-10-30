import hashlib,json,shutil,sys
from pathlib import Path
import numpy as np
import arviz as az
import bridgestan as bs
study=Path(__file__).resolve().parent;local=study/'local_recovery';attempt=int(sys.argv[1]) if len(sys.argv)>1 else 1;assert attempt in [1,2,3]
root=local/f'nativepreflight{attempt:02d}';root.mkdir(exist_ok=False)
assert shutil.disk_usage(root).free>=1024**3
sys.path.insert(0,str(local/'inputs'))
from resource_monitor import execute
model='sblrc-blr';models=local/'inputs/models' if attempt==1 else local/'threaded_build01'
if attempt>=2:
    assert json.loads((models/'SUMMARY.json').read_text())['passed']
    build=json.loads((models/'SUPERVISION.json').read_text());assert build['exit_code']==0 and build['group_drained']
so=models/(model+'_model.so');data=models/(model+'.data.json');source=models/(model+'.stan')
target=bs.StanModel(str(so),data=data.read_text(),seed=1);d=len(target.param_unc_names())
refs=json.loads((local/'localscaled01/REFERENCES.json').read_text());ref=refs[model];assert ref['passed']
def cname(n):
    p=n.split('.');return p[0]+'['+','.join(p[1:])+']' if len(p)>1 and all(s.isdigit() for s in p[1:]) else n
names=[cname(n) for n in target.param_names(include_tp=True,include_gq=False)];indices=[names.index(n) for n in ref['names']]
rows=[]
for arm in ['draw_diag','diag','low_rank']:
    folder=root/arm;folder.mkdir();inp=dict(model=str(so),data=str(data),source=str(source),dimension=d,seed=929800001,adaptation=arm)
    ip=folder/'INPUT.json';op=folder/'RESULT.json';ip.write_text(json.dumps(inp,indent=2)+'\n')
    r=execute([sys.executable,str(study/'nutpie_native_worker.py'),str(ip),str(op)],str(root),180,folder,2*1024**3,64*1024**2,folder/'worker.log',output_scan_interval=2)
    (folder/'SUPERVISION.json').write_text(json.dumps(r,indent=2)+'\n')
    if r['exit_code']!=0 or not r['group_drained']:
        rows.append(dict(arm=arm,passed=False,error='worker_failed',supervision=r));continue
    result=json.loads(op.read_text());q=np.asarray(result['draws']);a=np.asarray([target.param_constrain(x,include_tp=True,include_gq=False)[indices] for x in q.reshape(-1,d)]).reshape(4,2000,-1)
    ds=az.convert_to_dataset({'p':a});mean=a.mean((0,1));sd=a.reshape(-1,a.shape[-1]).std(0,ddof=1)
    rh=np.asarray(az.rhat(ds,method='rank').p);bulk=np.asarray(az.ess(ds,method='bulk').p);tail=np.asarray(az.ess(ds,method='tail').p);mcse=np.asarray(az.mcse(ds,method='mean').p)
    z=np.abs(mean-ref['mean'])/np.sqrt(mcse**2+np.asarray(ref['mcse'])**2);delta=np.abs(mean-ref['mean'])/ref['sd'];se=np.abs(sd/ref['sd']-1)
    passed=all(np.isfinite(v).all() for v in [mean,sd,rh,bulk,tail,mcse,z,delta,se]) and max(rh)<=1.01 and min(bulk)>=400 and min(tail)>=400 and result['retained_divergences']==0 and max(z)<=4.5 and max(delta)<=.1 and max(se)<=.1
    rows.append(dict(arm=arm,passed=bool(passed),rhat=float(max(rh)),bulk=float(min(bulk)),tail=float(min(tail)),divergences=result['retained_divergences'],max_z=float(max(z)),max_mean_sd=float(max(delta)),max_sd_error=float(max(se)),invocation_seconds=r['elapsed_seconds'],target_calls=None))
    (root/'PROGRESS.json').write_text(json.dumps(rows,indent=2)+'\n')
sources=[Path(__file__),study/'nutpie_native_worker.py',study/'NUTPIE-NATIVE-PREFLIGHT.md',so,data,source,local/'localscaled01/REFERENCES.json']
if attempt>=2:sources.extend([study/'NUTPIE-THREADING-AMENDMENT.md',models/'SUMMARY.json',models/'SUPERVISION.json'])
if attempt==3:sources.append(study/'NUTPIE-SERIALIZATION-AMENDMENT.md')
summary=dict(passed=all(r['passed'] for r in rows),rows=rows,scope='Native backend qualification only; no matched sampler superiority claim.',inputs={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in sources})
(root/'SUMMARY.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary))
