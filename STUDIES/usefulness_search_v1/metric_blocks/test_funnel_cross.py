import hashlib,json,sys
from pathlib import Path
import numpy as np
import arviz as az
study=Path(__file__).resolve().parent;local=study/'local_recovery';root=local/'funnel_cross_test01';root.mkdir(exist_ok=False)
sys.path.insert(0,str(local/'inputs'));from resource_monitor import execute
build=json.loads((local/'funnel_cross_build01/SUMMARY.json').read_text());binary=Path(build['binary']);assert hashlib.sha256(binary.read_bytes()).hexdigest()==build['binary_sha256']
def run(name,spec,runner=binary,expected=0):
    folder=root/name;folder.mkdir();inp=folder/'INPUT.json';inp.write_text(json.dumps(spec)+'\n')
    r=execute([str(runner),str(inp),str(folder/'RAW.json')],str(root),180,folder,2*1024**3,64*1024**2,folder/'worker.log',output_scan_interval=2)
    (folder/'SUPERVISION.json').write_text(json.dumps(r,indent=2)+'\n');assert r['group_drained'] and (r['exit_code']==0 if expected==0 else r['exit_code']!=0)
    return json.loads((folder/'RAW.json').read_text()) if expected==0 else None
spec=dict(target='analytic_rotated_gaussian',draws=4000,levels=8,max_error=1,chains=[dict(start=[0.,0.],mass=[2/3,-1/3,-1/3,2/3],step_size=.4,seed=941099801+i) for i in range(4)])
old=Path(json.loads((local/'fixed_metric_build02/SUMMARY.json').read_text())['binary'])
a=run('parity_old',spec,old);b=run('parity_new',spec)
assert a['target_calls']==b['target_calls']
assert all(c['draws']==d['draws'] and c['target_calls']==d['target_calls'] for c,d in zip(a['chains'],b['chains']))
controls=[]
for error in [1.,1000.]:
    spec=dict(target='noncentered',metric='diagonal',draws=20000,levels=8,max_error=error,chains=[dict(start=[float(i-2)]+[0.]*9,mass=[1.]*10,step_size=.3,seed=941099901+i) for i in range(4)])
    a=run(f'control-{error}',spec);x=np.asarray([c['draws'] for c in a['chains']]);var=np.array([9.]+[1.]*9)
    diag=[]
    for i in range(10):
        v=x[:,:,i];d=dict(rhat=float(az.rhat(v)),bulk=float(az.ess(v,method='bulk')),tail=float(az.ess(v,method='tail')),mean=float(v.mean()),variance=float(v.var()))
        assert d['rhat']<=1.01 and min(d['bulk'],d['tail'])>=400 and abs(d['mean'])/np.sqrt(var[i])<=.05 and abs(d['variance']/var[i]-1)<=.05
        diag.append(d)
    assert all(c['retained_divergences']==0 and c['work']['maximum_depth_stops']==0 and c['work']['all_phase_calls']==c['target_calls'] for c in a['chains'])
    single=dict(spec,chains=spec['chains'][:1]);b=run(f'replay-{error}',single)
    assert a['chains'][0]['draws']==b['chains'][0]['draws'] and a['chains'][0]['target_calls']==b['chains'][0]['target_calls']
    controls.append(dict(error=error,diagnostics=diag))
bad=dict(spec,chains=[dict(spec['chains'][0],mass=[-1.]+[1.]*9)])
run('invalid_mass',bad,expected=1)
(root/'SUMMARY.json').write_text(json.dumps(dict(passed=True,exact_gaussian_parity=True,controls=controls,exact_chain_replays=2,invalid_metric_rejected=True),indent=2)+'\n')
print('Funnel cross preflight passed: target tests, old-runner parity, two Gaussian controls, exact chain replays, invalid metric rejection')
