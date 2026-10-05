"""One fixed validation origin, four SV ablations, two backends; no market fit."""
import hashlib, importlib.util, json, sys, zipfile
from pathlib import Path
import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SV = ROOT/'STUDIES/market_uncertainty_v1/sv_prototype'
HIST = ROOT/'STUDIES/market_uncertainty_v1/historical_evaluation'
sys.path[:0] = [str(SV), str(HIST)]
from historical_inputs import build, ARMS
from synthetic import ILLUSTRATIVE_PRIORS
from evaluate import verified_load


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    seed_audit = json.loads((HERE/'seed-audit-v2.json').read_text())
    if seed_audit['hits'] or seed_audit['seeds'] != list(range(991901,991913)):
        raise ValueError('Seed collisions require review before preparation')
    out = HERE/'prepared'; out.mkdir(exist_ok=False)
    protocol = dict(status='diagnostic_preparation', qualified=False,
                    origin_ms=1789430400000, origin_utc='2026-09-15T00:00:00Z',
                    ablations=list(ARMS), minimum_history=20, lookback=256,
                    rho=.9, nu=5., priors=vars(ILLUSTRATIVE_PRIORS),
                    chains=4, warmup=1000, tiers=[1000,2000,4000],
                    cpus=[0,1,2,3], timeout_seconds_per_fit=1800,
                    global_seconds=21600, disk_floor_bytes=12*1024**3,
                    streams=[dict(ablation=arm,starts=991901+i,sampler=991905+i,
                                  predictive=991909+i,order=['public','reference'] if i%2==0 else ['reference','public']) for i,arm in enumerate(ARMS)],
                    scope='Single fixed historical validation origin; illustrative priors unchanged; no calibration or speed qualification; every intended fit retained')
    (out/'protocol.json').write_text(json.dumps(protocol,indent=2))
    acquisition = ROOT/'target/market-history-acquisition-v1'
    dataset = verified_load(acquisition/'september-development-v1',
                            protocol_path=acquisition/'protocol-frozen-v1.json',
                            collector_source=acquisition/'collector.py')
    (out/'acquisition-bindings.json').write_text(json.dumps(dataset['bindings'],indent=2))
    cells=[]; admissions=[]
    for role in protocol['streams']:
        built=build(dataset['rows'],protocol['origin_ms'],ablation=role['ablation'],
                    minimum_history=20,lookback=256)
        admissions.append(dict(ablation=role['ablation'],status=built['status'],
                               reason=built.get('reason'),training_count=built.get('training_count')))
        if built['status']!='ready':
            continue
        data=built['data'];data['rho']=.9;data['nu']=5.
        data['y'][~data['observed']]=0.;data['x'][~data['observed']]=0.
        p,k,n=data['x'].shape[1],data['w'].shape[1],len(data['y']);pr=ILLUSTRATIVE_PRIORS
        mean=np.r_[pr.mu_mean,pr.log_sigma_mean,np.zeros(p+k+n)]
        sd=np.r_[pr.mu_sd,pr.log_sigma_sd,np.full(p,pr.beta_sd),np.full(k,pr.gamma_sd),np.ones(n)]
        starts=mean+.25*sd*np.random.default_rng(role['starts']).normal(size=(4,len(mean)))
        f=dict(data=data,priors=vars(pr),future=built['future'],starts=starts,
               predictive_seed=role['predictive'],admission=built,stream_roles=role)
        path=out/(role['ablation']+'.json')
        path.write_text(json.dumps(f,indent=2,allow_nan=False,default=lambda x:x.tolist()))
        for arm in role['order']:
            cells.append(dict(id=role['ablation']+'-'+arm,arm=arm,seed=role['sampler'],fixture=str(path.resolve())))
    (out/'admission.json').write_text(json.dumps(admissions,indent=2))
    if len(cells)!=8:
        raise RuntimeError('Incomplete intended preparation; retain admissions, do not run subset')
    previous=ROOT/'target/sv-fresh-dataset-comparison-v1/prepared/config-frozen.json'
    config=json.loads(previous.read_text())
    config.pop('draft_sha256', None)
    paths={Path(p) for p in config['bindings']}
    paths.update(SV.glob('*.py'));paths.update(HIST.glob('*.py'))
    paths.update(HERE.glob('*.py'));paths.update(out.glob('*.json'))
    paths.add(HERE/'seed-audit.json')
    paths.add(HERE/'seed-audit-v2.json')
    paths.update(Path(p) for p in dataset['bindings'])
    config.update(status='draft_not_authorized_to_run',cells=cells,protocol=protocol,
                  bindings={str(p.resolve()):sha(p) for p in paths})
    (out/'config.json').write_text(json.dumps(config,indent=2))
    with zipfile.ZipFile(out/'sources.zip','x',zipfile.ZIP_DEFLATED) as z:
        for i,p in enumerate(sorted(paths)):
            if p.suffix=='.py': z.write(p,f'{i}/{p.name}')
    print('Prepared all eight intended fits; draft SHA',sha(out/'config.json'))


if __name__=='__main__': main()
