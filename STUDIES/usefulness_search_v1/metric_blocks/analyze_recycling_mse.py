import json
from pathlib import Path
import numpy as np
from scipy.integrate import quad
from scipy.special import ndtr,ndtri
study=Path(__file__).resolve().parent;root=study/'local_recovery/recycling_mse01'
normal=lambda z: np.exp(-z*z/2)/np.sqrt(2*np.pi)
integrand=lambda z:ndtr(-2*np.exp(-1.5*z))*normal(z)
tail1,e1=quad(integrand,-12,12,epsabs=1e-12,epsrel=1e-12)
tail2,e2=quad(integrand,-12,12,epsabs=1e-10,epsrel=1e-10)
tail3,e3=quad(lambda p:ndtr(-2*np.exp(-1.5*ndtri(p))),0,1,epsabs=1e-12,epsrel=1e-12)
assert abs(tail1-tail2)<1e-10 and abs(tail1-tail3)<1e-10 and max(e1,e3)<1e-10
summary=json.loads((root/'SUMMARY.json').read_text());assert len(summary['rows'])==96 and all(r['completed'] for r in summary['rows'])
indices=np.random.Generator(np.random.PCG64(941320001)).integers(0,64,size=(10000,64))
def ratio(a,b,cost):
    estimate=float(a.mean()/b.mean());boots=a[indices].mean(axis=1)/b[indices].mean(axis=1);ci=np.quantile(boots,[.025,.975]).tolist()
    return dict(ratio=estimate,ci95=ci,cost_adjusted=estimate/cost,cost_adjusted_ci95=(np.array(ci)/cost).tolist(),split_ratios=[float(a[:32].mean()/b[:32].mean()),float(a[32:].mean()/b[32:].mean())])
targets=[]
for target in ['analytic_rotated_gaussian','noncentered','funnel']:
    d=2 if target=='analytic_rotated_gaussian' else 10;estimates=[[],[]];costs={arm:dict(worker=0.,sampler=0.,bytes=0,calls=0,divergences=0,depth_caps=0) for arm in ['original','observed']}
    for batch in range(16):
        data={}
        for arm in costs:
            folder=root/f'{target}-{batch:02d}-{arm}';data[arm]=json.loads((folder/'RAW.json').read_text());s=json.loads((folder/'SUPERVISION.json').read_text());assert s['exit_code']==0 and s['group_drained']
            c=costs[arm];c['worker']+=s['elapsed_seconds'];c['sampler']+=sum(x['seconds'] for x in data[arm]['chains']);c['bytes']+=(folder/'RAW.json').stat().st_size;c['calls']+=data[arm]['target_calls'];c['divergences']+=sum(x['retained_divergences'] for x in data[arm]['chains']);c['depth_caps']+=sum(x['work']['maximum_depth_stops'] for x in data[arm]['chains'])
        for a,b in zip(data['original']['chains'],data['observed']['chains']):
            for k in a:
                if k!='seconds':assert a[k]==b[k],(target,batch,k)
            x=np.asarray(a['draws']);v=np.asarray(b['recycled']);assert x.shape==(1000,d) and v.shape==(1000,4*d) and np.isfinite(v).all()
            estimates[0].append(np.concatenate([x.mean(axis=0),(x*x).mean(axis=0),(x<0).mean(axis=0),(x<-2).mean(axis=0)]));estimates[1].append(v.mean(axis=0))
    assert costs['original']['calls']==costs['observed']['calls']
    variance=np.array([2.,2.] if d==2 else [9.]+([np.exp(4.5)]*9 if target=='funnel' else [1.]*9))
    tails=ndtr(-2/np.sqrt(variance))
    if target=='funnel':tails[1:]=tail1
    truth=np.concatenate([np.zeros(d),variance,np.full(d,.5),tails]);scale=np.concatenate([np.sqrt(variance),variance,np.ones(2*d)])
    est=np.asarray(estimates);error=est-truth;squared=(error/scale)**2;cost=costs['observed']['worker']/costs['original']['worker'];families=[];functionals=[]
    for j,name in enumerate(['mean','second_moment','below_zero','below_minus2']):
        section=slice(j*d,(j+1)*d);flags=[]
        for i in range(d):
            k=j*d+i;z=error[:,:,k].mean(axis=1)/(error[:,:,k].std(axis=1,ddof=1)/8)
            flags.append(bool(np.any(np.abs(z)>4.5)))
            functionals.append(dict(family=name,coordinate=i,truth=float(truth[k]),bias_z=z.tolist(),bias_flag=flags[-1],mse_original=float(np.mean(error[0,:,k]**2)),mse_observed=float(np.mean(error[1,:,k]**2)),**ratio(squared[0,:,k],squared[1,:,k],cost)))
        result=ratio(squared[0,:,section].mean(axis=1),squared[1,:,section].mean(axis=1),cost)
        result.update(family=name,bias_flag=any(flags),advance=result['ci95'][0]>1.2 and result['cost_adjusted_ci95'][0]>1 and not any(flags));families.append(result)
    targets.append(dict(target=target,costs=costs,worker_cost_ratio=cost,sampler_cost_ratio=costs['observed']['sampler']/costs['original']['sampler'],families=families,functionals=functionals,replicate_estimates=est.tolist(),truth=truth.tolist()))
report=dict(exploratory=True,replicates=64,transitions=1000,quadrature=dict(tail=tail1,alternate=tail3,error_bounds=[e1,e2,e3]),targets=targets)
(study/'RECYCLING-MSE-ANALYSIS.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
lines=['# Replicated recycling MSE screen','','| Target | Family | MSE ratio (95% CI) | Worker cost ratio | Cost-adjusted ratio (95% CI) | Advance |','|---|---|---|---|---|---|']
for t in targets:
    for f in t['families']:
        lines.append(f"| {t['target']} | {f['family']} | {f['ratio']:.3f} [{f['ci95'][0]:.3f}, {f['ci95'][1]:.3f}] | {t['worker_cost_ratio']:.3f} | {f['cost_adjusted']:.3f} [{f['cost_adjusted_ci95'][0]:.3f}, {f['cost_adjusted_ci95'][1]:.3f}] | {f['advance']} |")
lines+=['','Ratios above one favor recycling. Worker cost includes serialization/output. Intervals are exploratory paired-replicate bootstrap intervals, conditional on measured cost; not simultaneous intervals or held-out confirmation. Exact stationary starts and fixed known settings do not test a cold workflow. All functionals, split-half sensitivity, bias flags and health events are preserved in the analysis JSON. Native/recycled NUTS comparisons remain outstanding.']
(study/'RECYCLING-MSE-REPORT.md').write_text('\n'.join(lines)+'\n');print('\n'.join(lines))
