"""Prospective 80-cell feasibility planner/executor; no qualification claims.

Planning alone imports numerical generators. Execution is sequential, immutable,
and requires a separately frozen plan and digest sidecar. Nothing runs on import.
"""
import argparse
import copy
import hashlib
import json
import math
from pathlib import Path
import subprocess
import time
from endpoint_replicates import extract_cohort,analyze,predictive_inputs

HERE=Path(__file__).resolve().parent
TIERS=[1000,2000,4000,8000]
PRIMARY={'flow':['beta_bar','tau','mu_h','sigma_h','h_terminal'],
         'local_level':['h_initial','h_terminal','h_mean','sigma_obs','sigma_rw']}
FLOW_ALL=PRIMARY['flow']+['h_mean']+[name for g in range(4) for name in (f'alpha_{g}',f'beta_{g}')]


def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def canonical_hash(value):return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
def save_new(path,value):
    with Path(path).open('x',encoding='utf-8') as handle:json.dump(value,handle,indent=2,allow_nan=False)
def sources():return {p.name:digest(p) for p in HERE.glob('*.py')}


def initial_positions(model,data,seed):
    if model=='flow':
        from breadth import flow_initial_positions
        return flow_initial_positions(data,seed)
    import numpy as np
    rng=np.random.default_rng(seed);t=len(data['y']);anchor=float(data['anchor'])
    # Independent of observed values and generated latent truth; explicit fixed rule.
    h=anchor+rng.normal(0,.08,(4,1))+np.cumsum(rng.normal(0,.015,(4,t)),axis=1)
    scales=rng.normal([math.log(.08),math.log(.12)],[.15,.15],size=(4,2))
    return np.concatenate([h,scales],axis=1).tolist()


def endpoints(model):
    result={}
    for name in PRIMARY[model]+['next_observed']:
        if model=='flow':scale={'h_terminal':'log_variance','mu_h':'log_variance','sigma_h':'log_variance_innovation'}.get(name,'model_units')
        else:scale='log_price_increment' if name.startswith('sigma_') else 'log_price'
        selector={'kind':'functional','name':name} if name!='next_observed' else {'kind':'forecast','horizon':1,'group':0 if model=='flow' else None}
        for probability in [.05,.95]:result[f'{name}:{probability}']=dict(scale=scale,probability=probability,selector=selector)
    return result


def zero_flow_covariates(fixture):
    """Generation-only intervention preserves each generated observation noise."""
    truth=fixture['truth'];g=len(fixture['holdout']['x'][0])
    beta=[truth[0]+math.exp(truth[1])*truth[4+g+j] for j in range(g)]
    fixture['holdout']['y']=[[y[j]-beta[j]*x[j] for j in range(g)] for x,y in zip(fixture['holdout']['x'],fixture['holdout']['y'])]
    fixture['holdout']['x']=[[0.]*g for _ in fixture['holdout']['x']]
    return fixture


def check_environment(plan):
    environment=plan['environment']
    for role in ('python','adapter','extension'):
        entry=environment[role]
        if plan['bound_files'].get(entry['path'])!=entry['sha256'] or digest(entry['path'])!=entry['sha256']:
            raise ValueError('Required environment binding differs: '+role)
    if str(Path(plan['python']).resolve())!=str(Path(environment['python']['path']).resolve()):raise ValueError('Python executable binding mismatch')


