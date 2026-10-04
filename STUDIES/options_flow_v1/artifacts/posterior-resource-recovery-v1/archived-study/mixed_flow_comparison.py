"""Prospective eight-cell mixed-slope development comparison; no implicit launch."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import time
from continuation_comparison import sha,load,save,norm,attested_dependencies,validate_raw_starts
from flow_continuation_comparison import fixture_contract,fit_gate,validate_worker,NAMES
from masked_market_comparison_execute import tail_field

HERE=Path(__file__).resolve().parent
TIERS=[1000,2000,4000,8000]
SEEDS=[103110001,103110002]
PREDICTIVE=[seed+130000 for seed in SEEDS]
ARMS=['ow_nc','ow_mixed','numpyro_nc','numpyro_mixed']


def runtime(python):
    return json.loads(subprocess.check_output([str(python),'-c',
        "import sys,json,importlib.metadata as m;print(json.dumps(dict(python=sys.version,packages={p:m.version(p) for p in ['numpy','scipy','pymc','pytensor','numba','jax','jaxlib','numpyro','arviz']})))"],text=True))


def sources():return {str(p.resolve()):sha(p) for p in HERE.glob('*.py')}


def command(plan,cell,out):
    common=['--fixture',cell['fixture'],'--out',str(out),'--seed',str(cell['seed']),'--warmup','1000','--chains','4','--tiers',*map(str,TIERS)]
    if cell['arm'].startswith('ow_'):
        worker='pymc_flow_continuation_workflow.py';common+=['--model','flow','--block-size','32','--expected-cpus','0','--coordinates',cell['coordinates']]
    elif cell['arm']=='numpyro_nc':
        worker='continuation_precision.py';common+=['--model','flow','--batch-size','1000','--target-accept','0.9']
    elif cell['arm']=='numpyro_mixed':
        worker='mixed_flow_reference.py';common+=['--batch','1000','--target-accept','0.9']
    else:raise ValueError('Unknown comparison arm')
    return [plan['python'],str(HERE/'hardware_control.py'),'--cpus','0','--record',str(Path(out).parent/(cell['id']+'-hardware.json')),
        '--timeout','1800','--',plan['python'],str(HERE/worker),*common]


def create(out,python,package,attestation,fixtures,seed_audit):
    """Prepare a draft only; fresh exact-token seed audit must already exist."""
    audit=load(seed_audit)
    if audit.get('status')!='passed' or sorted(audit.get('seeds',[]))!=sorted(SEEDS+PREDICTIVE) or audit.get('hits')!=[] or not audit.get('scope'):raise ValueError('Exact prospective seed audit required')
    if len(fixtures)!=2:raise ValueError('Exactly T128 and T1000 fixtures required')
    package=Path(package).resolve();out=Path(out).resolve()
    bound={str(Path(p).resolve()):sha(p) for p in [python,package/'owalnuts/__init__.py',package/'owalnuts/_owalnuts.pyd',attestation,seed_audit]}
    bound.update(attested_dependencies(attestation,python,package))
    plan=dict(frozen=False,phase='development',qualified=False,expected=8,cells=[],python=str(Path(python).resolve()),pythonpath=str(package),
        bound_files=bound,study_bindings=sources(),attestation=str(Path(attestation).resolve()),runtime=runtime(python),seed_audit=audit,
        timeout_seconds=1800,maximum_worker_seconds=14400,chains=4,warmup=1000,tiers=TIERS,relative_mcse=.02,
        reference_target_accept=.9,candidate_tuning='Unchanged public defaults; attested core/adapter',
        initialization_policy='Identical existing explicit canonical starts across all four arms; coordinate transport only, no truth-informed changes',
        cache_policy='Fresh processes with existing disk caches retained; contained CPU0; no overlapping timed work',
        parity_policy='Both public arms run native-vs-independent normalized parity. Mixed NumPyro additionally runs direct-vs-canonical+Jacobian value/gradient parity. Existing NC NumPyro target is independently tested but has no runtime parity stage. All incurred parity is charged and separately reported.',
        cost_policy='Full wrapper/import/compilation/parity/adaptation/draw/diagnostic/prediction/serialization costs; all eight outcomes retained',
        comparison_policy='Fresh matched NC baselines; no historical timing ratios. Improvement assessed within posterior/seed only if both relevant arms pass. Two development posteriors are not broad reliability evidence.',
        failure_policy='No retry of any started cell; immutable records; provenance drift terminalizes all remaining cells')
    orders=[['numpyro_nc','ow_mixed','ow_nc','numpyro_mixed'],['numpyro_mixed','ow_nc','ow_mixed','numpyro_nc']]
    for index,(fixture,periods) in enumerate(zip(fixtures,[128,1000])):
        fixture=Path(fixture).resolve();shape=fixture_contract(load(fixture),periods)
        if shape['forecast_rows']!=4:raise ValueError('Exactly four one-step group forecasts required')
        for arm in orders[index]:
            cell=dict(id=f'T{periods}-{arm}',arm=arm,coordinates='mixed_slopes' if arm.endswith('mixed') else 'noncentered',
                fixture=str(fixture),fixture_sha256=sha(fixture),seed=SEEDS[index],predictive_seed=PREDICTIVE[index],**shape)
            cell['command']=command(plan,cell,out/cell['id']);plan['cells'].append(cell)
    out.mkdir(parents=True,exist_ok=False);save(out/'plan-draft.json',plan)
    return plan


def verify(path,plan,original):
    if sha(path)!=original or path.with_suffix('.sha256').read_text().strip()!=original:raise ValueError('Plan drift')
    if sources()!=plan['study_bindings'] or any(sha(p)!=v for p,v in plan['bound_files'].items()):raise ValueError('Source/runtime binding drift')
    if runtime(plan['python'])!=plan['runtime']:raise ValueError('Runtime versions drift')
    for cell in plan['cells']:
        if sha(cell['fixture'])!=cell['fixture_sha256']:raise ValueError('Fixture drift')


def gate(report,cell):
    rows=report['evaluation']['forecast']['rows']
    if {(r['horizon'],r['group']) for r in rows}!={(1,g) for g in range(4)} or len(rows)!=4:raise ValueError('Forecast family mismatch')
    if set(report['evaluation']['canonical_parameter_diagnostics'])!={f'q_{i}' for i in range(cell['dimension'])}:raise ValueError('Canonical coordinate family mismatch')
    return fit_gate(report,cell)


def validate(plan,cell,report,out):
    if report.get('status')!='completed':return False
    candidate=cell['arm'].startswith('ow_');mixed=cell['coordinates']=='mixed_slopes'
    if cell['arm']!='numpyro_mixed':
        alias=dict(cell,arm='owalnuts_continuation' if candidate else 'numpyro_continuation')
        result=validate_worker(plan,alias,report)
    else:
        expected=norm(plan['study_bindings']);expected[str(Path(cell['fixture']).resolve()).casefold()]=cell['fixture_sha256']
        expected[str(Path(plan['python']).resolve()).casefold()]=sha(plan['python'])
        actual=norm(report['bindings'])
        if any(actual.get(k)!=v for k,v in expected.items()):raise ValueError('Mixed reference bindings mismatch')
        settings=report['settings']
        if settings['warmup']!=1000 or settings['chains']!=4 or settings['target_accept']!=.9 or settings['batch']!=1000 or settings['tiers']!=TIERS:raise ValueError('Mixed reference settings mismatch')
        if report['seed']!=cell['seed'] or report['predictive_seed']!=cell['predictive_seed'] or report['initial_positions']!=cell['starts']:raise ValueError('Mixed reference seeds/starts mismatch')
        if report['hardware_control']['realized_cpus']!=[0]:raise ValueError('Mixed reference affinity mismatch')
        if set(report['precision_plan']['names'])!=set(NAMES) or report['precision_plan']['forecast_rows']!=4:raise ValueError('Mixed reference precision scope mismatch')
        result=report['precision_pass']
    if report.get('coordinates')!=cell['coordinates']:raise ValueError('Coordinates mismatch')
    if candidate and report['hardware_control']['realized_cpus']!=[0]:raise ValueError('Candidate affinity mismatch')
    if mixed:
        parity=report.get('parity',{})
        if parity.get('passed') is not True or parity.get('jax_enable_x64') is not True or parity.get('normalized_canonical_jacobian_value_and_gradient') is not True or not parity.get('cases'):raise ValueError('Mixed normalized parity missing')
    attempts=report['attempts'];draws=[a['draws'] for a in attempts]
    if not draws or draws!=TIERS[:len(draws)]:raise ValueError('Tier sequence mismatch')
    calls=report['warmup_target_calls'] if candidate else None
    for i,attempt in enumerate(attempts):
        tier=attempt['draws'];fit=load(out/(f'draws-{tier}/fit-report.json' if candidate else f'draws-{tier}-report.json'))
        passed=gate(fit,cell)
        if passed!=attempt['screen']['pass'] or (passed and i!=len(attempts)-1):raise ValueError('First-pass tier mismatch')
        if set(attempt['screen']['parameter_functionals'])!=set(NAMES) or attempt['screen']['forecast_rows']!=4 or attempt['screen']['threshold']!=.02:raise ValueError('Attempt precision family mismatch')
        if candidate:
            raw=out/f'draws-{tier}/python-pymc-flow-raw.json';validate_raw_starts(raw,cell['starts'])
            if tail_field(raw,'adapted_metadata')!=report['adapted_metadata']:raise ValueError('Candidate metric/tuning changed')
            if attempt['added_draws']!=tier-(draws[i-1] if i else 0):raise ValueError('Candidate retained increment mismatch')
            calls+=attempt['added_target_calls']
            if calls!=attempt['cumulative_target_calls']:raise ValueError('Candidate cumulative callback mismatch')
        elif mixed:validate_raw_starts(out/f'draws-{tier}-raw.json',cell['starts'])
    if not candidate:
        if not mixed:validate_raw_starts(out/'numpyro-continuation-raw.json',cell['starts'])
        checkpoints=report['checkpoints']
        if [v['draws_per_chain'] for v in checkpoints]!=list(range(1000,draws[-1]+1,1000)) or len({v['adaptation_sha256'] for v in checkpoints})!=1:raise ValueError('Reference frozen continuation mismatch')
        for i,checkpoint in enumerate(checkpoints):
            before=checkpoint['start_iterations'];after=checkpoint['end_iterations']
            if len(before)!=4 or len(after)!=4 or any(b-a!=1000 for a,b in zip(before,after)) or (i and before!=checkpoints[i-1]['end_iterations']):raise ValueError('Reference iteration continuity mismatch')
    else:
        if calls!=report['total_target_calls'] or calls!=report['session_progress_before_close']['target_calls'] or report['session_progress_before_close']['completed_transitions']!=[1000+draws[-1]]*4:raise ValueError('Candidate terminal work mismatch')
        if not 0<=report['initialization_target_calls']<=report['warmup_target_calls']:raise ValueError('Candidate initialization work mismatch')
    final=gate(report,cell)
    if result!=final or report['precision_pass']!=final or (not final and draws[-1]!=8000):raise ValueError('Terminal gate mismatch or early failed stop')
    return final


def execute(path):
    path=Path(path).resolve();plan=load(path);original=sha(path)
    if plan.get('frozen') is not True or plan['expected']!=8 or len(plan['cells'])!=8 or len({c['id'] for c in plan['cells']})!=8:raise ValueError('Frozen eight-cell plan required')
    abort=None
    for cell in plan['cells']:
        out=path.parent/cell['id'];status=path.parent/(cell['id']+'-status.json');marker=path.parent/(cell['id']+'-started.json')
        if out.exists() or status.exists() or marker.exists():raise ValueError('Already attempted; no automatic retry')
        if abort:
            save(status,dict(id=cell['id'],status='unattempted_provenance_abort',reason=abort,success=False,elapsed_seconds=0));continue
        save(marker,dict(id=cell['id'],plan_sha256=original));tick=time.perf_counter();record=dict(id=cell['id'],success=False,returncode=None)
        try:
            try:verify(path,plan,original)
            except Exception as exc:abort=str(exc);raise
            args=command(plan,cell,out)
            if args!=cell['command']:raise ValueError('Frozen command mismatch')
            record['command']=args
            with (path.parent/(cell['id']+'.log')).open('x') as log:r=subprocess.run(args,cwd=HERE,env=dict(os.environ,PYTHONPATH=plan['pythonpath']),stdout=log,stderr=subprocess.STDOUT)
            record['returncode']=r.returncode;save(path.parent/(cell['id']+'-exit.json'),dict(record))
            try:verify(path,plan,original)
            except Exception as exc:abort=str(exc);raise
            hp=path.parent/(cell['id']+'-hardware.json');hardware=load(hp);record.update(hardware_sha256=sha(hp),hardware_status=hardware['status'])
            if hardware.get('job_active_processes_after_cleanup')!=0 or hardware.get('realized_cpus')!=[0]:raise ValueError('Containment/affinity failure')
            if hardware['status']=='worker-timeout':
                if r.returncode!=124:raise ValueError('Timeout exit mismatch')
                record['status']='budgeted_computational_timeout'
            else:
                name='python-pymc-flow-report.json' if cell['arm'].startswith('ow_') else 'report.json' if cell['arm']=='numpyro_mixed' else 'numpyro-continuation-report.json'
                rp=out/name;report=load(rp);record['report_sha256']=sha(rp);passed=validate(plan,cell,report,out)
                record.update(status='completed' if report.get('status')=='completed' else 'worker_failed',success=passed and r.returncode==0 and hardware['status']=='completed')
        except Exception as exc:record.update(status='executor_or_validation_failed',error=str(exc))
        record['elapsed_seconds']=time.perf_counter()-tick;save(status,record)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=['plan','run']);p.add_argument('--out',type=Path);p.add_argument('--python',type=Path);p.add_argument('--package',type=Path)
    p.add_argument('--attestation',type=Path);p.add_argument('--fixtures',nargs=2,type=Path);p.add_argument('--seed-audit',type=Path);p.add_argument('--plan',type=Path);a=p.parse_args()
    if a.action=='plan':create(a.out,a.python,a.package,a.attestation,a.fixtures,a.seed_audit)
    else:execute(a.plan)
