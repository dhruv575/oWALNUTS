import hashlib,json,sys,tomllib
from pathlib import Path
import numpy as np
import arviz as az
from scipy.special import ndtr
study=Path(__file__).resolve().parent;local=study/'local_recovery';root=local/'native_recycling_test02';root.mkdir(exist_ok=False)
build=json.loads((local/'native_recycling_build02/SUMMARY.json').read_text());assert build['passed'];binaries={b['package']:b for b in build['rows']}
for b in binaries.values():assert hashlib.sha256(Path(b['binary']).read_bytes()).hexdigest()==b['binary_sha256']
locks=[]
for package in ['native_pristine_runner','native_recycling_runner']:
    lock=tomllib.loads((study/package/'Cargo.lock').read_text());locks.append({p['name']:(p['version'],p.get('source'),p.get('checksum')) for p in lock['package'] if p.get('source')})
assert locks[0]==locks[1],'Registry dependencies differ'
sys.path.insert(0,str(local/'inputs'));from resource_monitor import execute
paths=[Path(__file__),study/'NATIVE-RECYCLING-AUDIT.md',study/'native_recycling_runner/src/main.rs',study/'native_pristine_runner/src/main.rs',local/'native_recycling_source01/src/nuts.rs',local/'native_recycling_source01/src/research_recycling.rs'];hashes={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths};(root/'SOURCE-SNAPSHOT.json').write_text(json.dumps(hashes,indent=2)+'\n')
rows=[]
for ti,target in enumerate(['analytic_rotated_gaussian','noncentered','funnel']):
    d=2 if ti==0 else 10
    for adaptation in ['diag','low_rank']:
        data={};folders={}
        for arm in ['pristine','disabled','enabled']:
            folder=root/f'{target}-{adaptation}-{arm}';folder.mkdir();folders[arm]=folder
            spec=dict(target=target,adaptation=adaptation,warmup=1000,draws=4000,observe=arm=='enabled',chains=[dict(start=[float(2*i-3)]+[0.1*j for j in range(1,d)],seed=941500001+100*ti+i) for i in range(4)])
            inp=folder/'INPUT.json';inp.write_text(json.dumps(spec)+'\n');binary=binaries['native_pristine_runner' if arm=='pristine' else 'native_recycling_runner']['binary']
            r=execute([binary,str(inp),str(folder/'RAW.json')],str(root),180,folder,2*1024**3,64*1024**2,folder/'worker.log',output_scan_interval=2);(folder/'SUPERVISION.json').write_text(json.dumps(r,indent=2)+'\n');assert r['exit_code']==0 and r['group_drained'];data[arm]=json.loads((folder/'RAW.json').read_text())
        for a,b,c in zip(*(data[k]['chains'] for k in ['pristine','disabled','enabled'])):
            for k in a:
                if k not in ['seconds','recycled']:assert a[k]==b[k]==c[k],(target,adaptation,k)
            assert a['recycled']==b['recycled']==[] and len(c['recycled'])==5000
        x=np.asarray([c['all_draws'][1000:] for c in data['enabled']['chains']]);v=np.asarray([c['recycled'][1000:] for c in data['enabled']['chains']]);assert x.shape==(4,4000,d) and v.shape==(4,4000,4*d) and np.isfinite(v).all()
        assert v[:,:,2*d:].min()>=0 and v[:,:,2*d:].max()<=1+1e-14 and (v[:,:,d:2*d]-v[:,:,:d]**2).min()>-1e-9
        row=dict(target=target,adaptation=adaptation,exact_warmup_retained_progress_calls_parity=True,retained_divergences=sum(p['diverging'] for c in data['enabled']['chains'] for p in c['all_progress'][1000:]),target_calls=sum(c['target_calls'] for c in data['enabled']['chains']))
        if target!='funnel':
            variance=np.array([2.,2.] if ti==0 else [9.]+[1.]*9);truth=np.concatenate([np.zeros(d),variance,np.full(d,.5),ndtr(-2/np.sqrt(variance))]);means=v.mean(axis=(0,1));tol=np.concatenate([.05*np.sqrt(variance),.05*variance,np.full(2*d,.01)])
            diag=[dict(rhat=float(az.rhat(x[:,:,i])),bulk=float(az.ess(x[:,:,i],method='bulk')),tail=float(az.ess(x[:,:,i],method='tail'))) for i in range(d)]
            qualified=bool(np.all(abs(means-truth)<=tol) and row['retained_divergences']==0 and all(c['rhat']<=1.01 and min(c['bulk'],c['tail'])>=400 for c in diag))
            row.update(gaussian_qualified=qualified,conditional_estimates=means.tolist(),truth=truth.tolist(),tolerances=tol.tolist(),diagnostics=diag)
        rows.append(row);(root/'PROGRESS.json').write_text(json.dumps(rows,indent=2)+'\n');print(json.dumps({k:v for k,v in row.items() if k not in ['conditional_estimates','truth','tolerances','diagnostics']}),flush=True)
assert all(hashlib.sha256(Path(p).read_bytes()).hexdigest()==h for p,h in hashes.items())
passed=all(r.get('gaussian_qualified',True) for r in rows)
(root/'SUMMARY.json').write_text(json.dumps(dict(passed=passed,rows=rows,inputs=hashes,unchanged=True,registry_dependencies_identical=True,binaries=binaries),indent=2)+'\n');assert passed,'Known-truth Gaussian qualification failed'
