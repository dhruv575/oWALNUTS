import hashlib,json,subprocess,sys,time,shutil
from pathlib import Path
import numpy as np
study=Path(__file__).resolve().parent;local=study/'local_recovery';root=local/'compact_validation01'
def canonical(r):
    r=json.loads(json.dumps(r))
    for c in r['chains']:c.pop('seconds')
    return hashlib.sha256(json.dumps(r,sort_keys=True,separators=(',',':')).encode()).hexdigest()
if len(sys.argv)>1:
    folder=Path(sys.argv[1]);spec=json.loads((folder/'CONFIG.json').read_text());rng=np.random.Generator(np.random.PCG64(spec['order_seed']));records=[];expected={}
    for repeat in range(3):
        for arm in rng.permutation(['original','observed']).tolist():
            output=folder/(f'RAW-{arm}.json' if repeat==0 else f'REPLAY-{arm}.json');started=time.perf_counter()
            subprocess.run([spec['builds'][arm]['binary'],str(folder/f'INPUT-{arm}.json'),str(output)],check=True,capture_output=True)
            elapsed=time.perf_counter()-started;data=json.loads(output.read_text());digest=canonical(data)
            if repeat==0:expected[arm]=digest
            else:assert digest==expected[arm]
            records.append(dict(arm=arm,repeat=repeat,seconds=elapsed,canonical_sha256=digest))
    a=json.loads((folder/'RAW-original.json').read_text());b=json.loads((folder/'RAW-observed.json').read_text())
    for x,y in zip(a['chains'],b['chains']):
        for k in x:
            if k not in ['seconds','summary']:assert x[k]==y[k]
    (folder/'TIMINGS.json').write_text(json.dumps(records,indent=2)+'\n');sys.exit(0)
assert json.loads((local/'compact_recycling_test01/SUMMARY.json').read_text())['passed'] and json.loads((local/'compact_original_test01/SUMMARY.json').read_text())['passed']
root.mkdir(exist_ok=False);sys.path.insert(0,str(local/'inputs'));from resource_monitor import execute
builds={arm:json.loads((local/name/'SUMMARY.json').read_text()) for arm,name in [('original','compact_original_build01'),('observed','compact_recycling_build01')]}
for b in builds.values():assert hashlib.sha256(Path(b['binary']).read_bytes()).hexdigest()==b['binary_sha256']
paths=[Path(__file__),study/'COMPACT-RECYCLING-VALIDATION.md',study/'analyze_compact_validation.py',local/'recycling_source03/src/recycling.rs',study/'compact_recycling_runner/src/main.rs',study/'compact_original_runner/src/main.rs'];hashes={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths};(root/'SOURCE-SNAPSHOT.json').write_text(json.dumps(hashes,indent=2)+'\n');rows=[]
for t,target in enumerate(['analytic_rotated_gaussian','noncentered','funnel']):
    rng=np.random.Generator(np.random.PCG64(941400001+t));d=2 if t==0 else 10
    starts=rng.normal(size=(64,d));mass=[2/3,-1/3,-1/3,2/3] if t==0 else [1.]*d
    if t==0:starts=starts@np.linalg.cholesky([[2.,1.],[1.,2.]]).T
    else:
        starts[:,0]*=3
        if t==2:starts[:,1:]*=np.exp(starts[:,:1]/2)
    for batch in range(16):
        assert shutil.disk_usage(root).free>1024**3;folder=root/f'{target}-{batch:02d}';folder.mkdir()
        chains=[dict(start=starts[i].tolist(),mass=mass,step_size=.3,seed=941410001+1000*t+i) for i in range(4*batch,4*batch+4)]
        for arm in builds:
            spec=dict(target=target,metric='dense' if t==0 else 'diagonal',draws=1000,levels=8,max_error=1.,compact=True,observe=arm=='observed',chains=chains);(folder/f'INPUT-{arm}.json').write_text(json.dumps(spec)+'\n')
        (folder/'CONFIG.json').write_text(json.dumps(dict(builds=builds,order_seed=941430001+100*t+batch))+'\n')
        r=execute([sys.executable,str(Path(__file__).resolve()),str(folder)],str(root),180,folder,2*1024**3,64*1024**2,folder/'worker.log',output_scan_interval=2);(folder/'SUPERVISION.json').write_text(json.dumps(r,indent=2)+'\n');assert r['exit_code']==0 and r['group_drained'];rows.append(dict(target=target,batch=batch,folder=folder.name,completed=True))
        if batch==0:
            full=folder/'full';full.mkdir();spec=json.loads((folder/'INPUT-observed.json').read_text());spec['compact']=False;(full/'INPUT.json').write_text(json.dumps(spec)+'\n')
            r=execute([builds['observed']['binary'],str(full/'INPUT.json'),str(full/'RAW.json')],str(root),180,full,2*1024**3,64*1024**2,full/'worker.log',output_scan_interval=2);(full/'SUPERVISION.json').write_text(json.dumps(r,indent=2)+'\n');assert r['exit_code']==0 and r['group_drained']
            raw=json.loads((full/'RAW.json').read_text());compact=json.loads((folder/'RAW-observed.json').read_text())
            for a,b in zip(raw['chains'],compact['chains']):
                x=np.asarray(a['draws'],dtype='<f8');v=np.asarray(a['recycled']);assert hashlib.sha256(x.tobytes()).hexdigest()==b['draw_sha256']
                assert np.allclose(v.mean(axis=0),b['summary']['mean'],rtol=2e-13,atol=1e-10) and np.allclose(v.reshape(20,50,-1).mean(axis=1),b['summary']['block_means'],rtol=2e-13,atol=1e-10)
        (root/'PROGRESS.json').write_text(json.dumps(rows,indent=2)+'\n')
    print(target+' fresh validation complete',flush=True)
assert all(hashlib.sha256(Path(p).read_bytes()).hexdigest()==h for p,h in hashes.items())
(root/'SUMMARY.json').write_text(json.dumps(dict(passed=True,rows=rows,inputs=hashes,unchanged=True,builds=builds,full_checks=3),indent=2)+'\n')
