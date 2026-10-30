import hashlib,json,sys,tomllib,shutil
from pathlib import Path
import numpy as np
import arviz as az
from scipy.integrate import quad
from scipy.special import ndtr,erf
p=Path(__file__).resolve().parent;l=p/'local_recovery';root=l/'banana_recycling_test01';root.mkdir(exist_ok=False)
sys.path.insert(0,str(l/'inputs'));from resource_monitor import execute
build=json.loads((l/'banana_recycling_build01/SUMMARY.json').read_text());assert build['passed'];binaries={b['package']:b for b in build['rows']}
for b in binaries.values():assert hashlib.sha256(Path(b['binary']).read_bytes()).hexdigest()==b['binary_sha256']
for pair in [('banana_native_pristine_runner','banana_native_recycling_runner'),('banana_wal_original_runner','banana_wal_recycling_runner')]:
    locks=[]
    for package in pair:
        lock=tomllib.loads((p/package/'Cargo.lock').read_text());locks.append({x['name']:(x['version'],x.get('source'),x.get('checksum')) for x in lock['package'] if x.get('source')})
    assert locks[0]==locks[1]
paths=[Path(__file__),p/'BANANA-RECYCLING-QUALIFICATION.md',p/'banana_core.rs',l/'banana_wal_source01/src/recycling.rs',l/'banana_native_source01/src/research_recycling.rs']+[p/n/'src/main.rs' for n in binaries];hashes={str(f):hashlib.sha256(f.read_bytes()).hexdigest() for f in paths};(root/'SOURCE-SNAPSHOT.json').write_text(json.dumps(hashes,indent=2)+'\n')
def physical(q,latent):
    x=q.copy()
    if latent:x[...,1::2]+=5*(q[...,::2]**2-1)
    return x
def features(x):return np.concatenate([x,x*x,(x<0).astype(float),(x< -2).astype(float)],axis=-1)
var=np.tile([1.,51.],12);prob=[];quadrature=[]
for threshold in [0.,-2.]:
    density=lambda z:np.exp(-z*z/2)/np.sqrt(2*np.pi)
    a,ea=quad(lambda z:2*density(z)*ndtr(threshold-5*(z*z-1)),0,np.inf,epsabs=1e-11,epsrel=1e-11)
    b,eb=quad(lambda w:density(w)*erf(np.sqrt(max(0,(threshold-w+5)/10))),-np.inf,threshold+5,epsabs=1e-11,epsrel=1e-11)
    assert abs(a-b)<1e-9 and max(ea,eb)<1e-9;prob.extend(np.tile([ndtr(threshold),a],12));quadrature.append(dict(threshold=threshold,value=a,alternate=b,error_bounds=[ea,eb]))
truth=np.r_[np.zeros(24),var,prob];tol=np.r_[.05*np.sqrt(var),.1*var,np.full(48,.02)]
exact=physical(np.random.default_rng(941700002).normal(size=(200000,24)),True);exact_means=features(exact).mean(0);assert np.all(abs(exact_means-truth)<=tol);del exact
(root/'EXACT-CONTROL.json').write_text(json.dumps(dict(passed=True,draws=200000,seed=941700002,quadrature=quadrature,truth=truth.tolist(),tolerances=tol.tolist(),independent_estimates=exact_means.tolist()),indent=2)+'\n')
starts=np.random.default_rng(941700001).normal(size=(4,24));rows=[]
def run(folder,binary,spec):
    assert shutil.disk_usage(root).free>1024**3;folder.mkdir();(folder/'INPUT.json').write_text(json.dumps(spec)+'\n')
    r=execute([binary,str(folder/'INPUT.json'),str(folder/'RAW.json')],str(root),180,folder,2*1024**3,64*1024**2,folder/'worker.log',output_scan_interval=2);(folder/'SUPERVISION.json').write_text(json.dumps(r,indent=2)+'\n');assert r['exit_code']==0 and r['group_drained'],folder.name
    return json.loads((folder/'RAW.json').read_text())