def create_plan(spec,out):
    """Explicit spec requires python, bound_files, seeds per model and prior-use inventory."""
    if spec.get('local_coordinates','observation_residual') not in ('observation_residual','conditional_whitening'):raise ValueError('Unsupported local coordinate recipe')
    all_seeds=[]
    for model in PRIMARY:
        entry=spec['seeds'][model]
        if len(entry['replicates'])!=20:raise ValueError('Exactly twenty replicates per model required')
        all_seeds.append(entry['dataset_seed'])
        for row in entry['replicates']:
            all_seeds.extend([row['initialization_seed'],row['sampler_seed'],row['sampler_seed']+130000])
    if any(isinstance(s,bool) or not isinstance(s,int) or not 0<=s<2**32 for s in all_seeds) or len(set(all_seeds))!=len(all_seeds):raise ValueError('Invalid or colliding streams')
    if set(all_seeds)&set(spec['previously_used_seeds']):raise ValueError('Streams collide with prior experiment inventory')
    check_environment(spec)
    out=Path(out).resolve();out.mkdir(parents=True,exist_ok=False)
    from model import simulate as flow_simulate
    from local_level import simulate as local_simulate
    plan=dict(schema='endpoint-feasibility/v1',frozen=False,phase='exploratory',qualified=False,
        python=spec['python'],environment=spec['environment'],local_coordinates=spec.get('local_coordinates','observation_residual'),source_sha256=sources(),bound_files=spec['bound_files'],cpus=spec.get('cpus',[0]),
        timeout_seconds=spec.get('timeout_seconds',1800),cells=[],analyses={},initialization_rule='flow breadth prior-scale; local anchor+.08 chain offset+.015 cumulative iid increments; logs N(log[.08,.12],.15)',
        outer_cost_scope='Hardware wrapper invocation including process startup, worker, output and controller validation; distinct from worker clock')
    for model in PRIMARY:
        entry=spec['seeds'][model]
        fixture=flow_simulate(entry['dataset_seed'],periods=128,groups=4,holdout=1,prior=False) if model=='flow' else local_simulate(entry['dataset_seed'],periods=128,holdout=1,prior=False,anchor=0.)
        if model=='flow':zero_flow_covariates(fixture)
        contract=dict(horizon=1,observed=True,group=0 if model=='flow' else None,x=[0.]*4 if model=='flow' else None,dt=1 if model=='local_level' else None)
        target_hash=canonical_hash(dict(data=fixture['data'],predictive_contract=contract,predictive_inputs=predictive_inputs(fixture)))
        for arm in ['candidate','reference']:
            plan['analyses'][model+'/'+arm]=dict(target_sha256=target_hash,arm=arm,policy='first-pass-1000-2000-4000-8000',replicate_ids=[],endpoints=endpoints(model),streams={},worker_bindings={},predictive_contract=contract,reference_bank={'resolved':False})
        for index,seeds in enumerate(entry['replicates']):
            rid=f'{model}-{index:02d}';streams=dict(seeds,prediction_seed=seeds['sampler_seed']+130000)
            current=copy.deepcopy(fixture);current['replicate_streams']=streams
            current['data']['initial_positions']=initial_positions(model,current['data'],seeds['initialization_seed'])
            fixture_path=out/(rid+'-fixture.json');save_new(fixture_path,current)
            for arm in (['candidate','reference'] if index%2==0 else ['reference','candidate']):
                cell=dict(id=rid+'-'+arm,replicate_id=rid,model=model,arm=arm,fixture=str(fixture_path),fixture_sha256=digest(fixture_path),streams=streams)
                plan['cells'].append(cell)
                analysis=plan['analyses'][model+'/'+arm];analysis['replicate_ids'].append(rid);analysis['streams'][rid]=streams
    save_new(out/'plan.json',plan)
    return plan


def verify(plan,path,original_digest=None):
    if plan.get('local_coordinates') not in ('observation_residual','conditional_whitening'):raise ValueError('Unsupported local coordinate recipe')
    if original_digest is not None and digest(path)!=original_digest:raise ValueError('Plan changed during invocation')
    check_environment(plan)
    if plan.get('frozen') is not True or path.with_suffix('.sha256').read_text().strip()!=digest(path):raise ValueError('Frozen plan/digest required')
    if sources()!=plan['source_sha256']:raise ValueError('Study source drift')
    for filename,sha in plan['bound_files'].items():
        if digest(filename)!=sha:raise ValueError('Bound dependency drift')
    if len(plan['cells'])!=80 or len({c['id'] for c in plan['cells']})!=80:raise ValueError('Expected eighty unique cells')


