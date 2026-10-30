import hashlib,json
from pathlib import Path
import numpy as np,arviz as az,bridgestan as bs
base=Path(__file__).resolve().parent;root=base/'sampler_screen_remote01';runtime=base.parent/'metric_blocks/local_recovery/gp_aws_runtime_bundle01'
refaudit=json.loads((base/'REFERENCE-AUDIT.json').read_text());assert refaudit['audit_passed'] and refaudit['reference_qualified'];ref=json.loads((base/'reference_remote01/results/SUMMARY.json').read_text())['stats']
for n,h in json.loads((root/'INPUT-HASHES.json').read_text()).items():
    prefix='/home/ubuntu/lanes/real-counts-sampler-screen-20261030/'
    if n.startswith(prefix):f=root/n[len(prefix):]
    elif '/preflight/' in n:f=runtime.parent/'gp_aws_runtime_preflight01'/n.split('/preflight/',1)[1]
    else:f=runtime/n.split('/gp-portable-runtime-20261030/',1)[1]
    assert hashlib.sha256(f.read_bytes()).hexdigest()==h,n
summary=json.loads((root/'results/SUMMARY.json').read_text());assert summary['completed'] and len(summary['rows'])==4
target=bs.StanModel(str(runtime/'models/raw.so'),data=(root/'GP-TRAIN.json').read_text(),seed=1);names=target.param_names(include_tp=True,include_gq=False);ix=[names.index(n) for n in ['rho','alpha']+[f'f.{j}' for j in range(1,80)]];rows=[]
for g in range(4):
    out=root/'results'/str(g);s=json.loads((out/'SUPERVISION.json').read_text());complete=s['exit_code']==0 and s['group_drained'] and (out/'SUMMARY.json').exists()
    if not complete:rows.append(dict(group=g,qualified=False,complete=False,supervision=s));continue
    result=json.loads((out/'SUMMARY.json').read_text());assert result['seed']==951500001+g;cfg=json.loads((out/'INPUT.json').read_text());assert cfg['seed']==951500001+g
    a=np.load(out/'DRAWS-STATS.npz');q=a['sample_stats__unconstrained_draw'];assert q.shape==(4,4000,81) and np.isfinite(q).all()
    if g<3:
        assert cfg['draws']==4000 and cfg['tune']==1100 and cfg['adaptation']=='diag' and cfg['target_accept']==[.9,.95,.99][g] and cfg['maxdepth']==10
        div=int(a['sample_stats__diverging'].sum());assert result['calls']['gradient']>=sum(a[k+'__n_steps'].sum() for k in ['sample_stats','warmup_sample_stats'])
    else:
        raw=json.loads((out/'RAW.json').read_text());assert np.array_equal(q,raw['draws']) and result['calls']['gradient']==raw['target_calls'];div=int(raw['retained_divergences']);assert cfg['warmup']==1100 and cfg['draws']==4000 and cfg['target_accept']==.9 and cfg['arm']=='dense'
    assert div==result['divergences']
    physical=np.asarray([target.param_constrain(x,include_tp=True,include_gq=False)[ix] for x in q.reshape(-1,81)]).reshape(4,4000,81);v=np.load(out/'FUNCTIONALS.npz')['values'];assert np.allclose(np.concatenate([physical,np.exp(physical[:,:,2:])],axis=2),v,rtol=1e-10,atol=1e-10)
    ds=az.convert_to_dataset({'p':v});st=dict(mean=v.mean((0,1)),sd=v.reshape(-1,160).std(0,ddof=1),rhat=np.asarray(az.rhat(ds,method='rank').p),bulk=np.asarray(az.ess(ds,method='bulk').p),tail=np.asarray(az.ess(ds,method='tail').p),mcse=np.asarray(az.mcse(ds,method='mean').p))
    for k,x in st.items():assert np.allclose(x,result['stats'][k],rtol=1e-10,atol=1e-10),(g,k)
    delta=abs(st['mean']-ref['mean']);z=delta/np.sqrt(st['mcse']**2+np.array(ref['mcse'])**2);err=delta/ref['sd'];sderr=abs(st['sd']/np.array(ref['sd'])-1)
    checks=dict(finite=all(np.isfinite(x).all() for x in [*st.values(),z,err,sderr]),rhat=max(st['rhat'])<=1.01,bulk=min(st['bulk'])>=400,tail=min(st['tail'])>=400,divergences=div==0,mean=max(err)<=.1,sd=max(sderr)<=.1,z=max(z)<=4)
    rows.append(dict(group=g,qualified=bool(all(checks.values())),checks={k:bool(x) for k,x in checks.items()},divergences=div,max_z=float(max(z)),max_mean_sd=float(max(err)),max_sd_relative=float(max(sderr)),min_bulk=float(min(st['bulk'])),min_tail=float(min(st['tail'])),max_rhat=float(max(st['rhat'])),ess_per_gradient=float(min(st['bulk'])/result['calls']['gradient'])))
eligible=[x for x in rows if x['group']<3 and x['qualified']];selected=max(eligible,key=lambda x:(x['ess_per_gradient'],x['group']))['group'] if eligible else None
result=dict(audit_passed=True,rows=rows,selected_native_group=selected,selected_native_acceptance=[.9,.95,.99][selected] if selected is not None else None,scope='Exposed-data settings screen; fresh confirmation required',auditor_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
(base/'SAMPLER-SCREEN-AUDIT.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result),flush=True)
