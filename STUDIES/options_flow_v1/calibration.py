"""Cross-replication SBC report. Never promotes exploratory runs to qualification."""
import argparse,json
from pathlib import Path
import numpy as np
from scipy.stats import binomtest,kstest
from model import functionals,load_fixture


def aggregate(directory,arm,rank_draws=50):
    rows=[];failures=[];ranks={};coverage={};attempted=0;complete=0
    manifest_path=Path(directory)/'manifest.json'
    manifest=json.loads(manifest_path.read_text()) if manifest_path.exists() else None
    intended=[c for c in manifest['intended_cells'] if c['arm']==arm] if manifest else None
    missing=[c['report'] for c in intended if not (Path(directory)/c['report']).exists()] if intended is not None else []
    for path in sorted(Path(directory).glob(f'*/{arm}-report.json')):
        attempted+=1
        report=json.loads(path.read_text()); fixture=load_fixture(path.parent/'fixture.json')
        if not fixture.get('prior_predictive'):
            failures.append({'path':str(path),'reason':'not a prior-generative SBC fixture'});continue
        if report['status']!='completed' or not report.get('healthy'):
            failures.append({'path':str(path),'reason':'computational screen failed'});continue
        raw=json.loads((path.parent/f'{arm}-raw.json').read_text())
        q=np.asarray([c['draws'] for c in raw['chains']]); values=functionals(q,len(fixture['data']['x'][0]))
        truth=functionals(np.asarray(fixture['truth']),len(fixture['data']['x'][0]))
        all_functionals=True
        for name,v in values.items():
            diag=report['evaluation']['functionals'][name]
            # Conservative spacing heuristic, not an independence proof. Rank test remains exploratory.
            stride=max(1,int(np.ceil(v.size/min(diag['bulk_ess'],diag['tail_ess']))))
            spaced=v[:,::stride].reshape(-1)
            if len(spaced)<rank_draws:
                all_functionals=False
                failures.append({'path':str(path),'functional':name,'reason':'insufficient effective rank draws'});continue
            rng=np.random.default_rng(int(fixture['seed'])+91919)
            subsample=rng.choice(spaced,rank_draws,replace=False)
            randomized=(np.sum(subsample<truth[name])+rng.uniform())/(rank_draws+1)
            ranks.setdefault(name,[]).append(float(randomized))
            coverage.setdefault(name,[]).append(diag['covers_truth_90'])
        rows.append(str(path))
        complete+=int(all_functionals)
    denominator=len(intended) if intended is not None else attempted
    stats={}
    for name,r in ranks.items():
        hits=sum(coverage[name]); n=len(r);ci=binomtest(hits,n,.9).proportion_ci(.95)
        stats[name]={'replications':n,'randomized_rank_uniformity_ks_p':float(kstest(r,'uniform').pvalue),
                     'coverage_90_conditional_on_computational_success':hits/n,'unconditional_usable_and_covering_rate_lower_bound':hits/denominator,'coverage_95_ci':[ci.low,ci.high],'ranks':r}
    return {'arm':arm,'intended_replications':denominator,'frozen_intention_manifest_present':manifest is not None,'missing_reports':missing,'total_observed_reports':attempted,'computationally_healthy_replications':len(rows),'all_functional_rank_replications':complete,'failed_replications':failures,'functionals':stats,
            'qualified':False,'limitation':'Exploratory ranks use ESS-based spacing, not proven independent posterior draws; multiplicity and prespecified replication power required. Failed fits are not removed from denominator when judging workflow reliability.'}
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('directory',type=Path);p.add_argument('--arm',default='numpyro');p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    a.out.write_text(json.dumps(aggregate(a.directory,a.arm),indent=2,allow_nan=False))
