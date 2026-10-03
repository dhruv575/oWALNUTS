"""Plan, execute and summarize an exploratory prior-predictive breadth screen.

Planning launches nothing. Spec JSON has seeds={flow:[{dataset_seed,chain_seed,init_seed},
...24],local_level:[{dataset_seed,chain_seed},...24]}, executables={flow:path,local_level:path}, optional
reference_indices={flow:[...six zero-based indices],local_level:[...six]},
cpus=[0], timeout_per_tier=1800. References are fixed before any execution.

Commands: breadth.py plan SPEC OUTPUT; breadth.py run OUTPUT [--cell ID ...];
breadth.py summarize OUTPUT. All stages remain exploratory. Fixed-regime stress
fixtures belong in a different study manifest and cannot enter this denominator.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import time

HERE=Path(__file__).resolve().parent
RECIPES={'flow':'autodiff-noncentered','local_level':'autodiff'}
REFERENCE={'flow':'numpyro-noncentered','local_level':'numpyro'}
NAMES={'flow':['beta_bar','tau','mu_h','sigma_h','h_terminal'],
       'local_level':['h_initial','h_terminal','h_mean','sigma_obs','sigma_rw']}
TIERS=[1000,2000,4000,8000]
FLOW_START_FORMULA=('Four independent canonical starts; global means [0,-1,-1,-1.5] '
    'plus independent Normal(0,0.25*prior_sd), prior_sd=[.5,.5,1,.5]; '
    'z_alpha,z_beta independent Normal(0,.25); h=-1+stationary AR1 perturbation '
    'with data rho and innovation_sd=.25*exp(-1.5), independent of start globals. '
    'Uses shape and fixed rho only; never observed values, generated truth or held-out data.')


def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_new(path,value):
    with Path(path).open('x',encoding='utf-8') as handle:
        json.dump(value,handle,indent=2,allow_nan=False)


def source_snapshot():
    from build import source_snapshot as rust_sources
    return {'python':{p.name:digest(p) for p in sorted(HERE.glob('*.py'))},
            'rust':rust_sources(HERE),
            'requirements_sha256':digest(HERE/'requirements.txt')}


def flow_initial_positions(data,init_seed):
    """Fixed four-chain prior-scale dispersion, independent of target observations."""
    import numpy as np
    shape=np.shape(data['y'])
    if len(shape)!=2 or min(shape)<1:raise ValueError('Nonempty rectangular T by G shape required')
    periods,groups=shape;rho=float(data['rho'])
    if not math.isfinite(rho) or abs(rho)>=1:raise ValueError('Finite abs(rho)<1 required')
    if not isinstance(init_seed,int) or isinstance(init_seed,bool) or init_seed<0:
        raise ValueError('Explicit nonnegative integer initialization seed required')
    rng=np.random.default_rng(init_seed);global_dim=4+2*groups
    starts=np.empty((4,global_dim+periods))
    starts[:,:4]=rng.normal([0.,-1.,-1.,-1.5],.25*np.array([.5,.5,1.,.5]),size=(4,4))
    starts[:,4:global_dim]=rng.normal(0.,.25,size=(4,2*groups))
    innovation=.25*math.exp(-1.5)
    starts[:,global_dim]=-1.+rng.normal(0.,innovation/math.sqrt(1-rho*rho),size=4)
    for t in range(1,periods):
        starts[:,global_dim+t]=-1.+rho*(starts[:,global_dim+t-1]+1.)+rng.normal(0.,innovation,size=4)
    return starts.tolist()


def _validate_spec(spec):
    if set(spec.get('seeds',{}))!=set(RECIPES):raise ValueError('Explicit seed lists for both models required')
    all_seeds=[];predictive_seeds=[]
    for model in RECIPES:
        entries=spec['seeds'][model]
        if len(entries)!=24:raise ValueError('Exactly 24 prior datasets per model required')
        for entry in entries:
            keys=('dataset_seed','chain_seed','init_seed') if model=='flow' else ('dataset_seed','chain_seed')
            if model=='local_level' and 'init_seed' in entry:
                raise ValueError('Local-level uses deterministic dispersed application starts, not an unused init_seed')
            for key in keys:
                value=entry.get(key)
                if not isinstance(value,int) or isinstance(value,bool) or not 0<=value<2**32-130000:
                    raise ValueError('Explicit nonnegative 32-bit-safe dataset/chain/initialization seeds required')
                all_seeds.append(value)
            predictive_seeds.append(entry['chain_seed']+130000)
        indices=spec.get('reference_indices',{}).get(model,[])
        if indices and (len(indices)!=6 or len(set(indices))!=6 or any(not isinstance(i,int) or isinstance(i,bool) or i<0 or i>=24 for i in indices)):
            raise ValueError('Reference checks must be six distinct prespecified indices per selected model')
    if len(all_seeds)!=len(set(all_seeds)):
        raise ValueError('All dataset, chain and initialization seeds must be mutually distinct across models')
    if set(predictive_seeds)&set(all_seeds):
        raise ValueError('Derived predictive seeds collide with declared dataset/chain/initialization seeds')
    cpus=spec.get('cpus',[0])
    if not cpus or any(not isinstance(i,int) or isinstance(i,bool) or i<0 for i in cpus) or len(cpus)!=len(set(cpus)):
        raise ValueError('Explicit unique nonnegative CPU IDs required')
    timeout=spec.get('timeout_per_tier',1800.)
    if not isinstance(timeout,(int,float)) or not math.isfinite(timeout) or timeout<=0:
        raise ValueError('Positive finite timeout required')


def plan(spec,out):
    """Create every frozen fixture, then immutable intended manifest; no fits."""
    _validate_spec(spec)
    from model import simulate as flow_simulate
    from local_level import simulate as local_simulate
    executables={model:Path(spec['executables'][model]).resolve() for model in RECIPES}
    if any(not path.is_file() for path in executables.values()):raise ValueError('Existing binary paths required for hash binding')
    out=Path(out);out.mkdir(parents=True,exist_ok=False)
    (out/'fixtures').mkdir();(out/'status').mkdir()
    snapshot=source_snapshot();cells=[]
    for model in RECIPES:
        refs=set(spec.get('reference_indices',{}).get(model,[]))
        for index,seeds in enumerate(spec['seeds'][model]):
            dataset_seed=seeds['dataset_seed'];chain_seed=seeds['chain_seed']
            fixture=(flow_simulate(dataset_seed,128,4,1,True) if model=='flow'
                     else local_simulate(dataset_seed,128,1,True,0.))
            fixture['breadth_seed_contract']={'dataset_seed':dataset_seed,'chain_seed':chain_seed,
               'predictive_seed':chain_seed+130000,'purpose':'exploratory prior-predictive breadth'}
            if model=='flow':
                fixture['data']['initial_positions']=flow_initial_positions(fixture['data'],seeds['init_seed'])
                fixture['breadth_seed_contract']['init_seed']=seeds['init_seed']
                fixture['initialization']={'coordinates':'canonical centered','formula':FLOW_START_FORMULA,
                                           'chains':4,'init_seed':seeds['init_seed']}
            else:
                fixture['initialization']={'coordinates':'canonical centered',
                  'formula':'Existing application data-based deterministic four-chain offsets; no stochastic initialization seed.',
                  'chains':4,'uses_observed_values':True,'uses_truth':False}
            path=out/'fixtures'/f'{model}-{index:02d}.json';write_new(path,fixture)
            arms=[RECIPES[model]]+([REFERENCE[model]] if index in refs else [])
            if index%2:arms.reverse()
            for arm in arms:
                cells.append({'id':f'{model}-{index:02d}-{arm}','model':model,'index':index,
                  'arm':arm,'dataset_seed':dataset_seed,'chain_seed':chain_seed,
                  'init_seed':seeds.get('init_seed'),
                  'fixture':str(path.relative_to(out)),'fixture_sha256':digest(path),
                  'executable':str(executables[model]),'executable_sha256':digest(executables[model]),
                  'reference':arm.startswith('numpyro'),'prior_predictive':True,
                  'precision_names':NAMES[model]})
    manifest={'schema':'options-flow-breadth/v1','phase':'exploratory','qualified':False,
       'status':'PLANNED','source_snapshot':snapshot,'cells':cells,
       'settings':{'periods':128,'groups':4,'holdout':1,'warmup':1000,'chains':4,
         'tiers':TIERS,'relative_mcse':.02,'timeout_per_tier':spec.get('timeout_per_tier',1800.),
         'cpus':spec.get('cpus',[0]),'require_attestation':True},
       'recipes':RECIPES,'model_dimensions':{'flow':{'periods':128,'groups':4},'local_level':{'periods':128}},
       'reference_indices':spec.get('reference_indices',{}),
       'reference_script':str(HERE/'optimized_reference.py'),
       'seed_policy':'Explicit disjoint generator/chain/flow-initialization seeds and derived predictive stream; user must check historical reuse before executing.',
       'flow_initialization_formula':FLOW_START_FORMULA,
       'coverage_scope':'Five physical parameter truths plus next observation; flow conditional on generated exogenous next covariate, not fixed x=0.',
       'interpretation':'24 iid prior fixtures per model are a feasibility/failure-mode screen, not calibration equivalence or reliability qualification.',
       'stress_policy':'No fixed-parameter stress fixtures accepted into this manifest.'}
    write_new(out/'manifest.json',manifest)
    write_new(out/'manifest-sha256.json',{'sha256':digest(out/'manifest.json')})
    return manifest


def load_manifest(out,check_sources=False):
    out=Path(out);manifest=json.loads((out/'manifest.json').read_text())
    if digest(out/'manifest.json')!=json.loads((out/'manifest-sha256.json').read_text())['sha256']:
        raise ValueError('Immutable manifest changed')
    if manifest.get('schema')!='options-flow-breadth/v1' or manifest.get('phase')!='exploratory':
        raise ValueError('Unsupported breadth manifest')
    if check_sources and manifest['source_snapshot']!=source_snapshot():
        raise ValueError('Sources changed since breadth plan; create a new plan, do not overwrite')
    return manifest


def run(out,cell_ids=None,runner=None):
    """Explicit execution only; a started/missing-terminal cell is never rerun."""
    out=Path(out);manifest=load_manifest(out,True)
    if runner is None:
        from precision_tiers import run_tiers as runner
    selected=set(cell_ids) if cell_ids else {c['id'] for c in manifest['cells']}
    if selected-{c['id'] for c in manifest['cells']}:raise ValueError('Unknown expected cell ID')
    settings=manifest['settings'];done=[]
    for cell in manifest['cells']:
        if cell['id'] not in selected:continue
        status=out/'status'/f"{cell['id']}.json";started=out/'status'/f"{cell['id']}.started.json"
        if status.exists() or started.exists():raise FileExistsError('Cell already attempted; preserve results and inspect incomplete work')
        write_new(started,{'id':cell['id'],'phase':'exploratory','status':'started'})
        start=time.perf_counter();record={'id':cell['id'],'phase':'exploratory','qualified':False,'status':'failed'}
        try:
            load_manifest(out,True)
            fixture=out/cell['fixture']
            if digest(fixture)!=cell['fixture_sha256'] or digest(cell['executable'])!=cell['executable_sha256']:
                raise ValueError('Fixture or executable changed since plan')
            options={'model':cell['model'],'relative_mcse':.02,'names':cell['precision_names'],
                     'require_attestation':True,'cpus':settings['cpus']}
            if cell['reference'] and cell['model']=='flow':options['reference_script']=Path(manifest['reference_script'])
            result=runner(fixture,out/'cells'/cell['id'],cell['arm'],Path(cell['executable']),
              cell['chain_seed'],settings['warmup'],settings['tiers'],settings['chains'],
              settings['timeout_per_tier'],**options)
            record.update(status='completed',precision_pass=result.get('precision_pass',False),
                          result=f"cells/{cell['id']}/precision-result.json")
        except Exception as exc:
            record['error']=f'{type(exc).__name__}: {exc}'
        record['cell_driver_seconds']=time.perf_counter()-start
        write_new(status,record);done.append(record)
    return done


def _coverage(report,model):
    evaluation=report.get('evaluation',{});result={};gaps=[]
    for name in NAMES[model]:
        row=evaluation.get('functionals',{}).get(name,{})
        bounds=row.get('interval_90',[]);truth=row.get('truth')
        valid=len(bounds)==2 and isinstance(truth,(int,float)) and math.isfinite(truth) and all(isinstance(v,(int,float)) and math.isfinite(v) for v in bounds) and bounds[0]<bounds[1]
        if not valid:gaps.append(name)
        result[name]=bool(valid and bounds[0]<=truth<=bounds[1])
    rows=[r for r in evaluation.get('forecast',{}).get('rows',[]) if r.get('horizon')==1 and r.get('group')==(0 if model=='flow' else None)]
    label='next_observed_y' if model=='flow' else 'next_observed_log_price'
    if len(rows)!=1:gaps.append(label);result[label]=False
    else:
        row=rows[0];vals=[row.get('lower'),row.get('upper'),row.get('observed')]
        valid=all(isinstance(v,(int,float)) and math.isfinite(v) for v in vals) and vals[0]<vals[1]
        if not valid:gaps.append(label)
        result[label]=bool(valid and vals[0]<=vals[2]<=vals[1])
    return result,gaps


def summarize(out):
    """Read every intended cell; report missing/failure costs and descriptive coverage."""
    out=Path(out);manifest=load_manifest(out);groups={};rows=[]
    for cell in manifest['cells']:
        key=cell['model']+'/'+cell['arm']
        primary_names=NAMES[cell['model']]+(['next_observed_y'] if cell['model']=='flow' else ['next_observed_log_price'])
        group=groups.setdefault(key,{'expected':0,'precision_pass':0,'categories':{},'recorded_driver_seconds':0.,
           'charged_fit_and_report_seconds':0.,'cost_missing_cells':0,'coverage_usable_and_covering':{n:0 for n in primary_names},'truth_field_gaps':[]})
        group['expected']+=1;category='missing_not_started';coverage={};gaps=[]
        status_path=out/'status'/f"{cell['id']}.json";result_path=out/'cells'/cell['id']/'precision-result.json'
        if (out/'status'/f"{cell['id']}.started.json").exists():category='started_without_terminal_status'
        if status_path.exists():
            status=json.loads(status_path.read_text())
            elapsed=status.get('cell_driver_seconds')
            if isinstance(elapsed,(int,float)) and math.isfinite(elapsed) and elapsed>=0:group['recorded_driver_seconds']+=elapsed
            else:group['cost_missing_cells']+=1
            category='executor_failed' if status.get('status')!='completed' else 'missing_precision_result'
            if result_path.exists():
                result=json.loads(result_path.read_text());attempts=result.get('attempts',[])
                attempt_problems=[]
                if [a.get('draws') for a in attempts]!=manifest['settings']['tiers'][:len(attempts)]:
                    attempt_problems.append('nonprefix attempted tiers')
                for attempt in attempts:
                    attempt_path=Path(attempt.get('report',''))
                    if not attempt_path.is_file():attempt_problems.append('missing attempted report');continue
                    attempt_report=json.loads(attempt_path.read_text())
                    if any(attempt_report.get(k)!=v for k,v in {'arm':cell['arm'],'seed':cell['chain_seed'],'fixture_sha256':cell['fixture_sha256']}.items()):
                        attempt_problems.append('report identity mismatch')
                    if any(attempt_report.get('source_sha256',{}).get(k)!=v for k,v in manifest['source_snapshot']['python'].items()):
                        attempt_problems.append('report source mismatch')
                    expected_settings={'warmup':1000,'draws':attempt['draws'],'chains':4,'cpus':manifest['settings']['cpus'],'chain_execution':'sequential'}
                    if attempt_report.get('settings')!=expected_settings:attempt_problems.append('report settings mismatch')
                cost=result.get('cumulative_fit_and_report_seconds')
                costs=[a.get('call_seconds_including_reporting') for a in attempts]
                if not all(isinstance(v,(int,float)) and math.isfinite(v) and v>0 for v in costs):
                    attempt_problems.append('missing attempt costs')
                elif not isinstance(cost,(int,float)) or not math.isclose(sum(costs),cost,rel_tol=1e-10,abs_tol=1e-6):
                    attempt_problems.append('inconsistent cumulative attempt costs')
                if isinstance(cost,(int,float)) and math.isfinite(cost) and cost>=0:group['charged_fit_and_report_seconds']+=cost
                else:group['cost_missing_cells']+=1
                if attempts:
                    final=Path(attempts[-1]['report'])
                    if final.exists():
                        report=json.loads(final.read_text())
                        if report.get('status')!='completed':category='worker_failed'
                        elif not report.get('healthy'):category='convergence_failed'
                        else:
                            from precision_tiers import precision_screen
                            screen=precision_screen(report,.02,cell['precision_names'])
                            category='precision_pass' if result.get('precision_pass') and screen['pass'] else 'precision_exhausted'
                        coverage,gaps=_coverage(report,cell['model'])
                        if category=='precision_pass' and gaps:category='missing_truth_fields'
                    else:category='missing_final_report'
                else:category='missing_attempts'
                if attempt_problems:category='incomplete_or_mismatched_attempt_evidence'
                if status.get('status')!='completed':category='executor_failed'
        else:group['cost_missing_cells']+=1
        if category=='precision_pass':
            group['precision_pass']+=1
            for name,covered in coverage.items():
                group['coverage_usable_and_covering'][name]=group['coverage_usable_and_covering'].get(name,0)+int(covered)
        group['truth_field_gaps'].extend({'cell':cell['id'],'functional':name} for name in gaps)
        group['categories'][category]=group['categories'].get(category,0)+1
        rows.append({'id':cell['id'],'category':category,'truth_field_gaps':gaps})
    for group in groups.values():
        group['coverage_descriptive_unconditional']={k:v/group['expected'] for k,v in group['coverage_usable_and_covering'].items()}
        group['coverage_descriptive_conditional_on_precision_success']={k:v/group['precision_pass'] for k,v in group['coverage_usable_and_covering'].items()} if group['precision_pass'] else {}
    return {'phase':'exploratory','qualified':False,'expected_cells':len(manifest['cells']),
       'groups':groups,'cells':rows,'interpretation':'Missing/failed cells retained. Reported costs are lower bounds when cells lack terminal costs. Coverage is descriptive, not equivalence or SBC rank qualification; 24 successes cannot establish99% reliability.'}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);commands=parser.add_subparsers(dest='command',required=True)
    p=commands.add_parser('plan');p.add_argument('spec',type=Path);p.add_argument('out',type=Path)
    p=commands.add_parser('run');p.add_argument('out',type=Path);p.add_argument('--cell',action='append')
    p=commands.add_parser('summarize');p.add_argument('out',type=Path)
    args=parser.parse_args()
    value=plan(json.loads(args.spec.read_text()),args.out) if args.command=='plan' else run(args.out,args.cell) if args.command=='run' else summarize(args.out)
    print(json.dumps(value,indent=2,allow_nan=False))
