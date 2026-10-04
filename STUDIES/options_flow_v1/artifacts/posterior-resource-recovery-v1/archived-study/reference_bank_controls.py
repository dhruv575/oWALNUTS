"""Prospective finite-bank uncertainty controls; analysis, never sampler evidence.

Small default is a cost/operating-characteristic pilot, not calibrated coverage.
Normal stationary AR1 fits have analytic N(shift,1) marginals. Shifted-backend
alternatives deliberately violate a common-target bank and should not resolve.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import time
from reference_bank import analyze


def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def save(path,value):
    with Path(path).open('x') as handle:json.dump(value,handle,indent=2,allow_nan=False)


def make_plan(seed=1900000000,trials=12):
    if not isinstance(trials,int) or isinstance(trials,bool) or trials<2:raise ValueError('At least two trials')
    cells=[];cursor=seed
    for rho in [0.,.9]:
        for shift in [0.,.5]:
            for i in range(trials):
                streams=list(range(cursor,cursor+17));cursor+=17
                cells.append(dict(id=f'rho{rho}-shift{shift}-{i:03d}',rho=rho,backend_b_shift=shift,fit_seeds=streams[:8],init_seeds=streams[8:16],bootstrap_seed=streams[16]))
    return dict(frozen=False,phase='exploratory',qualified=False,cells=cells,trials=trials,lengths=[128,256],fits_per_backend=4,
        bootstrap_replicates=1000,minimum_tail_count=2,alpha=.05,relative_half_width=.1,
        backend_equivalence_relative_width=.02,length_equivalence_relative_width=.1,
        worker_sha256=digest(__file__),bank_sha256=digest(Path(__file__).with_name('reference_bank.py')),
        caveat='Small pilot only: 12 outer trials cannot establish 95% coverage or rare false-resolution rate; four fits/backend and ~4 bootstrap draws per extreme tail are deliberately recorded finite-bank limitations',
        alternatives='BackendB shifted by.5 while declared target remains Normal(0,1); this is a misspecified-bank control, never valid target evidence')


def summarize(rows,expected):
    completed=[r for r in rows if r['status']=='completed'];resolved=[r for r in completed if r['bank_status']=='numerically_resolved_under_declared_checks']
    return dict(expected=expected,recorded=len(rows),completed=len(completed),resolved=len(resolved),
        unconditional_resolution_rate=len(resolved)/expected,
        simultaneous_endpoint_coverage_rate=sum(r['both_endpoints_cover_truth'] for r in completed)/expected,
        resolved_but_truth_outside_bounds_rate=sum(not r['both_endpoints_cover_truth'] for r in resolved)/expected,
        shifted_backend_false_resolution_rate=sum(r['backend_b_shift']!=0 for r in resolved)/expected,
        resolved_but_endpoint_error_over_budget_rate=sum(r['max_endpoint_error_over_width']>.1 for r in resolved)/expected,
        scope='All planned outer trials remain denominator; coverage measures returned simultaneous bank endpoint bounds even when precision/equivalence gates fail')


def run(plan_path,out):
    import numpy as np
    import scipy
    from scipy.signal import lfilter
    from scipy.stats import norm
    path=Path(plan_path);sha=digest(path);p=json.loads(path.read_text())
    if not p.get('frozen') or path.with_suffix('.sha256').read_text().strip()!=sha:raise ValueError('Frozen plan required')
    if p['worker_sha256']!=digest(__file__) or p['bank_sha256']!=digest(Path(__file__).with_name('reference_bank.py')):raise ValueError('Source changed')
    if p['software']!={'numpy':np.__version__,'scipy':scipy.__version__}:raise ValueError('Software differs')
    for filename,expected in p['source_files'].items():
        if digest(filename)!=expected:raise ValueError('Bound source changed')
    streams=[v for c in p['cells'] for v in c['fit_seeds']+c['init_seeds']+[c['bootstrap_seed']]]
    if len(set(streams))!=len(streams):raise ValueError('Control streams collide')
    out=Path(out);out.mkdir(parents=True,exist_ok=False);rows=[];truth=norm.ppf([.05,.95]);width=truth[1]-truth[0]
    for cell in p['cells']:
        start=time.perf_counter();row=dict(cell,status='failed')
        save(out/(cell['id']+'-started.json'),dict(plan_sha256=sha,cell=cell))
        try:
            if digest(path)!=sha or path.with_suffix('.sha256').read_text().strip()!=sha:raise ValueError('Plan changed')
            for filename,expected in p['source_files'].items():
                if digest(filename)!=expected:raise ValueError('Bound source changed')
            fits=[]
            for i,seed in enumerate(cell['fit_seeds']):
                n=p['lengths'][-1];rho=cell['rho'];rng=np.random.default_rng(seed)
                innovations=rng.normal(size=n)*np.sqrt(1-rho*rho)
                innovations[0]=np.random.default_rng(cell['init_seeds'][i]).normal()
                values=lfilter([1.],[1.,-rho],innovations)+(cell['backend_b_shift'] if i>=4 else 0.)
                fit=dict(id=str(i),backend='a' if i<4 else 'b',seed=seed,initialization_seed=cell['init_seeds'][i],fixture_sha256='analytic-normal',source_sha256=p['bank_sha256'],target_sha256='normal-zero-one',levels={})
                for length in p['lengths']:
                    distribution=dict(scale='unit',distribution_id='theta',draws=values[:length].tolist())
                    fit['levels'][str(length)]=dict(status='completed',healthy=True,draws_per_chain=length,endpoints={'lo':distribution,'hi':distribution})
                fits.append(fit)
            spec={key:p[key] for key in ['lengths','bootstrap_replicates','minimum_tail_count','alpha','relative_half_width','backend_equivalence_relative_width','length_equivalence_relative_width']}
            spec.update(fits=[{k:v for k,v in f.items() if k!='levels'} for f in fits],chains=1,source_sha256=p['bank_sha256'],target_sha256='normal-zero-one',numerical_policy='validated_estimate',candidate_streams=[],bootstrap_seed=cell['bootstrap_seed'],interval_pairs=[['lo','hi']],endpoints={name:dict(kind='parameter',distribution_id='theta',probability=prob,scale='unit') for name,prob in [('lo',.05),('hi',.95)]})
            bank=analyze(spec,fits)
            if 'endpoints' not in bank:raise ValueError('Bank analysis did not return uncertainty: '+str(bank['reasons']))
            bounds=[bank['endpoints'][name] for name in ['lo','hi']]
            row.update(status='completed',bank_status=bank['status'],bank_reasons=bank['reasons'],bounds=bounds,
                truth=truth.tolist(),both_endpoints_cover_truth=all(b['lower']<=q<=b['upper'] for b,q in zip(bounds,truth)),
                max_endpoint_error_over_width=max(abs(b['estimate']-q)/width for b,q in zip(bounds,truth)),
                shared_reference_covariance=float(np.cov(np.array([[r['lo'],r['hi']] for r in bank['joint_bootstrap_endpoints']]).T)[0,1]),
                health_note='Known stationary exact-marginal control; healthy=True is a construction flag, not an MCMC diagnostic claim')
            save(out/(cell['id']+'-bank.json'),bank)
        except Exception as exc:row['error']=f'{type(exc).__name__}: {exc}'
        row['seconds']=time.perf_counter()-start;rows.append(row);save(out/(cell['id']+'.json'),row)
    if digest(path)!=sha or path.with_suffix('.sha256').read_text().strip()!=sha:raise ValueError('Plan changed')
    for filename,expected in p['source_files'].items():
        if digest(filename)!=expected:raise ValueError('Bound source changed')
    groups={}
    for rho in [0.,.9]:
        for shift in [0.,.5]:groups[f'{rho}/{shift}']=summarize([r for r in rows if r['rho']==rho and r['backend_b_shift']==shift],sum(c['rho']==rho and c['backend_b_shift']==shift for c in p['cells']))
    save(out/'summary.json',dict(phase='exploratory',qualified=False,plan_sha256=sha,groups=groups))


def main():
    p=argparse.ArgumentParser();p.add_argument('--plan',type=Path);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    if a.plan:run(a.plan,a.out)
    else:save(a.out,make_plan())


if __name__=='__main__':main()
