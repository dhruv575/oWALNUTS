"""Draft-only sparse-market computational comparison planner (stdlib only).

Authoring/importing this module does not generate fixtures or run workers.
Invoke prepare only after a coordinated quiet window and bounded seed review.
The output is deliberately NOT frozen and cannot launch an experiment.
"""
import argparse
import copy
import json
import math
from pathlib import Path
import random
import subprocess
from continuation_comparison import sha,load,save,attested_dependencies

HERE=Path(__file__).resolve().parent
INIT_SEED=102010001
CHAIN_SEEDS=[102110001,102110002]
PREDICTIVE_SEEDS=[s+130000 for s in CHAIN_SEEDS]
NAMES=['beta_bar','tau','mu_h','sigma_h','h_terminal','h_mean']+[name+str(g) for g in range(4) for name in ['alpha_','beta_']]


def seed_family(init_seed=INIT_SEED,chain_seeds=None):
    chains=list(CHAIN_SEEDS if chain_seeds is None else chain_seeds)
    if type(init_seed) is not int or not 0<=init_seed<2**32:raise ValueError('Initialization seed must be a uint32 integer')
    if len(chains)!=2 or any(type(seed) is not int or not 0<=seed<2**32-130000 for seed in chains):raise ValueError('Exactly two valid chain seeds with uint32 predictive offsets required')
    predictive=[seed+130000 for seed in chains];inventory=[init_seed,*chains,*predictive]
    if len(set(inventory))!=len(inventory):raise ValueError('Initialization, chain and derived predictive seeds must all be distinct')
    return chains,predictive,inventory


def dispersed_starts(periods,groups,rho,seed):
    """Prior-scale dispersion uses only shape/fixed rho, never data values."""
    if periods<1 or groups<1 or not math.isfinite(rho) or abs(rho)>=1:raise ValueError('Invalid model structure')
    rng=random.Random(seed);starts=[]
    for chain in range(4):
        globals_=[mean+.25*sd*rng.gauss(0.,1.) for mean,sd in zip([0.,-1.,-1.,-1.5],[.5,.5,1.,.5])]
        groups_=[.25*rng.gauss(0.,1.) for _ in range(2*groups)]
        mu=globals_[2];sigma=math.exp(globals_[3]);path=[mu+sigma*.25*rng.gauss(0.,1.)/math.sqrt(1-rho*rho)]
        for _ in range(1,periods):path.append(mu+rho*(path[-1]-mu)+sigma*.25*rng.gauss(0.,1.))
        starts.append(globals_+groups_+path)
    return starts


def contract(fixture):
    """Explicit shape/mask contract for this one prospective real-data fixture."""
    data=fixture['data'];future=fixture['holdout'];g=4;t=96;h=48
    def matrix(values,rows):
        return isinstance(values,list) and len(values)==rows and all(isinstance(row,list) and len(row)==g for row in values)
    for key in ['y','x','observation_mask']:
        if not matrix(data[key],t):raise ValueError('Expected96-by4trainingpanel')
    if data['grid_index']!=list(range(t)):raise ValueError('Training latent grid must retain every step')
    for row in data['observation_mask']:
        if any(type(v) is not bool for v in row):raise ValueError('Explicit boolean training mask required')
    def finite(value):return not isinstance(value,bool) and isinstance(value,(int,float)) and math.isfinite(value)
    for i,row in enumerate(data['observation_mask']):
        for j,observed in enumerate(row):
            if observed and not all(finite(data[key][i][j]) for key in ['y','x']):raise ValueError('Nonfinite observed training value')
    if sum(map(sum,data['observation_mask']))!=18:raise ValueError('Expected18observedtrainingcells')
    ym=future.get('y_available',future.get('observation_mask'));xm=future['x_available']
    if 'y_available' in future and 'observation_mask' in future and future['y_available']!=future['observation_mask']:raise ValueError('Conflicting outcome masks')
    for values in [future['y'],future['x'],ym,xm]:
        if not matrix(values,h):raise ValueError('Expected48-by4futurepanel')
    if future['grid_index'] not in [list(range(h)),list(range(t,t+h))]:raise ValueError('Future latent grid must retain every step')
    cells=[]
    for i in range(h):
        for j in range(g):
            if type(xm[i][j]) is not bool or type(ym[i][j]) is not bool:raise ValueError('Explicit boolean future masks required')
            if xm[i][j]:
                if not finite(future['x'][i][j]):raise ValueError('Nonfinite available future covariate')
                cells.append([i+1,j])
            if ym[i][j] and not finite(future['y'][i][j]):raise ValueError('Nonfinite observed future outcome')
    if len(cells)!=192 or sum(map(sum,ym))!=4:raise ValueError('Expected192availableforecastsand4observedlabels')
    if not finite(data['rho']) or abs(data['rho'])>=1 or not finite(data['nu']) or data['nu']<=2:raise ValueError('Invalid fixed rho/nu')
    return dict(periods=t,groups=g,dimension=t+12,training_observed=18,forecast_scheduled=192,
                forecast_cells=cells,forecast_observed=4,precision_names=NAMES)


def command(plan,cell,out):
    common=['--fixture',cell['fixture'],'--out',str(out),'--seed',str(cell['seed']),
            '--warmup','1000','--chains','4','--tiers','1000','2000','4000','8000']
    if cell['arm']=='owalnuts_continuation':
        worker='pymc_flow_continuation_workflow.py';common+=['--model','masked-flow','--block-size','32','--expected-cpus','0']
    elif cell['arm']=='numpyro_continuation':
        worker='masked_flow_reference.py';common+=['--batch','1000','--target-accept','0.9']
    else:raise ValueError('Unknown arm')
    return [plan['python'],str(HERE/'hardware_control.py'),'--cpus','0','--record',str(Path(out).parent/(cell['id']+'-hardware.json')),
        '--timeout',str(plan['timeout_seconds']),'--',plan['python'],str(HERE/worker),*common]