def command(plan,cell,out):
    shared=['--fixture',cell['fixture'],'--out',str(out),'--seed',str(cell['streams']['sampler_seed']),'--warmup','1000','--chains','4','--tiers',*map(str,TIERS)]
    if cell['arm']=='reference':
        args=[str(HERE/'continuation_precision.py'),*shared,'--model',cell['model'],'--target-accept','0.9']
        if cell['model']=='local_level':args+=['--coordinates',plan['local_coordinates']]
        filename='numpyro-continuation-report.json';raw='numpyro-continuation-raw.json'
    elif cell['model']=='flow':
        args=[str(HERE/'pymc_flow_workflow.py'),*shared,'--block-size','32','--precision-names',*FLOW_ALL]
        filename='python-pymc-flow-report.json';raw='python-pymc-flow-raw.json'
    else:
        args=[str(HERE/'pymc_workflow.py'),*shared,'--coordinates',plan['local_coordinates']]
        filename='python-pymc-report.json';raw='python-pymc-raw.json'
    return [plan['python'],str(HERE/'hardware_control.py'),'--cpus',','.join(map(str,plan['cpus'])),'--record',str(out.parent/(cell['id']+'-hardware.json')),'--timeout',str(plan['timeout_seconds']),'--',plan['python'],*args],filename,raw


def validate_terminal(plan,cell,worker,raw):
    draws=worker.get('settings',{}).get('draws')
    if draws not in TIERS:raise ValueError('Terminal draws outside frozen tiers')
    if worker.get('precision_pass') is not True and draws!=TIERS[-1]:raise ValueError('Nonpassing completed fit must exhaust final tier')
    attempts=worker.get('attempts',[])
    if not attempts or [a['draws'] for a in attempts]!=TIERS[:TIERS.index(draws)+1]:raise ValueError('Attempt sequence differs from frozen tier plan')
    if any(a['screen']['pass'] for a in attempts[:-1]) or attempts[-1]['screen']['pass']!=worker.get('precision_pass'):raise ValueError('Selected attempt inconsistent with first-pass policy')
    expected_names=set(FLOW_ALL if cell['model']=='flow' else PRIMARY['local_level'])
    for attempt in attempts:
        if set(attempt['screen']['parameter_functionals'])!=expected_names or attempt['screen']['forecast_rows']!=(4 if cell['model']=='flow' else 1):raise ValueError('Stopping family mismatch')
    fixture=json.loads(Path(cell['fixture']).read_text())
    expected=initial_positions(cell['model'],fixture['data'],cell['streams']['initialization_seed'])
    if expected!=fixture['data']['initial_positions'] or raw.get('initial_positions')!=expected:raise ValueError('Initialization regeneration/raw-start mismatch')
    settings=dict(warmup=1000,draws=draws,chains=4)
    if cell['arm']=='reference':settings['target_accept']=.9;arm='numpyro-continuation' if cell['model']=='flow' else 'numpyro-continuation-'+plan['local_coordinates'].replace('_','-')
    else:
        settings.update(threads=1,chain_execution='sequential')
        if cell['model']=='flow':settings['block_size']=32;arm='python-pymc-flow-noncentered'
        else:arm='python-pymc-cfunc-'+plan['local_coordinates'].replace('_','-')
    fields=dict(arm=arm,seed=cell['streams']['sampler_seed'],source_sha256=plan['source_sha256'],settings=settings)
    if cell['arm']=='candidate':
        fields.update(adapter_source_sha256=plan['environment']['adapter']['sha256'],extension_sha256=plan['environment']['extension']['sha256'],software=plan['environment']['candidate_software'])
    if any(worker.get(k)!=v for k,v in fields.items()):raise ValueError('Worker invariant identity/settings/environment mismatch')
    if worker.get('fixture_sha256')!=cell['fixture_sha256']:raise ValueError('Worker fixture mismatch')
    return dict(fixture_sha256=cell['fixture_sha256'],prediction_seed_rule='sampler_seed_plus_130000',endpoint_scales={k:v['scale'] for k,v in endpoints(cell['model']).items()},report_fields=fields)


