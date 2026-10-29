"""One bounded replicate with all failures retained and no outcome-based retries."""
import json,time,traceback,sys
from pathlib import Path
import numpy as np
from scipy.special import expit
from scipy.stats import nbinom
from models import generate,functional,decision,bandit_target
from inference import sample,laplace,functional_summary


def write(path,value):
    path.write_text(json.dumps(value,indent=2,allow_nan=False,default=lambda x:x.item() if isinstance(x,np.generic) else x.tolist())+'\n')


def baselines(p,candidate,seed):
    rng=np.random.default_rng(seed);out={}
    if candidate=='hierarchical_ab':
        y,n=p['y'],p['n'];out['separate_beta']=rng.beta(y+1,n-y+1,size=(4000,8,2))
        draws=rng.beta(y.sum(axis=0)+1,(n-y).sum(axis=0)+1,size=(4000,2))
        out['pooled_beta']=np.repeat(draws[:,None,:],8,axis=1)
    elif candidate=='revenue_ab':
        out['sample_mean']=np.array([[v.mean() for v in p['observations']]])
        out['bootstrap']=np.column_stack([rng.choice(v,size=(2000,len(v)),replace=True).mean(axis=1) for v in p['observations']])
    else:
        y=p['y'];empirical=np.quantile(y,.8,axis=1,method='inverted_cdf')
        shrink=(y.sum(axis=1)+5*y.mean())/(p['n']+5)
        # Direct fixed-policy evaluation; avoid pretending point quantiles are posterior draws.
        from models import inventory_cost
        mu=p['truth'];r=p['true_dispersion'];oracle=nbinom.ppf(.8,r,r/(r+mu));cost=inventory_cost(oracle,mu,r).mean()
        for name,q in [('empirical_quantile',empirical),('shrinkage_nb',nbinom.ppf(.8,5,5/(5+shrink)))]:
            regret=float((inventory_cost(q,mu,r)-inventory_cost(oracle,mu,r)).mean())
            out[name]=dict(action=q.tolist(),regret=regret,normalized_regret=regret/max(cost,1e-12))
        return out
    return {name:decision(p,values,candidate) for name,values in out.items()}


def run_static(p,candidate,seed,out,warmup,draws):
    result={};start=time.monotonic();result['baselines']=baselines(p,candidate,seed+10)
    result['baseline_seconds']=time.monotonic()-start
    start=time.monotonic();import nutpie,owalnuts
    result['framework_initialization_seconds']=time.monotonic()-start
    # Frozen random order reduces systematic timing order effects.
    methods=np.random.default_rng(seed+11).permutation(['nuts','walnuts','laplace'])
    result['method_order']=methods.tolist();result['methods']={}
    for i,method in enumerate(methods):
        try:
            method_seed=seed+100+['nuts','walnuts','laplace'].index(method)
            start=time.monotonic()
            if method=='laplace':q,info=laplace(p['target'],method_seed)
            else:
                raw,info=sample(p['target'],method,method_seed,warmup,draws)
                info['functional_summary']=functional_summary(p,raw,candidate)
                q=raw.reshape(-1,raw.shape[-1]);np.savez_compressed(out/f'{method}-draws.npz',draws=raw)
            values=functional(p,q,candidate);info['decision']=decision(p,values,candidate)
            info['posterior_functional_mean']=values.mean(axis=0).tolist()
            info['total_seconds']=time.monotonic()-start
            result['methods'][method]=info
        except Exception as exc:
            result['methods'][method]=dict(status='failed',qualified=False,error=repr(exc));(out/f'{method}-error.txt').write_text(traceback.format_exc())
        write(out/'PROGRESS.json',result)
    return result


