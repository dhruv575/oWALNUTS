"""Reconstruct all reference functionals from raw positions and recheck gates."""
import hashlib,itertools,json
from pathlib import Path
import numpy as np,arviz as az,bridgestan as bs
base=Path(__file__).resolve().parent;root=base/'reference_remote01';r=root/'results'
local=base.parent/'metric_blocks/local_recovery';runtime=local/'gp_aws_runtime_bundle01'
def mapped(n):
    for prefix,target in [('/home/ubuntu/lanes/real-counts-reference-20261030/',root),('/home/ubuntu/lanes/gp-portable-runtime-20261030/preflight/',local/'gp_aws_runtime_preflight01'),('/home/ubuntu/lanes/gp-portable-runtime-20261030/',runtime),('/home/ubuntu/lanes/gp-full-cost-20261030/',local/'gp_aws_full_remote01')]:
        if n.startswith(prefix):return target/n[len(prefix):]
    raise ValueError(n)
hashes=json.loads((root/'INPUT-HASHES.json').read_text())
for n,h in hashes.items():assert hashlib.sha256(mapped(n).read_bytes()).hexdigest()==h,(n,'input hash')
transfer=json.loads((root/'TRANSFER-MANIFEST.json').read_text())
for n,m in transfer.items():
    f=root/n;assert f.stat().st_size==m['bytes'] and hashlib.sha256(f.read_bytes()).hexdigest()==m['sha256'],n
summary=json.loads((r/'SUMMARY.json').read_text());rows=sorted(summary['rows'],key=lambda x:x['group']);assert [x['group'] for x in rows]==list(range(4))
supervision=json.loads((root/'summary-supervision/SUPERVISION.json').read_text());assert supervision['exit_code']==0 and supervision['group_drained']
model=bs.StanModel(str(runtime/'models/raw.so'),data=(root/'GP-TRAIN.json').read_text(),seed=1);assert model.param_unc_num()==81
names=model.param_names(include_tp=True,include_gq=False);ix=[names.index(n) for n in ['rho','alpha']+[f'f.{j}' for j in range(1,80)]]
def stats(v):
    ds=az.convert_to_dataset({'p':v});return dict(mean=v.mean((0,1)),sd=v.reshape(-1,160).std(0,ddof=1),rhat=np.asarray(az.rhat(ds,method='rank').p),bulk=np.asarray(az.ess(ds,method='bulk').p),tail=np.asarray(az.ess(ds,method='tail').p),mcse=np.asarray(az.mcse(ds,method='mean').p))
allv=[];audit=[];allstats=[]
for row in rows:
    g=row['group'];out=r/str(g);s=json.loads((out/'SUPERVISION.json').read_text())
    complete=s['exit_code']==0 and s['group_drained'] and (out/'SUMMARY.json').exists()
    if not complete:
        assert not row['passed'];audit.append(dict(group=g,complete=False,qualified=False,supervision=s));continue
    assert row==json.loads((out/'SUMMARY.json').read_text()) and row['seed']==951200001+g
    cfg=json.loads((out/'INPUT.json').read_text());a=np.load(out/'DRAWS-STATS.npz');q=a['sample_stats__unconstrained_draw'];assert q.shape==(4,8000,81) and np.isfinite(q).all()
    if g<2:
        assert cfg==dict(draws=8000,tune=2000,chains=4,cores=4,seed=951200001+g,save_warmup=True,progress_bar=False,adaptation='diag',target_accept=.999,maxdepth=12,store_unconstrained=True,step_size_jitter=0.)
        div=int(a['sample_stats__diverging'].sum());assert row['calls']['gradient']>=sum(a[k+'__n_steps'].sum() for k in ['sample_stats','warmup_sample_stats'])
    else:
        raw=json.loads((out/'RAW.json').read_text());assert np.array_equal(q,raw['draws']) and row['calls']['gradient']==raw['target_calls'];div=int(raw['retained_divergences'])
        assert cfg['seed']==951200001+g and cfg['warmup']==2000 and cfg['draws']==8000 and cfg['arm']=='dense' and cfg['target_accept']==.95
        assert np.array_equal(cfg['starts'],np.random.default_rng(951200001+g).uniform(-2,2,(4,81)))
    assert div==row['divergences'] and all(row['calls'][k]==0 for k in ['value','hessian','hvp'])
    physical=np.asarray([model.param_constrain(x,include_tp=True,include_gq=False)[ix] for x in q.reshape(-1,81)]).reshape(4,8000,81)
    v=np.concatenate([physical,np.exp(physical[:,:,2:])],axis=2);saved=np.load(out/'FUNCTIONALS.npz')['values'];assert np.isfinite(v).all() and np.allclose(v,saved,rtol=1e-10,atol=1e-10)
    # Use saved exact bits after reconstructing all functionals; avoids BLAS
    # platform roundoff affecting rank ties in an otherwise identical audit.
    st=stats(saved)
    for k,x in st.items():assert np.allclose(x,row['stats'][k],rtol=1e-10,atol=1e-10),(g,k)
    passed=all(np.isfinite(x).all() for x in st.values()) and max(st['rhat'])<=1.01 and min(st['bulk'])>=1000 and min(st['tail'])>=1000 and div==0
    assert bool(passed)==row['passed'];allv.append(saved);allstats.append(st)
    audit.append(dict(group=g,complete=True,qualified=bool(passed),rhat=float(max(st['rhat'])),bulk=float(min(st['bulk'])),tail=float(min(st['tail'])),divergences=div))
qualified=False
if all(x['qualified'] for x in audit):
    st=stats(np.concatenate(allv));pairs=[]
    for a,b in itertools.combinations(allstats,2):
        delta=abs(a['mean']-b['mean']);pairs.append(dict(max_z=float(max(delta/np.sqrt(a['mcse']**2+b['mcse']**2))),max_mean_sd=float(max(delta/st['sd'])),max_sd_relative=float(max(abs(a['sd']-b['sd'])/((a['sd']+b['sd'])/2)))))
    checks=dict(finite=all(np.isfinite(x).all() for x in st.values()),rhat=max(st['rhat'])<=1.01,bulk=min(st['bulk'])>=4000,tail=min(st['tail'])>=2000,mcse=max(st['mcse']/st['sd'])<=.02,pairs=all(x['max_z']<=4 and x['max_mean_sd']<=.05 and x['max_sd_relative']<=.1 for x in pairs))
    assert {k:bool(x) for k,x in checks.items()}==summary['checks']
    for k,x in st.items():assert np.allclose(x,summary['stats'][k],rtol=1e-10,atol=1e-10),k
    qualified=bool(all(checks.values()))
assert qualified==summary['passed']
result=dict(audit_passed=True,reference_qualified=qualified,groups=audit,scope='All raw training functionals and qualification gates; no predictive qualification',auditor_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
(base/'REFERENCE-AUDIT.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result),flush=True)
