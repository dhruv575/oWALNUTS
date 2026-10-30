"""Frozen analytic-target injection, replay and invalid-input preflight."""
import hashlib,json,sys
from pathlib import Path
study=Path(__file__).resolve().parent;local=study/'local_recovery';root=local/'refinement_ablation_test01'
if len(sys.argv)==1:
    root.mkdir(exist_ok=False);sys.path.insert(0,str(local/'inputs'))
    from resource_monitor import execute
    r=execute([sys.executable,str(Path(__file__)),'worker'],str(root),180,root,2*1024**3,64*1024**2,root/'worker.log',output_scan_interval=2)
    (root/'SUPERVISION.json').write_text(json.dumps(r,indent=2)+'\n');assert r['exit_code']==0 and r['group_drained']
else:
    import subprocess,numpy as np,arviz as az
    build=json.loads((local/'refinement_ablation_build01/SUMMARY.json').read_text());assert build['passed']
    binary=Path(build['binary']);assert hashlib.sha256(binary.read_bytes()).hexdigest()==build['binary_sha256']
    configs=[dict(start=[.2,-.1],mass=[2/3,-1/3,-1/3,2/3],step_size=step,seed=940800001+i) for i,step in enumerate([.2,.4,.6,.8])]
    spec=dict(target='analytic_rotated_gaussian',draws=4000,chains=configs)
    def run(name,spec,good=True):
        inp=root/(name+'-INPUT.json');out=root/(name+'-OUTPUT.json');inp.write_text(json.dumps(spec)+'\n')
        r=subprocess.run([str(binary),str(inp),str(out)],capture_output=True,text=True,timeout=60)
        (root/(name+'-STDERR.txt')).write_text(r.stderr)
        assert (r.returncode==0)==good
        if good:return json.loads(out.read_text())
        assert not out.exists()
    control=run('control',spec)
    old=json.loads((local/'fixed_metric_test01/combined-OUTPUT.json').read_text())
    for a,b in zip(control['chains'],old['chains']):
        for key in ['draws','target_calls','retained_divergences','step_size','mass','seed','revision']:assert a[key]==b[key]
        assert a['levels']==2 and a['max_error']==1
    spec.update(levels=1,max_error=1000.)
    result=run('combined',spec)
    for r in result['chains']:
        assert r['levels']==1 and r['max_error']==1000 and r['work']['target_calls_reverse']==0
        assert r['work']['all_phase_calls']==r['target_calls']
    q=np.asarray([r['draws'] for r in result['chains']]);assert q.shape==(4,4000,2)
    for i,c in enumerate(configs):
        replay=run('replay'+str(i),dict(spec,chains=[c]));r=result['chains'][i];b=replay['chains'][0]
        assert r['draws']==b['draws'] and r['target_calls']==b['target_calls'] and r['step_size']==c['step_size'] and r['mass']==c['mass']
    assert result['target_calls']==sum(r['target_calls'] for r in result['chains'])
    ds=az.convert_to_dataset({'q':q});rh=np.asarray(az.rhat(ds,method='rank').q);bulk=np.asarray(az.ess(ds,method='bulk').q);tail=np.asarray(az.ess(ds,method='tail').q);mcse=np.asarray(az.mcse(ds,method='mean').q)
    flat=q.reshape(-1,2);mean=flat.mean(0);sd=flat.std(0,ddof=1);cov=np.cov(flat.T);ref=np.array([[2.,1.],[1.,2.]])
    diag=dict(rhat=float(rh.max()),bulk=float(bulk.min()),tail=float(tail.min()),max_z=float(np.max(abs(mean)/mcse)),max_mean_sd=float(np.max(abs(mean)/np.sqrt(2))),max_sd_error=float(np.max(abs(sd/np.sqrt(2)-1))),max_covariance_error=float(np.max(abs(cov-ref)/2)),divergences=sum(r['retained_divergences'] for r in result['chains']))
    good=all(np.isfinite(v) for v in diag.values()) and diag['rhat']<=1.01 and diag['bulk']>=400 and diag['tail']>=400 and diag['max_z']<=4.5 and diag['max_mean_sd']<=.1 and diag['max_sd_error']<=.1 and diag['max_covariance_error']<=.1 and diag['divergences']==0
    run('invalid_mass',dict(spec,draws=1,chains=[dict(configs[0],mass=[1,2,2,1])]),False)
    run('invalid_step',dict(spec,draws=1,chains=[dict(configs[0],step_size=0)]),False)
    (root/'SUMMARY.json').write_text(json.dumps(dict(passed=bool(good),diagnostics=diag,exact_single_chain_replays=4,invalid_inputs_rejected=2,binary_sha256=build['binary_sha256'],scope=__doc__),indent=2)+'\n');print(json.dumps(diag));assert good
