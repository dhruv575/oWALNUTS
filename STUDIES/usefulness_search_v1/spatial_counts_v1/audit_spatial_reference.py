import hashlib
import itertools
import json
from pathlib import Path
import numpy as np
import arviz as az
import bridgestan as bs

out=Path(__file__).resolve().parent
original=Path('/home/ubuntu/lanes/spatial-counts-reference-20261031')
repair=original.with_name(original.name+'-v2')
smoke=original.with_name('spatial-counts-preflight-20261030')
for root in [original,repair]:
    for n,h in json.loads((root/'INPUT-HASHES.json').read_text()).items():
        assert hashlib.sha256(Path(n).read_bytes()).hexdigest()==h,n
sources={int(g):Path(p) for g,p in json.loads((repair/'GROUP-SOURCES.json').read_text()).items()}
assert sources=={g:(original if g==0 else repair)/'results'/str(g) for g in range(4)}
summary=json.loads((repair/'results/SUMMARY.json').read_text())
summary_supervision=json.loads((repair/'summary-supervision/SUPERVISION.json').read_text())
assert summary_supervision['status']=='exited' and summary_supervision['exit_code']==0 and summary_supervision['group_drained']
model=bs.StanModel(str(smoke/'spatial_gp_model.so'),data=(original/'GP-TRAIN.json').read_text(),seed=1)
names=model.param_names(include_tp=True,include_gq=False)
ix=[names.index(n) for n in ['rho','alpha']+[f'beta.{j}' for j in range(1,4)]+[f'f.{j}' for j in range(1,201)]]

def stats(v):
    ds=az.convert_to_dataset({'p':v})
    return dict(mean=v.mean((0,1)),sd=v.reshape(-1,405).std(0,ddof=1),
                rhat=np.asarray(az.rhat(ds,method='rank').p),bulk=np.asarray(az.ess(ds,method='bulk').p),
                tail=np.asarray(az.ess(ds,method='tail').p),mcse=np.asarray(az.mcse(ds,method='mean').p))

rows=[];values=[];statistics=[]
for g,root in sorted(sources.items()):
    supervision=json.loads((root/'SUPERVISION.json').read_text()) if (root/'SUPERVISION.json').exists() else {}
    complete=supervision.get('status')=='exited' and supervision.get('exit_code')==0 and supervision.get('group_drained')
    if not complete:
        rows.append(dict(group=g,complete=False,qualified=False,supervision=supervision));continue
    row=json.loads((root/'SUMMARY.json').read_text());cfg=json.loads((root/'INPUT.json').read_text())
    assert row['seed']==952200001+g and cfg['seed']==row['seed']
    a=np.load(root/'DRAWS-STATS.npz');q=a['sample_stats__unconstrained_draw']
    assert q.shape==(4,2000,205) and np.isfinite(q).all()
    if g<2:
        expected=dict(draws=2000,tune=2000,chains=4,cores=4,seed=952200001+g,save_warmup=True,
                      progress_bar=False,adaptation='diag',target_accept=.999,maxdepth=12,
                      store_unconstrained=True,step_size_jitter=0.)
        assert cfg==expected
        div=int(a['sample_stats__diverging'].sum())
        assert row['calls']['gradient']>=sum(a[k+'__n_steps'].sum() for k in ['sample_stats','warmup_sample_stats'])
    else:
        assert cfg['warmup']==2000 and cfg['draws']==2000 and cfg['arm']=='dense' and cfg['target_accept']==.95
        assert np.array_equal(cfg['starts'],np.random.default_rng(952200001+g).uniform(-2,2,(4,205)))
        raw=json.loads((root/'RAW.json').read_text());assert np.array_equal(q,raw['draws'])
        div=int(raw['retained_divergences']);assert raw['target_calls']==row['calls']['gradient']
    assert div==row['divergences'] and all(row['calls'][k]==0 for k in ['value','hessian','hvp'])
    saved=np.load(root/'FUNCTIONALS.npz')['values'];assert saved.shape==(4,2000,405) and np.isfinite(saved).all()
    maximum=0.
    for rawq,want in zip(q.reshape(-1,205),saved.reshape(-1,405)):
        v=np.asarray(model.param_constrain(rawq,include_tp=True,include_gq=False))[ix]
        physical=np.r_[v,np.exp(v[5:])]
        assert np.allclose(physical,want,rtol=1e-10,atol=1e-10)
        maximum=max(maximum,float(np.max(abs(physical-want)/np.maximum(1,abs(want)))))
    st=stats(saved)
    for k,v in st.items():assert np.allclose(v,row['stats'][k],rtol=1e-10,atol=1e-10),(g,k)
    qualified=all(np.isfinite(v).all() for v in st.values()) and max(st['rhat'])<=1.01 and min(st['bulk'])>=1000 and min(st['tail'])>=1000 and div==0
    assert bool(qualified)==row['passed']
    rows.append(dict(group=g,complete=True,qualified=bool(qualified),rhat=float(max(st['rhat'])),
                     bulk=float(min(st['bulk'])),tail=float(min(st['tail'])),divergences=div,
                     physical_max_scaled_error=maximum,seconds=row['seconds']))
    values.append(saved);statistics.append(st)
    print(json.dumps(rows[-1]),flush=True)
qualified=False;pairs=[]
if all(r['qualified'] for r in rows):
    st=stats(np.concatenate(values))
    for a,b in itertools.combinations(statistics,2):
        delta=abs(a['mean']-b['mean'])
        pairs.append(dict(max_z=float(max(delta/np.sqrt(a['mcse']**2+b['mcse']**2))),
                          max_mean_sd=float(max(delta/st['sd'])),
                          max_relative_sd=float(max(abs(a['sd']-b['sd'])/((a['sd']+b['sd'])/2)))))
    checks=dict(finite=all(np.isfinite(v).all() for v in st.values()),rhat=max(st['rhat'])<=1.01,
                bulk=min(st['bulk'])>=4000,tail=min(st['tail'])>=2000,mcse=max(st['mcse']/st['sd'])<=.02,
                pairs=all(p['max_z']<=4 and p['max_mean_sd']<=.05 and p['max_relative_sd']<=.1 for p in pairs))
    assert {k:bool(v) for k,v in checks.items()}==summary['checks']
    for k,v in st.items():assert np.allclose(v,summary['stats'][k],rtol=1e-10,atol=1e-10)
    qualified=bool(all(checks.values()))
assert qualified==summary['passed']
result=dict(audit_passed=True,reference_qualified=qualified,groups=rows,pairs=pairs,
            scope='Training spatial posterior diagnostics; no predictive or practical-value claim',
            administrative_failures_preserved=[1,2,3],auditor_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
(out/'AUDIT.json').write_text(json.dumps(result,indent=2)+'\n')
(out/'RESULT.md').write_text('# Spatial reference attempt\n\nIndependent raw audit passed. Reference qualified: '+str(qualified)+'.\n\n'+
    '\n'.join('- Group '+str(r['group'])+': '+json.dumps(r) for r in rows)+'\n\nNo heldout scores were computed.\n')
