import hashlib,json,sys,tomllib,shutil
from pathlib import Path
import numpy as np
import arviz as az
p=Path(__file__).resolve().parent;l=p/'local_recovery';root=l/'cold_recycling_test01';root.mkdir(exist_ok=False)
sys.path.insert(0,str(l/'inputs'));from resource_monitor import execute
build=json.loads((l/'cold_recycling_build03/SUMMARY.json').read_text());assert build['passed'];binaries={b['package']:b for b in build['rows']}
for b in binaries.values():assert hashlib.sha256(Path(b['binary']).read_bytes()).hexdigest()==b['binary_sha256']
locks=[]
for n in binaries:
    lock=tomllib.loads((p/n/'Cargo.lock').read_text());locks.append({v['name']:(v['version'],v.get('source'),v.get('checksum')) for v in lock['package'] if v.get('source')})
assert locks[0]==locks[1]
paths=[Path(__file__),p/'COLD-RECYCLING-PROTOCOL.md',p/'banana_core.rs',l/'banana_recycling_test01/EXACT-CONTROL.json',l/'cold_wal_source01/src/recycling.rs',l/'cold_wal_source01/src/walnutpie.rs']+[p/n/'src/main.rs' for n in binaries];hashes={str(f):hashlib.sha256(f.read_bytes()).hexdigest() for f in paths};(root/'SOURCE-SNAPSHOT.json').write_text(json.dumps(hashes,indent=2)+'\n')
exact=json.loads((l/'banana_recycling_test01/EXACT-CONTROL.json').read_text());truth=np.array(exact['truth']);tol=np.array(exact['tolerances']);starts=np.random.default_rng(941800001).normal(size=(4,24));rows=[]
cases=[(t,m) for t in ['banana_direct','banana_latent'] for m in ['identity','diagonal']]+[('funnel','diagonal')]
def run(folder,binary,spec):
    assert shutil.disk_usage(root).free>1024**3;folder.mkdir();(folder/'INPUT.json').write_text(json.dumps(spec)+'\n');r=execute([binary,str(folder/'INPUT.json'),str(folder/'RAW.json')],str(root),180,folder,2*1024**3,64*1024**2,folder/'worker.log',output_scan_interval=2);(folder/'SUPERVISION.json').write_text(json.dumps(r,indent=2)+'\n');assert r['exit_code']==0 and r['group_drained'],folder.name
    return json.loads((folder/'RAW.json').read_text())
for ci,(target,metric) in enumerate(cases):
    d=10 if target=='funnel' else 24;initial=starts.copy()
    if target=='banana_direct':initial[:,1::2]+=5*(initial[:,::2]**2-1)
    elif target=='funnel':initial=np.array([[2*i-3]+[.1*j for j in range(1,10)] for i in range(4)])
    data={};specs={}
    for arm in ['original','disabled','enabled']:
        spec=dict(target=target,metric=metric,warmup=1000,draws=4000,target_accept=.9,levels=8,max_error=1.,compact=True,observe=arm=='enabled',chains=[dict(start=initial[i].tolist(),seed=941810001+100*ci+i,mass=[1.]*d,step_size=.3) for i in range(4)])
        name='cold_wal_original_runner' if arm=='original' else 'cold_wal_recycling_runner';specs[arm]=spec;data[arm]=run(root/f'{target}-{metric}-{arm}',binaries[name]['binary'],spec)
    for a,b,c in zip(*(data[k]['chains'] for k in ['original','disabled','enabled'])):
        for k in a:
            if k not in ['seconds','summary']:assert a[k]==b[k]==c[k],(target,metric,k)
        assert a['summary']==b['summary'];assert c['summary']['count']==4000 and c['summary']['block_sizes']==[50]*80
    full=run(root/f'{target}-{metric}-full',binaries['cold_wal_recycling_runner']['binary'],dict(specs['enabled'],compact=False));xs=[];vs=[];os=[]
    for f,c,a in zip(full['chains'],data['enabled']['chains'],data['original']['chains']):
        for k in c:
            if k not in ['seconds','summary','draws','recycled']:assert f[k]==c[k],k
        x=np.array(f['draws'],dtype='<f8');v=np.array(f['recycled']);assert x.shape==(4000,d) and v.shape==(4000,4*d);assert hashlib.sha256(x.tobytes()).hexdigest()==c['draw_sha256']
        q=x.copy()
        if target=='banana_latent':q[:,1::2]+=5*(q[:,::2]**2-1)
        obs=np.concatenate([q,q*q,(q<0).astype(float),(q< -2).astype(float)],axis=1)
        np.testing.assert_allclose(a['summary']['mean'],obs.mean(0),rtol=2e-13,atol=1e-10);np.testing.assert_allclose(c['summary']['mean'],v.mean(0),rtol=2e-13,atol=1e-10);np.testing.assert_allclose(c['summary']['block_means'],v.reshape(80,50,4*d).mean(1),rtol=2e-13,atol=1e-10)
        assert np.isfinite(v).all() and v[:,2*d:].min()>=0 and v[:,2*d:].max()<=1+1e-14 and (v[:,d:2*d]-v[:,:d]**2).min()>-1e-8
        xs.append(x);vs.append(v);os.append(obs)
    x=np.array(xs);v=np.array(vs);o=np.array(os);diag=[dict(rhat=float(az.rhat(x[:,:,i])),bulk=float(az.ess(x[:,:,i],method='bulk')),tail=float(az.ess(x[:,:,i],method='tail'))) for i in range(d)];div=sum(c['retained_divergences'] for c in data['enabled']['chains'])
    row=dict(target=target,metric=metric,exact_parity=True,compact_full_replay=True,retained_records_per_chain=4000,retained_divergences=div,diagnostics=diag,conditional_estimates=v.mean((0,1)).tolist(),ordinary_estimates=o.mean((0,1)).tolist(),final_steps=[c['step_size'] for c in data['enabled']['chains']],actual_discarded=[c['discarded'] for c in data['enabled']['chains']])
    if target=='banana_latent':row['latent_qualified']=bool(div==0 and np.all(abs(v.mean((0,1))-truth)<=tol) and np.all(abs(o.mean((0,1))-truth)<=tol) and all(c['rhat']<=1.01 and min(c['bulk'],c['tail'])>=400 for c in diag))
    rows.append(row);(root/'PROGRESS.json').write_text(json.dumps(rows,indent=2)+'\n');print(json.dumps({k:v for k,v in row.items() if k not in ['diagnostics','conditional_estimates','ordinary_estimates']}),flush=True)
assert all(hashlib.sha256(Path(f).read_bytes()).hexdigest()==h for f,h in hashes.items());passed=all(row.get('latent_qualified',True) for row in rows)
(root/'SUMMARY.json').write_text(json.dumps(dict(passed=passed,rows=rows,inputs=hashes,unchanged=True,binaries=binaries),indent=2)+'\n');assert passed,'Latent qualification failed'
