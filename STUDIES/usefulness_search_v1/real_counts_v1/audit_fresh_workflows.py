import hashlib,json,os
from pathlib import Path
import numpy as np,arviz as az,bridgestan as bs
from scipy.special import logsumexp
from conditional_proposal import ConditionalProposal
base=Path(os.environ.get('REAL_COUNTS_AUDIT_ROOT',str(Path(__file__).resolve().parent)));root=base/'fresh_remote01';runtime=Path(os.environ.get('GP_RUNTIME',str(base.parent/'metric_blocks/local_recovery/gp_aws_runtime_bundle01')));preflight=Path(os.environ.get('GP_RUNTIME_PREFLIGHT',str(runtime.parent/'gp_aws_runtime_preflight01')))
audit=json.loads((base/'REFERENCE-AUDIT.json').read_text());assert audit['audit_passed'] and audit['reference_qualified'];ref=json.loads((base/'reference_remote01/results/SUMMARY.json').read_text())['stats']
for n,h in json.loads((root/'INPUT-HASHES.json').read_text()).items():
    prefix='/home/ubuntu/lanes/real-counts-fresh-workflows-20261030/'
    if n.startswith(prefix):f=root/n[len(prefix):]
    elif '/preflight/' in n:f=preflight/n.split('/preflight/',1)[1]
    else:f=runtime/n.split('/gp-portable-runtime-20261030/',1)[1]
    assert hashlib.sha256(f.read_bytes()).hexdigest()==h,n