def run_bandit(p,seed,out,warmup,draws):
    initialization=time.monotonic();import nutpie,owalnuts
    initialization=time.monotonic()-initialization
    policies={};order=np.random.default_rng(seed+11).permutation(['nuts','walnuts','laplace','ucb'])
    for method in order:
        start=time.monotonic();X=[p['X'][t,a] for t,a in enumerate(p['initial'])];y=[p['potential'][t,a] for t,a in enumerate(p['initial'])]
        actions=[];fits=[];regret=0.;rng=np.random.default_rng(seed+200+['nuts','walnuts','laplace','ucb'].index(method))
        try:
            for batch in range(4):
                target=bandit_target(X,y);s=seed+300+batch*10+['nuts','walnuts','laplace','ucb'].index(method)
                if method in ['nuts','walnuts']:
                    raw,info=sample(target,method,s,warmup,draws);q=raw.reshape(-1,4)
                    np.savez_compressed(out/f'{method}-batch{batch}-draws.npz',draws=raw)
                else:q,info=laplace(target,s)
                info['training_observations']=len(y);fits.append(info)
                # Fit uses observations strictly before this batch. All 20 actions
                # are chosen before rewards are appended; no future truth enters inference.
                for t in range(20+20*batch,40+20*batch):
                    features=p['X'][t]
                    if method=='ucb':
                        mean=np.asarray(info['mean']);cov=np.asarray(info['covariance'])
                        score=features@mean+1.96*np.sqrt(np.einsum('ij,jk,ik->i',features,cov,features))
                    else:score=features@q[rng.integers(len(q))]
                    a=int(np.argmax(score));actions.append(a)
                    regret+=float(p['truth'][t].max()-p['truth'][t,a])
                for t,a in zip(range(20+20*batch,40+20*batch),actions[-20:]):X.append(p['X'][t,a]);y.append(p['potential'][t,a])
            policies[method]=dict(status='ok',qualified=all(f['qualified'] for f in fits),strict_reference_qualified=all(f.get('strict_reference_qualified',False) for f in fits),fits=fits,
                decision=dict(action=actions,regret=regret/80,normalized_regret=regret/float(p['truth'][20:].max(axis=1).sum())),total_seconds=time.monotonic()-start)
        except Exception as exc:
            policies[method]=dict(status='failed',qualified=False,error=repr(exc),fits=fits,total_seconds=time.monotonic()-start)
            (out/f'{method}-error.txt').write_text(traceback.format_exc())
        write(out/'PROGRESS.json',dict(methods=policies))
    return dict(method_order=order.tolist(),methods=policies,baselines={},framework_initialization_seconds=initialization,scope='80 sequential decisions after 20 common randomized observations; four 20-decision updates; policies have their own histories')


def run(candidate,scenario,replicate,output,warmup=500,draws=750,pilot=False):
    from models import CANDIDATES,SCENARIOS
    out=Path(output);out.mkdir(parents=True,exist_ok=False)
    seed=(539100000 if pilot else 529100000)+CANDIDATES.index(candidate)*1000000+SCENARIOS.index(scenario)*100000+replicate*1000
    start=time.monotonic();p=generate(candidate,scenario,seed)
    inputs={k:v for k,v in p.items() if k!='target'}
    if 'target' in p:inputs['target']=dict(kind=p['target'].kind,data=p['target'].data)
    write(out/'INPUT.json',inputs)
    write(out/'START.json',dict(candidate=candidate,scenario=scenario,replicate=replicate,seed=seed,warmup=warmup,draws=draws,pilot=pilot))
    if candidate=='contextual_bandit':result=run_bandit(p,seed,out,warmup,draws)
    else:result=run_static(p,candidate,seed,out,warmup,draws)
    result.update(candidate=candidate,scenario=scenario,replicate=replicate,seed=seed,seconds=time.monotonic()-start,pilot=pilot)
    write(out/'RESULT.json',result)
    print(json.dumps(dict(candidate=candidate,scenario=scenario,replicate=replicate,seconds=result['seconds'],status={m:v['status'] for m,v in result['methods'].items()})),flush=True)


if __name__=='__main__':run(sys.argv[1],sys.argv[2],int(sys.argv[3]),sys.argv[4],int(sys.argv[5]),int(sys.argv[6]),len(sys.argv)>7 and sys.argv[7]=='pilot')