for ti,representation in enumerate(['direct','latent']):
    latent=representation=='latent';initial=physical(starts,not latent)
    for engine in ['wal','diag','low_rank']:
        data={};specs={}
        for arm in ['original','disabled','enabled']:
            chains=[dict(start=initial[i].tolist(),seed=941710001+100*ti+i) for i in range(4)]
            if engine=='wal':
                chains=[dict(c,mass=[1.]*24 if latent else (1/var).tolist(),step_size=.3 if latent else .1) for c in chains];name='banana_wal_original_runner' if arm=='original' else 'banana_wal_recycling_runner';spec=dict(target='banana_'+representation,chains=chains,metric='diagonal',draws=4000,levels=8,max_error=1.,compact=True,observe=arm=='enabled')
            else:name='banana_native_pristine_runner' if arm=='original' else 'banana_native_recycling_runner';spec=dict(target='banana_'+representation,chains=chains,adaptation=engine,warmup=1000,draws=4000,compact=True,observe=arm=='enabled')
            specs[arm]=spec;data[arm]=run(root/f'{representation}-{engine}-{arm}',binaries[name]['binary'],spec)
        for a,b,c in zip(*(data[k]['chains'] for k in ['original','disabled','enabled'])):
            for k in ['draw_sha256','target_calls','retained_divergences']+(['work'] if engine=='wal' else ['warmup_calls','total_steps','ordinary_summary']):assert a[k]==b[k]==c[k],(representation,engine,k)
        spec=dict(specs['enabled'],compact=False);name='banana_wal_recycling_runner' if engine=='wal' else 'banana_native_recycling_runner';full=run(root/f'{representation}-{engine}-full',binaries[name]['binary'],spec);xs=[];vs=[];ordinary=[]
        for raw,compact,orig in zip(full['chains'],data['enabled']['chains'],data['original']['chains']):
            q=np.asarray(raw['draws'] if engine=='wal' else raw['all_draws'],dtype='<f8');assert hashlib.sha256(q.tobytes()).hexdigest()==compact['draw_sha256'];warmup=0 if engine=='wal' else 1000;q=q[warmup:];v=np.asarray(raw['recycled'])[warmup:];assert q.shape==(4000,24) and v.shape==(4000,96)
            f=features(physical(q,latent));sm=compact['summary' if engine=='wal' else 'conditional_summary'];om=orig['summary' if engine=='wal' else 'ordinary_summary'];np.testing.assert_allclose(sm['mean'],v.mean(0),rtol=2e-13,atol=1e-10);np.testing.assert_allclose(sm['block_means'],v.reshape(80,50,96).mean(1),rtol=2e-13,atol=1e-10);np.testing.assert_allclose(om['mean'],f.mean(0),rtol=2e-13,atol=1e-10)
            assert np.isfinite(v).all() and v[:,48:].min()>=0 and v[:,48:].max()<=1+1e-14 and (v[:,24:48]-v[:,:24]**2).min()>-1e-8
            xs.append(q);vs.append(v);ordinary.append(f)
        x=np.array(xs);v=np.array(vs);o=np.array(ordinary);diag=[dict(rhat=float(az.rhat(x[:,:,i])),bulk=float(az.ess(x[:,:,i],method='bulk')),tail=float(az.ess(x[:,:,i],method='tail'))) for i in range(24)];div=sum(c['retained_divergences'] for c in data['enabled']['chains'])
        row=dict(representation=representation,engine=engine,exact_parity=True,compact_full_replay=True,retained_divergences=div,conditional_estimates=v.mean((0,1)).tolist(),ordinary_estimates=o.mean((0,1)).tolist(),diagnostics=diag)
        if latent:row['latent_qualified']=bool(div==0 and np.all(abs(v.mean((0,1))-truth)<=tol) and np.all(abs(o.mean((0,1))-truth)<=tol) and all(c['rhat']<=1.01 and min(c['bulk'],c['tail'])>=400 for c in diag))
        rows.append(row);(root/'PROGRESS.json').write_text(json.dumps(rows,indent=2)+'\n');print(json.dumps({k:v for k,v in row.items() if k not in ['conditional_estimates','ordinary_estimates','diagnostics']}),flush=True)
assert all(hashlib.sha256(Path(f).read_bytes()).hexdigest()==h for f,h in hashes.items());passed=all(row.get('latent_qualified',True) for row in rows)
(root/'SUMMARY.json').write_text(json.dumps(dict(passed=passed,rows=rows,inputs=hashes,unchanged=True,binaries=binaries),indent=2)+'\n');assert passed,'Latent control failed'