assert hashlib.sha256((base/'conditional_proposal.py').read_bytes()).hexdigest()==hashlib.sha256((root/'conditional_proposal.py').read_bytes()).hexdigest()
summary=json.loads((root/'results/SUMMARY.json').read_text());assert summary['completed'] and [(x['rep'],x['method']) for x in summary['rows']]==[(0,'wal'),(0,'importance'),(0,'native'),(1,'native'),(1,'importance'),(1,'wal')]
target=bs.StanModel(str(runtime/'models/raw.so'),data=(root/'GP-TRAIN.json').read_text(),seed=1);names=target.param_names(include_tp=True,include_gq=False);ix=[names.index(n) for n in ['rho','alpha']+[f'f.{j}' for j in range(1,80)]];rows=[]
for item in summary['rows']:
    rep,method=item['rep'],item['method'];out=root/'results'/f'{rep}-{method}';s=json.loads((out/'SUPERVISION.json').read_text());complete=s['exit_code']==0 and s['group_drained'] and (out/'SUMMARY.json').exists();assert complete==item['completed']
    if not complete:rows.append(dict(rep=rep,method=method,qualified=False,completed=False,supervision=s));continue
    result=json.loads((out/'SUMMARY.json').read_text());assert result==item['result'] and result['seed']==951600001+rep
    timing=json.loads((out/'PROCESS-TIME.json').read_text());assert timing==item['timing'] and timing['returncode']==0
    if method=='importance':
        a=np.load(out/'DRAWS.npz');q=a['q'];v=a['values'];assert q.shape==(4096,81) and v.shape==(4096,160)
        assert result['counts']==dict(value=4096,gradient=0,hessian=0,hvp=0)
        lt=np.asarray([target.log_density(x) for x in q]);assert np.allclose(lt,a['log_target'],rtol=1e-10,atol=1e-8)
        p=ConditionalProposal(json.loads((root/'GP-TRAIN.json').read_text()));prob,scores=p.grid();grid=np.load(out/'GRID.npz');assert np.allclose(prob,grid['prob'],rtol=1e-9,atol=1e-12) and np.allclose(scores,grid['scores'],rtol=1e-10,atol=1e-8)
        lq=[]
        for x in q:
            mode,C,_,_=p.solve(x[:2]);lq.append(p.hyper_logq(x[:2],grid['prob'])+p.conditional_logq(x[2:],mode,C))
        assert np.allclose(lq,a['log_proposal'],rtol=1e-9,atol=1e-7)
        lw=a['log_target']-a['log_proposal'];assert np.array_equal(lw,a['log_weight']);w=np.exp(lw-logsumexp(lw));assert np.array_equal(w,a['weight'])
        mean=w@v;sd=np.sqrt(w@((v-mean)**2));mcse=np.sqrt(np.sum((w[:,None]*(v-mean))**2,axis=0));ess=float(1/(w@w));_,pk=az.psislw(lw);checks=dict(ess=ess>=1000,pareto=pk<.7);st=dict(mean=mean,sd=sd,mcse=mcse)
        assert np.isclose(ess,result['ess'],rtol=1e-12) and np.isclose(pk,result['pareto_k'],rtol=1e-12)
    else:
        a=np.load(out/'DRAWS-STATS.npz');q=a['sample_stats__unconstrained_draw'];v=np.load(out/'FUNCTIONALS.npz')['values'];assert q.shape==(4,4000,81) and v.shape==(4,4000,160)
        cfg=json.loads((out/'INPUT.json').read_text());assert cfg['seed']==951600001+rep and cfg['draws']==4000
        if method=='native':
            assert cfg==dict(draws=4000,tune=1100,chains=4,cores=4,seed=951600001+rep,save_warmup=True,progress_bar=False,adaptation='diag',target_accept=.99,maxdepth=10,store_unconstrained=True,step_size_jitter=0.)
            div=int(a['sample_stats__diverging'].sum());assert result['calls']['gradient']>=sum(a[k+'__n_steps'].sum() for k in ['sample_stats','warmup_sample_stats'])
        else:
            raw=json.loads((out/'RAW.json').read_text());assert np.array_equal(q,raw['draws']) and result['calls']['gradient']==raw['target_calls'];div=int(raw['retained_divergences']);assert cfg['warmup']==1100 and cfg['target_accept']==.9 and cfg['arm']=='dense';assert np.array_equal(cfg['starts'],np.random.default_rng(951600001+rep).uniform(-2,2,(4,81)))
        assert div==result['divergences'];ds=az.convert_to_dataset({'p':v});st=dict(mean=v.mean((0,1)),sd=v.reshape(-1,160).std(0,ddof=1),rhat=np.asarray(az.rhat(ds,method='rank').p),bulk=np.asarray(az.ess(ds,method='bulk').p),tail=np.asarray(az.ess(ds,method='tail').p),mcse=np.asarray(az.mcse(ds,method='mean').p));checks=dict(rhat=max(st['rhat'])<=1.01,bulk=min(st['bulk'])>=400,tail=min(st['tail'])>=400,divergences=div==0)
    physical=np.asarray([target.param_constrain(x,include_tp=True,include_gq=False)[ix] for x in q.reshape(-1,81)]);regenerated=np.c_[physical,np.exp(physical[:,2:])];assert np.allclose(regenerated,v.reshape(-1,160),rtol=1e-10,atol=1e-10)
    for k,x in st.items():assert np.allclose(x,result['stats'][k],rtol=1e-10,atol=1e-10),(rep,method,k)
    delta=abs(st['mean']-ref['mean']);z=delta/np.sqrt(st['mcse']**2+np.array(ref['mcse'])**2);err=delta/ref['sd'];sderr=abs(st['sd']/np.array(ref['sd'])-1);precision=float(max(st['mcse']/ref['sd']))
    checks.update(finite=all(np.isfinite(x).all() for x in [*st.values(),z,err,sderr]),mean=max(err)<=.1,sd=max(sderr)<=.1,z=max(z)<=4,precision=precision<=.025)
    rows.append(dict(rep=rep,method=method,qualified=bool(all(checks.values())),checks={k:bool(x) for k,x in checks.items()},seconds=timing['seconds'],max_mcse_refsd=precision,max_z=float(max(z)),max_mean_sd=float(max(err)),max_sd_relative=float(max(sderr)),divergences=div if method!='importance' else None))
allpass=all(x['qualified'] for x in rows);pairs=[]
if allpass:
    for rep in range(2):
        a={x['method']:x for x in rows if x['rep']==rep};ratio=max(x['max_mcse_refsd'] for x in a.values())/min(x['max_mcse_refsd'] for x in a.values());pair=dict(rep=rep,precision_ratio=ratio,precision_comparable=ratio<=1.5)
        if ratio<=1.5:pair.update(native_over_wal=a['native']['seconds']/a['wal']['seconds'],importance_over_wal=a['importance']['seconds']/a['wal']['seconds'])
        pairs.append(pair)
result=dict(audit_passed=True,all_qualified=allpass,rows=rows,descriptive_pairs=pairs,scope='Training accuracy and serial whole-process costs; two repeats, no predictive or practical advantage claim',auditor_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
(base/'FRESH-WORKFLOW-AUDIT.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result),flush=True)
