import hashlib,json,os
from pathlib import Path
import numpy as np,arviz as az,bridgestan as bs
from scipy.special import logsumexp
from conditional_proposal import ConditionalProposal
base=Path(os.environ.get('REAL_COUNTS_AUDIT_ROOT',str(Path(__file__).resolve().parent)));root=base/'importance_remote01';runtime=Path(os.environ.get('GP_RUNTIME',str(base.parent/'metric_blocks/local_recovery/gp_aws_runtime_bundle01')));preflight=Path(os.environ.get('GP_RUNTIME_PREFLIGHT',str(runtime.parent/'gp_aws_runtime_preflight01')))
audit=json.loads((base/'REFERENCE-AUDIT.json').read_text());assert audit['audit_passed'] and audit['reference_qualified'];ref=json.loads((base/'reference_remote01/results/SUMMARY.json').read_text())['stats']
hashes=json.loads((root/'INPUT-HASHES.json').read_text())
for n,h in hashes.items():
    prefix='/home/ubuntu/lanes/real-counts-importance-20261030/'
    if n.startswith(prefix):f=root/n[len(prefix):]
    elif '/preflight/' in n:f=preflight/n.split('/preflight/',1)[1]
    else:f=runtime/n.split('/gp-portable-runtime-20261030/',1)[1]
    assert hashlib.sha256(f.read_bytes()).hexdigest()==h,n
assert hashlib.sha256((base/'conditional_proposal.py').read_bytes()).hexdigest()==hashlib.sha256((root/'conditional_proposal.py').read_bytes()).hexdigest()
summary=json.loads((root/'results/SUMMARY.json').read_text());assert summary['completed'] and len(summary['rows'])==2
target=bs.StanModel(str(runtime/'models/raw.so'),data=(root/'GP-TRAIN.json').read_text(),seed=1);names=target.param_names(include_tp=True,include_gq=False);ix=[names.index(n) for n in ['rho','alpha']+[f'f.{j}' for j in range(1,80)]];rows=[]
for rep in range(2):
    out=root/'results'/str(rep);s=json.loads((out/'SUPERVISION.json').read_text());assert s['exit_code']==0 and s['group_drained']
    result=json.loads((out/'SUMMARY.json').read_text());assert result['seed']==951400001+rep and result['counts']==dict(value=16384,gradient=0,hessian=0,hvp=0)
    a=np.load(out/'DRAWS.npz');q=a['q'];v=a['values'];assert q.shape==(16384,81) and v.shape==(16384,160)
    physical=np.asarray([target.param_constrain(x,include_tp=True,include_gq=False)[ix] for x in q]);regenerated=np.c_[physical,np.exp(physical[:,2:])];assert np.allclose(regenerated,v,rtol=1e-10,atol=1e-10)
    lt=np.asarray([target.log_density(x) for x in q]);assert np.allclose(lt,a['log_target'],rtol=1e-10,atol=1e-8)
    p=ConditionalProposal(json.loads((root/'GP-TRAIN.json').read_text()));prob,scores=p.grid();grid=np.load(out/'GRID.npz');assert np.allclose(prob,grid['prob'],rtol=1e-9,atol=1e-12) and np.allclose(scores,grid['scores'],rtol=1e-10,atol=1e-8)
    lq=[]
    for x in q:
        mode,C,_,_=p.solve(x[:2]);lq.append(p.hyper_logq(x[:2],grid['prob'])+p.conditional_logq(x[2:],mode,C))
    if not np.allclose(lq,a['log_proposal'],rtol=1e-9,atol=1e-7):
        failure=dict(audit_passed=False,rep=rep,check='proposal density reconstruction',max_abs_error=float(max(abs(np.asarray(lq)-a['log_proposal']))),failed_draws=int(np.sum(~np.isclose(lq,a['log_proposal'],rtol=1e-9,atol=1e-7))),runtime=str(runtime))
        (base/'IMPORTANCE-AUDIT-FAILURE.json').write_text(json.dumps(failure,indent=2)+'\n');print(json.dumps(failure),flush=True)
        raise AssertionError('Proposal density reconstruction mismatch')
    lw=a['log_target']-a['log_proposal'];assert np.array_equal(lw,a['log_weight']);w=np.exp(lw-logsumexp(lw));assert np.array_equal(w,a['weight'])
    mean=w@v;sd=np.sqrt(w@((v-mean)**2));mcse=np.sqrt(np.sum((w[:,None]*(v-mean))**2,axis=0));ess=float(1/(w@w));_,pk=az.psislw(lw)
    for k,x in dict(mean=mean,sd=sd,mcse=mcse).items():assert np.allclose(x,result['stats'][k],rtol=1e-10,atol=1e-10)
    assert np.isclose(ess,result['ess'],rtol=1e-12) and np.isclose(pk,result['pareto_k'],rtol=1e-12)
    delta=abs(mean-ref['mean']);z=delta/np.sqrt(mcse**2+np.array(ref['mcse'])**2);err=delta/ref['sd'];sderr=abs(sd/np.array(ref['sd'])-1)
    checks=dict(finite=all(np.isfinite(x).all() for x in [mean,sd,mcse,z,err,sderr,ess,pk]),ess=ess>=1000,pareto=pk<.7,mean=max(err)<=.1,sd=max(sderr)<=.1,z=max(z)<=4)
    rows.append(dict(rep=rep,qualified=bool(all(checks.values())),checks={k:bool(x) for k,x in checks.items()},ess=ess,pareto_k=float(pk),max_z=float(max(z)),max_mean_sd=float(max(err)),max_sd_relative=float(max(sderr))))
result=dict(audit_passed=True,all_qualified=all(x['qualified'] for x in rows),rows=rows,scope='Exact target and proposal density recomputed for all32768 draws;160 training quantities only; no clean timing comparison or predictive qualification',auditor_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
(base/'IMPORTANCE-AUDIT.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result),flush=True)
