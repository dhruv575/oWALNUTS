"""Exact-marginal controls for quantile MCSE; not validation of MCMC accuracy.

No numerical stack is imported until run(). Gaussian AR1 starts in stationarity;
t5 uses a monotone Gaussian copula, retaining known marginal quantiles.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import statistics
import time

TIERS=[1000,2000,4000,8000]


def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def save_new(path,value):
    with Path(path).open('x') as handle:json.dump(value,handle,indent=2,allow_nan=False)


def validate_spec(spec):
    tiers=spec.get('tiers',[])
    if spec.get('chains')!=4 or not tiers or any(isinstance(n,bool) or not isinstance(n,int) or n<8 for n in tiers) or any(b<=a for a,b in zip(tiers,tiers[1:])):raise ValueError('Unsupported chains/tiers')
    if spec.get('health')!={'rhat_max':1.01,'bulk_ess_min':400,'tail_ess_min':400} or spec.get('relative_mcse')!=.02:raise ValueError('Unsupported health or precision configuration')
    policies={f'fixed_{n}' for n in tiers}|{'prefix_first_pass','restart_first_pass'}
    ids=set();seeds=set()
    if not spec.get('cells'):raise ValueError('No expected control cells')
    for cell in spec['cells']:
        key=cell.get('id')
        if not isinstance(key,str) or not key or key in ids or Path(key).name!=key or key in ('.','..'):raise ValueError('Unsafe or duplicate cell ID')
        ids.add(key)
        if cell.get('marginal') not in ('normal','student_t5') or isinstance(cell.get('rho'),bool) or cell.get('rho') not in (0.,.9,.99) or cell.get('policy') not in policies:raise ValueError('Unknown marginal, rho or policy')
        required=4*len(tiers) if cell['policy']=='restart_first_pass' else 4
        if len(cell.get('seeds',[]))!=required:raise ValueError('Incorrect stream count')
        for value in cell['seeds']:
            if isinstance(value,bool) or not isinstance(value,int) or not 0<=value<2**32 or value in seeds:raise ValueError('Invalid or duplicate stream')
            seeds.add(value)


def check_binding(path,original,spec):
    if digest(path)!=original or path.with_suffix('.sha256').read_text().strip()!=original:raise ValueError('Plan or sidecar changed')
    if digest(__file__)!=spec['source_sha256']:raise ValueError('Control source changed')


def plan(seed,replicates=200,tiers=None):
    tiers=TIERS if tiers is None else tiers
    if isinstance(seed,bool) or not isinstance(seed,int) or seed<0:raise ValueError('Nonnegative integer seed required')
    if isinstance(replicates,bool) or not isinstance(replicates,int) or replicates<2:raise ValueError('At least two replicates required')
    if not tiers or any(isinstance(n,bool) or not isinstance(n,int) or n<8 for n in tiers) or any(b<=a for a,b in zip(tiers,tiers[1:])):raise ValueError('Increasing integer tiers >=8 required')
    cells=[];next_seed=seed
    for marginal in ['normal','student_t5']:
        for rho in [0.,.9,.99]:
            for policy in [f'fixed_{n}' for n in tiers]+['prefix_first_pass','restart_first_pass']:
                for replicate in range(replicates):
                    batches=len(tiers) if policy=='restart_first_pass' else 1
                    seeds=list(range(next_seed,next_seed+4*batches));next_seed+=len(seeds)
                    cells.append(dict(id=f'{marginal}-rho{rho}-{policy}-{replicate:04d}',marginal=marginal,rho=rho,policy=policy,seeds=seeds))
    return dict(schema='exact-endpoint-controls/v1',frozen=False,phase='exploratory',qualified=False,
        source_sha256=digest(__file__),replicates=replicates,tiers=tiers,chains=4,cells=cells,
        health=dict(rhat_max=1.01,bulk_ess_min=400,tail_ess_min=400),relative_mcse=.02,
        interpretation='Known stationary marginal controls only; no validation of posterior exploration, model calibration, or market usefulness',
        policy_notes='Each fixed_N uses independent streams at that declared length; prefix reuses stationary chain prefixes; restart generates independent four-chain batch at each tier. All policies have independent replicate streams.')


def summarize(rows,expected,finite_estimator_only=False):
    if len({r['id'] for r in rows})!=len(rows) or set(r['id'] for r in rows)-set(expected):raise ValueError('Duplicate or unexpected control ID')
    good=[r for r in rows if r.get('status','completed')=='completed' and (r.get('finite_estimator') is True if finite_estimator_only else r.get('usable') is True)]
    output=dict(expected=len(expected),recorded=len(rows),usable=len(good),usable_rate=len(good)/len(expected),
        missing_ids=sorted(set(expected)-{r['id'] for r in rows}),conditional_on_usable=not finite_estimator_only,scope='All finite stationary estimates irrespective of health; not usable inference outputs' if finite_estimator_only else 'Usable procedure outputs',endpoints={})
    for j,p in enumerate([.05,.95]):
        if not good:continue
        values=[r['estimate'][j] for r in good];errors=[r['mcse'][j] for r in good];delta=[r['estimate'][j]-r['truth'][j] for r in good]
        meanvar=statistics.mean(e*e for e in errors)
        output['endpoints'][str(p)]=dict(mean_error=statistics.mean(delta),rmse=math.sqrt(statistics.mean(e*e for e in delta)),
            empirical_sd=statistics.stdev(values) if len(values)>1 else None,
            mean_reported_mcse=statistics.mean(errors),mcse_calibration_ratio=math.sqrt(statistics.variance(values)/meanvar) if len(values)>1 and meanvar>0 else None,
            usable_with_error_le_04_true_width_rate=sum(abs(r['estimate'][j]-r['truth'][j])<=.04*(r['truth'][1]-r['truth'][0]) for r in good)/len(expected))
    return output


def run(plan_path,out):
    import numpy as np
    import scipy
    from scipy.special import ndtr
    from scipy.signal import lfilter
    from scipy.stats import norm,t
    import arviz as az
    path=Path(plan_path);original=digest(path);spec=json.loads(path.read_text())
    validate_spec(spec)
    if spec.get('frozen') is not True or path.with_suffix('.sha256').read_text().strip()!=original:raise ValueError('Frozen plan and sidecar required')
    if spec['source_sha256']!=digest(__file__):raise ValueError('Control source changed')
    out=Path(out);out.mkdir(parents=True,exist_ok=False)
    versions=dict(numpy=np.__version__,scipy=scipy.__version__,arviz=az.__version__)
    if versions!=spec.get('software'):raise ValueError('Freeze exact numerical software versions before execution')
    allrows=[]
    for cell in spec['cells']:
        check_binding(path,original,spec)
        start=time.perf_counter();row=dict(cell,id=cell['id'],status='failed',usable=False,attempts=[])
        save_new(out/(cell['id']+'-started.json'),dict(plan_sha256=original,cell=cell))
        try:
            distribution=norm if cell['marginal']=='normal' else t(df=5)
            row['truth']=distribution.ppf([.05,.95]).tolist();full=None
            fixed=cell['policy'].startswith('fixed_')
            lengths=[int(cell['policy'].split('_')[1])] if fixed else spec['tiers']
            for index,n in enumerate(lengths):
                if full is None or cell['policy']=='restart_first_pass':
                    length=n if fixed or cell['policy']=='restart_first_pass' else spec['tiers'][-1]
                    offset=4*index if cell['policy']=='restart_first_pass' else 0
                    z=np.empty((4,length));rho=cell['rho']
                    for c in range(4):
                        rng=np.random.default_rng(cell['seeds'][offset+c])
                        innovations=rng.normal(size=length)*np.sqrt(1-rho*rho)
                        innovations[0]/=np.sqrt(1-rho*rho)
                        z[c]=lfilter([1.],[1.,-rho],innovations)
                    if cell['marginal']=='normal':full=z
                    else:
                        probabilities=ndtr(z)
                        if np.any((probabilities<=0)|(probabilities>=1)):raise ValueError('Finite-precision copula CDF saturated; do not clip silently')
                        full=distribution.ppf(probabilities)
                q=full[:,:n]
                estimates=np.quantile(q,[.05,.95]);mcse=np.array([float(az.mcse(q,method='quantile',prob=p)) for p in [.05,.95]])
                if not np.isfinite(estimates).all() or not np.isfinite(mcse).all():raise ValueError('Nonfinite quantile estimator or MCSE')
                rhat=float(az.rhat(q,method='rank'));bulk=float(az.ess(q,method='bulk'));tail=float(az.ess(q,method='tail',prob=(.05,.95)))
                healthy=bool(np.isfinite([rhat,bulk,tail]).all() and rhat<=1.01 and min(bulk,tail)>=400)
                width=estimates[1]-estimates[0]
                precise=bool(np.isfinite(mcse).all() and np.all(mcse>=0) and width>0 and max(mcse)<=.02*width)
                passed=healthy and precise
                row['attempts'].append(dict(draws=n,rhat=rhat if math.isfinite(rhat) else None,bulk_ess=bulk if math.isfinite(bulk) else None,tail_ess=tail if math.isfinite(tail) else None,healthy=healthy,precision_pass=passed))
                row.update(finite_estimator=True,estimate=estimates.tolist(),mcse=mcse.tolist(),healthy=healthy,precision_pass=passed,
                    usable=healthy if fixed else passed)
                if not fixed and passed:break
            row['status']='completed'
        except Exception as exc:row.update(status='failed',usable=False,finite_estimator=False,error=f'{type(exc).__name__}: {exc}')
        row['seconds']=time.perf_counter()-start;save_new(out/(cell['id']+'.json'),row);allrows.append(row)
    check_binding(path,original,spec)
    groups={}
    for cell in spec['cells']:
        key=f"{cell['marginal']}/{cell['rho']}/{cell['policy']}";groups.setdefault(key,[]).append(cell['id'])
    save_new(out/'summary.json',dict(phase='exploratory',qualified=False,software=versions,plan_sha256=original,
        fixed_policy_note='Fixed-length usable means healthy, regardless of precision pass; stopped-policy usable requires first-pass success',
        groups={k:dict(procedure=summarize([r for r in allrows if r['id'] in ids],ids),
            finite_fixed_length_estimator=summarize([r for r in allrows if r['id'] in ids],ids,True) if '/fixed_' in k else None) for k,ids in groups.items()}))


def main():
    p=argparse.ArgumentParser(description=__doc__);sub=p.add_subparsers(dest='action',required=True)
    a=sub.add_parser('plan');a.add_argument('--seed',type=int,required=True);a.add_argument('--replicates',type=int,default=200);a.add_argument('--out',type=Path,required=True)
    a=sub.add_parser('run');a.add_argument('--plan',type=Path,required=True);a.add_argument('--out',type=Path,required=True)
    args=p.parse_args()
    if args.action=='plan':save_new(args.out,plan(args.seed,args.replicates))
    else:run(args.plan,args.out)


if __name__=='__main__':main()
