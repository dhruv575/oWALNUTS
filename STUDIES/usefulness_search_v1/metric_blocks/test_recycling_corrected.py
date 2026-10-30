import hashlib,json,sys
from pathlib import Path
import numpy as np
import arviz as az
from scipy.special import ndtr
study=Path(__file__).resolve().parent;local=study/'local_recovery';root=local/'recycling_test02';root.mkdir(exist_ok=False)
sys.path.insert(0,str(local/'inputs'));from resource_monitor import execute
build=json.loads((local/'recycling_build03/SUMMARY.json').read_text());binary=Path(build['binary']);assert hashlib.sha256(binary.read_bytes()).hexdigest()==build['binary_sha256']
old=Path(json.loads((local/'funnel_cross_build01/SUMMARY.json').read_text())['binary'])
paths=[Path(__file__),study/'RECYCLING-AUDIT.md',study/'recycling_runner/src/main.rs',local/'recycling_source02/src/kernel.rs',local/'recycling_source02/src/recycling.rs']
hashes={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths};(root/'SOURCE-SNAPSHOT.json').write_text(json.dumps(hashes,indent=2)+'\n')
def run(name,spec,runner):
    folder=root/name;folder.mkdir();inp=folder/'INPUT.json';inp.write_text(json.dumps(spec)+'\n')
    r=execute([str(runner),str(inp),str(folder/'RAW.json')],str(root),180,folder,2*1024**3,64*1024**2,folder/'worker.log',output_scan_interval=2)
    (folder/'SUPERVISION.json').write_text(json.dumps(r,indent=2)+'\n');assert r['exit_code']==0 and r['group_drained']
    return json.loads((folder/'RAW.json').read_text())
rows=[]
for target in ['analytic_rotated_gaussian','noncentered','funnel']:
    d=2 if target=='analytic_rotated_gaussian' else 10
    mass=[2/3,-1/3,-1/3,2/3] if d==2 else [1.]*d
    spec=dict(target=target,metric='dense' if d==2 else 'diagonal',draws=10000 if target!='funnel' else 4000,levels=8,max_error=1.,chains=[dict(start=[0.]*d,mass=mass,step_size=.3,seed=941200001+i) for i in range(4)])
    original=run(target+'-original',spec,old);disabled=run(target+'-disabled',dict(spec,observe=False),binary);enabled=run(target+'-enabled',dict(spec,observe=True),binary)
    for a,b,c in zip(original['chains'],disabled['chains'],enabled['chains']):
        for k in a:
            if k!='seconds':assert a[k]==b[k]==c[k],(target,k)
        assert b['recycled']==[] and len(c['recycled'])==spec['draws']
        assert np.asarray(c['recycled']).shape==(spec['draws'],4*d) and np.isfinite(c['recycled']).all()
    assert original['target_calls']==disabled['target_calls']==enabled['target_calls']
    row=dict(target=target,exact_draws_and_all_work_parity=True,observations_per_transition=1,target_calls=enabled['target_calls'])
    if target!='funnel':
        x=np.asarray([c['draws'] for c in enabled['chains']]);v=np.asarray([c['recycled'] for c in enabled['chains']]);variance=np.array([2.,2.] if d==2 else [9.]+[1.]*9)
        means=v.mean(axis=(0,1));truth=np.concatenate([np.zeros(d),variance,np.full(d,.5),ndtr(-2/np.sqrt(variance))])
        tolerances=np.concatenate([.05*np.sqrt(variance),.05*variance,np.full(2*d,.01)])
        assert np.all(np.abs(means-truth)<=tolerances),(target,means,truth)
        diag=[]
        for i in range(d):
            values=x[:,:,i];result=dict(rhat=float(az.rhat(values)),bulk=float(az.ess(values,method='bulk')),tail=float(az.ess(values,method='tail')))
            assert result['rhat']<=1.01 and min(result['bulk'],result['tail'])>=400;diag.append(result)
        assert all(c['retained_divergences']==0 and c['work']['maximum_depth_stops']==0 for c in enabled['chains'])
        row.update(conditional_estimates=means.tolist(),truth=truth.tolist(),tolerances=tolerances.tolist(),diagnostics=diag)
    rows.append(row);print(target+' passed',flush=True)
assert all(hashlib.sha256(Path(p).read_bytes()).hexdigest()==h for p,h in hashes.items())
(root/'SUMMARY.json').write_text(json.dumps(dict(passed=True,rows=rows,inputs=hashes,unchanged=True,binary=build),indent=2)+'\n')