def matched_fixture(original,init_seed=INIT_SEED):
    fixture=copy.deepcopy(original)
    for i,row in enumerate(fixture['data']['observation_mask']):
        for j,observed in enumerate(row):
            if not observed:
                for key in ['y','x']:fixture['data'][key][i][j]=0.
    fixture['data']['initial_positions']=dispersed_starts(96,4,fixture['data']['rho'],init_seed)
    fixture['training_placeholder_contract']='Unobserved training x/y normalized to finite zero for strict start-shape helpers; explicit mask preserved; gathered likelihood unchanged. Future missing outcomes remain missing.'
    fixture['initialization_contract']=dict(seed=init_seed,algorithm='Python random.Random.gauss; interpreter bound',
        formula='Globals mean[0,-1,-1,-1.5]+0.25*priorSD[.5,.5,1,.5]*N; group z=0.25N; stationaryAR path conditional on each chain mu/sigma with innovations0.25N',
        input_scope='Shape and fixed rho only; no observed values, outcomes, truth or fitted diagnostics',
        distribution_note='Dispersed initial positions at0.25priorSD; not full prior draws')
    return fixture


def prepare(out,fixture_path,python,package,attestation,seed_audit,*,init_seed=INIT_SEED,chain_seeds=None):
    """Generate a fresh matched-start fixture and draft plan; never freeze/run."""
    chains,predictive,seeds=seed_family(init_seed,chain_seeds)
    out=Path(out).resolve();fixture_path=Path(fixture_path).resolve();package=Path(package).resolve()
    original=load(fixture_path);schema=contract(original)
    audit=load(seed_audit)
    if audit.get('status')!='passed' or sorted(audit.get('seeds',[]))!=sorted(seeds) or audit.get('hits')!=[] or not audit.get('scope'):
        raise ValueError('Requires preaudited exact seed family and declared bounded search scope')
    dependencies=attested_dependencies(attestation,python,package)
    runtime=json.loads(subprocess.check_output([str(python),'-c',
        "import sys,json,importlib.metadata as m; print(json.dumps(dict(python=sys.version,packages={p:m.version(p) for p in ['numpy','scipy','pymc','pytensor','numba','jax','jaxlib','numpyro','arviz']})))"],text=True))
    bound={str(Path(p).resolve()):sha(p) for p in [fixture_path,python,package/'owalnuts/__init__.py',package/'owalnuts/_owalnuts.pyd',attestation,seed_audit]}
    bound.update(dependencies)
    fixture=matched_fixture(original,init_seed)
    out.mkdir(parents=True,exist_ok=False);matched=out/'fixture-matched-starts.json';save(matched,fixture)
    plan=dict(frozen=False,status='draft_requires_review',phase='development_computational_only',qualified=False,
        original_fixture=str(fixture_path),original_fixture_sha256=sha(fixture_path),fixture=str(matched),fixture_sha256=sha(matched),
        python=str(Path(python).resolve()),pythonpath=str(package),runtime=runtime,attestation=str(Path(attestation).resolve()),bound_files=bound,
        study_bindings={str(p.resolve()):sha(p) for p in HERE.glob('*.py')},seed_audit=audit,
        initialization=fixture['initialization_contract'],starts=fixture['data']['initial_positions'],
        expected=4,timeout_seconds=900,maximum_worker_seconds=3600,chains=4,warmup=1000,tiers=[1000,2000,4000,8000],
        relative_mcse=.02,reference_target_accept=.9,candidate_target_accept='Unchanged public default0.8; attested adapter/core',
        schema=schema,cells=[],runtime_policy='Fresh processes; existing disk caches retained; CPU0 contained worker descendants; no overlapping timed work',
        parity_policy='Candidate repeats independent normalized JAX+centered parity, included in costs; reference independent JAX density implementation',
        cost_policy='Imports, compilation, parity, adaptation, retained draws, diagnostics, prediction, output and wrapper included; every timeout/failure retained',
        failure_policy='Immutable intent/start/exit/terminal records; no automatic retry of a started cell; source drift abort terminalizes all remaining cells',
        interpretation='Single sparse posterior, two paired sampler seeds. No reliability breadth, calibration, positive-alpha, coverage or trading-usefulness claim. Ratios only for matched successful cells.',
        forecast_scope='Fixed-origin conditional scenario supplied future covariates; every available-x cell precision-gated regardless of label. Four labels score only; no positive-alpha requirement.')
    for rep,(seed,predictive_seed) in enumerate(zip(chains,predictive)):
        order=['owalnuts_continuation','numpyro_continuation'] if rep==0 else ['numpyro_continuation','owalnuts_continuation']
        for arm in order:
            cell=dict(id=f'rep{rep}-{arm}',arm=arm,seed=seed,predictive_seed=predictive_seed,fixture=str(matched),fixture_sha256=sha(matched),starts=plan['starts'])
            cell['command']=command(plan,cell,out/cell['id']);plan['cells'].append(cell)
    save(out/'plan-draft.json',plan)
    return plan


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ['out','fixture','python','package','attestation','seed-audit']:p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--init-seed',type=int,default=INIT_SEED);p.add_argument('--chain-seeds',type=int,nargs=2,default=CHAIN_SEEDS)
    args=p.parse_args();prepare(args.out,args.fixture,args.python,args.package,args.attestation,args.seed_audit,init_seed=args.init_seed,chain_seeds=args.chain_seeds)