def execute(plan_path):
    plan_path=Path(plan_path).resolve();plan=json.loads(plan_path.read_text());original_digest=digest(plan_path);verify(plan,plan_path,original_digest)
    for cell in plan['cells']:
        directory=plan_path.parent;marker=directory/(cell['id']+'-started.json');status=directory/(cell['id']+'-status.json');out=directory/cell['id']
        if marker.exists() or status.exists() or out.exists():continue
        save_new(marker,dict(cell=cell,plan_sha256=digest(plan_path)));start=time.perf_counter();record=dict(status='failed',cell=cell,plan_sha256=original_digest)
        try:
            verify(plan,plan_path,original_digest)
            if digest(cell['fixture'])!=cell['fixture_sha256']:raise ValueError('Fixture drift')
            args,filename,rawname=command(plan,cell,out)
            with (directory/(cell['id']+'.log')).open('x') as log:
                completed=subprocess.run(args,stdout=log,stderr=subprocess.STDOUT,cwd=HERE,timeout=plan['timeout_seconds']+30)
            worker=json.loads((out/filename).read_text());record.update(worker=worker,returncode=completed.returncode)
            verify(plan,plan_path,original_digest)
            if digest(cell['fixture'])!=cell['fixture_sha256']:raise ValueError('Fixture drift during worker')
            if worker.get('status')=='completed':
                rawpath=out/rawname if cell['arm']=='reference' else out/f"draws-{worker['settings']['draws']}"/rawname
                binding=validate_terminal(plan,cell,worker,json.loads(rawpath.read_text()))
                record.update(binding=binding,report_path=str(out/filename),report_sha256=digest(out/filename),raw_path=str(rawpath),raw_sha256=digest(rawpath),status='validated',initialization_regenerated_and_raw_verified=True)
        except Exception as exc:record['error']=f'{type(exc).__name__}: {exc}'
        record['outer_elapsed_seconds']=time.perf_counter()-start;save_new(status,record)


def summarize(plan_path,out):
    plan_path=Path(plan_path);plan=json.loads(plan_path.read_text());original_digest=digest(plan_path);verify(plan,plan_path,original_digest);results={}
    for key,manifest in plan['analyses'].items():
        manifest=copy.deepcopy(manifest);artifacts={};outer=[];missing=[];invalid=[]
        for cell in [c for c in plan['cells'] if c['model']+'/'+c['arm']==key]:
            path=plan_path.parent/(cell['id']+'-status.json')
            if not path.exists():missing.append(cell['id']);continue
            record=json.loads(path.read_text());outer.append(record['outer_elapsed_seconds'])
            if record.get('plan_sha256')!=original_digest or record.get('cell')!=cell:record['status']='invalid_binding'
            if record['status']=='validated':
                try:
                    if digest(record['report_path'])!=record['report_sha256'] or digest(record['raw_path'])!=record['raw_sha256'] or digest(cell['fixture'])!=cell['fixture_sha256']:raise ValueError('Saved evidence changed')
                    checked_worker=json.loads(Path(record['report_path']).read_text())
                    binding=validate_terminal(plan,cell,checked_worker,json.loads(Path(record['raw_path']).read_text()))
                    if checked_worker!=record['worker'] or binding!=record['binding']:raise ValueError('Status binding differs from validated artifact')
                    manifest['worker_bindings'][cell['replicate_id']]=binding
                    artifacts[cell['replicate_id']]=(checked_worker,Path(cell['fixture']).read_bytes())
                except (ValueError,KeyError,TypeError,OSError) as exc:
                    record['status']='invalid_artifact';record['analysis_error']=str(exc)
            if record['status']!='validated':
                invalid.append(dict(id=cell['replicate_id'],target_sha256=manifest['target_sha256'],arm=manifest['arm'],policy=manifest['policy'],streams=cell['streams'],status='failed',elapsed_seconds=record.get('worker',{}).get('end_to_end_seconds')))
        rows=extract_cohort(manifest,artifacts)+invalid
        results[key]=analyze(manifest,rows,None)
        results[key]['outer_costs']=dict(seconds=sum(outer),recorded=len(outer),expected=20,missing_ids=missing)
    save_new(out,dict(phase='exploratory',qualified=False,analyses=results))


def main():
    p=argparse.ArgumentParser(description=__doc__);sub=p.add_subparsers(dest='action',required=True)
    a=sub.add_parser('plan');a.add_argument('--spec',type=Path,required=True);a.add_argument('--out',type=Path,required=True)
    a=sub.add_parser('run');a.add_argument('--plan',type=Path,required=True)
    a=sub.add_parser('summarize');a.add_argument('--plan',type=Path,required=True);a.add_argument('--out',type=Path,required=True)
    args=p.parse_args()
    if args.action=='plan':create_plan(json.loads(args.spec.read_text()),args.out)
    elif args.action=='run':execute(args.plan)
    else:summarize(args.plan,args.out)


if __name__=='__main__':main()
