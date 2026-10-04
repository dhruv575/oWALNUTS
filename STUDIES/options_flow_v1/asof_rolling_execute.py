"""Study-specific as-of replay gate and terminal controller; unvalidated draft."""
import math
import os
import subprocess
import time
from pathlib import Path
from continuation_comparison import load,save,sha,validate_raw_starts,norm
from masked_market_comparison_execute import tail_field
from asof_rolling_protocol import HERE,ORIGINS,ARMS,command,runtime_versions

TIERS=[1000,2000,4000,8000]


def gate(report,cell):
    e=report['evaluation'];f=e['functionals'];q=e['canonical_parameter_diagnostics']
    if set(f)!=set(cell['precision_names']) or set(q)!={f'q_{i}' for i in range(140)} or e['chain_count']!=4:raise ValueError('Diagnostic family mismatch')
    def finite(v):return type(v) in (int,float) and math.isfinite(v)
    def health(v):return all(finite(v[k]) for k in ['rhat','bulk_ess','tail_ess']) and 0<v['rhat']<=1.01 and min(v['bulk_ess'],v['tail_ess'])>=400
    def precise(bounds,errors):return len(bounds)==len(errors)==2 and all(finite(v) for v in bounds+errors) and bounds[1]>bounds[0] and min(errors)>=0 and max(errors)/(bounds[1]-bounds[0])<=.02
    forecast=e['forecast'];rows=forecast['rows'];expected={tuple(v) for v in cell['forecast_cells']}
    if not expected:raise ValueError('Empty forecast family must remain unattempted')
    if len(rows)!=4 or {(r['horizon'],r['group']) for r in rows}!={(1,g) for g in range(4)}:raise ValueError('Scheduled forecast family mismatch')
    available=[]
    for r in rows:
        eligible=(r['horizon'],r['group']) in expected
        if r['grid_index']!=128 or r['forecast_available'] is not eligible or r['target_observed'] is not False or any(r[k] is not None for k in ['observed','covered','interval_score']):raise ValueError('Future labels or eligibility/grid drift')
        if eligible:
            if r['width']!=r['upper']-r['lower']:raise ValueError('Interval width mismatch')
            available.append(r)
        elif any(r[k] is not None for k in ['lower','upper','width','endpoint_mcse']):raise ValueError('Unavailable target forecast fabricated')
    if forecast['scored_cells']!=0 or forecast['observed_target_cells']!=0 or forecast['available_forecast_cells']!=len(expected):raise ValueError('Forecast denominator drift')
    return report.get('status')=='completed' and report['retained_divergences']==0 and all(health(v) for v in [*q.values(),*f.values()]) and all(precise(v['interval_90'],v['endpoint_mcse']) for v in f.values()) and all(precise([v['lower'],v['upper']],v['endpoint_mcse']) for v in available)


def verify(path,plan,digest):
    if sha(path)!=digest or path.with_suffix('.sha256').read_text().strip()!=digest:raise ValueError('Plan drift')
    if {str(p.resolve()):sha(p) for p in HERE.glob('*.py')}!=plan['study_bindings']:raise ValueError('Source drift')
    if any(sha(p)!=v for p,v in plan['bound_files'].items()) or any(sha(c['fixture'])!=c['fixture_sha256'] for c in plan['cells']):raise ValueError('Runtime/input drift')
    if runtime_versions(plan['python'])!=plan['runtime']:raise ValueError('Package drift')


def validate_result(plan,cell,report,out):
    if report.get('status')!='completed':return False
    public=cell['arm']=='owalnuts_continuation';settings=report['settings'] if public else report['plan']
    if settings['chains']!=4 or settings['warmup']!=1000 or report['seed']!=cell['seed']:raise ValueError('Sampling contract mismatch')
    if public:
        if report['initial_positions']!=cell['starts'] or report['predictive_seed']!=cell['predictive_seed'] or report['parity']['passed'] is not True:raise ValueError('Start/parity mismatch')
        expected=norm(plan['study_bindings']);expected.update({k:v for k,v in norm(plan['bound_files']).items() if Path(k).name in ['python.exe','__init__.py','_owalnuts.pyd']});expected[str(Path(cell['fixture']).resolve()).casefold()]=cell['fixture_sha256']
        actual=norm(report['bindings'])
        if any(actual.get(k)!=v for k,v in expected.items()) or report['hardware_control']['realized_cpus']!=[0]:raise ValueError('Public provenance mismatch')
        if report.get('arm')!='python-pymc-masked-flow-noncentered-continuation' or report['model']!='masked-flow' or settings['threads']!=1 or settings['block_size']!=32:raise ValueError('Public configuration mismatch')
    else:
        if settings.get('model')!='masked_flow' or settings.get('arm')!='numpyro-masked-noncentered-continuation':raise ValueError('Reference model/arm mismatch')
        if settings['source']!={Path(k).name:v for k,v in plan['study_bindings'].items()} or settings['fixture_sha256']!=cell['fixture_sha256']:raise ValueError('Reference provenance mismatch')
        if settings['target_accept']!=.9 or settings['batch']!=1000 or settings['cpu_affinity']!=[0] or settings['predictive_seed']!=cell['predictive_seed']:raise ValueError('Reference configuration mismatch')
    attempts=report['attempts'];counts=[a['draws'] for a in attempts]
    if not counts or counts!=TIERS[:len(counts)]:raise ValueError('Tier mismatch')
    calls=report.get('warmup_target_calls',0)
    for i,a in enumerate(attempts):
        fit=load(out/(f'draws-{a["draws"]}/fit-report.json' if public else f'draws-{a["draws"]}-report.json'))
        passed=gate(fit,cell)
        if a['screen']['pass']!=passed or (passed and i!=len(attempts)-1):raise ValueError('First passing tier mismatch')
        if public:
            raw=out/f'draws-{a["draws"]}/python-pymc-flow-raw.json';validate_raw_starts(raw,cell['starts'])
            if tail_field(raw,'adapted_metadata')!=report['adapted_metadata']:raise ValueError('Frozen adaptation changed')
            calls+=a['added_target_calls']
            if calls!=a['cumulative_target_calls'] or a['added_draws']!=counts[i]-(counts[i-1] if i else 0):raise ValueError('Continuation work mismatch')
    if public:
        if calls!=report['total_target_calls'] or calls!=report['session_progress_before_close']['target_calls'] or report['session_progress_before_close']['completed_transitions']!=[1000+counts[-1]]*4:raise ValueError('Terminal work mismatch')
    else:
        validate_raw_starts(out/'raw.json',cell['starts']);checkpoints=report['checkpoints']
        if [c['draws_per_chain'] for c in checkpoints]!=list(range(1000,counts[-1]+1,1000)) or len({c['adaptation_sha256'] for c in checkpoints})!=1:raise ValueError('Reference state changed')
        validate_checkpoint_continuity(checkpoints)
    passed=gate(report,cell)
    if report['precision_pass']!=passed or (not passed and counts[-1]!=8000):raise ValueError('Final precision mismatch')
    return passed


def execute(path):
    path=Path(path).resolve();plan=load(path);digest=sha(path)
    if plan.get('frozen') is not True or plan['origins']!=ORIGINS or plan['expected']!=32 or len(plan['cells'])!=32 or len({c['id'] for c in plan['cells']})!=32:raise ValueError('Frozen reviewed32-cell plan required')
    validate_plan(plan,path.parent)
    # Preflight every output before any launch; never silently resume/retry.
    for c in plan['cells']:
        if any((path.parent/(c['id']+suffix)).exists() for suffix in ['', '-status.json','-started.json','-exit.json','-hardware.json','.log']):raise ValueError('Already attempted cell')
    abort=None
    for c in plan['cells']:
        out=path.parent/c['id'];status=path.parent/(c['id']+'-status.json')
        if abort:save(status,dict(status='unattempted_provenance_abort',error=abort,success=False,elapsed_seconds=0));continue
        save(path.parent/(c['id']+'-started.json'),dict(id=c['id'],plan_sha256=digest,fixture_sha256=c['fixture_sha256']))
        tick=time.perf_counter();record=dict(id=c['id'],success=False)
        try:
            try:verify(path,plan,digest)
            except Exception as exc:abort=str(exc);raise
            if not c['forecast_cells']:
                overhead=time.perf_counter()-tick
                record.update(status='no_forecast_eligible',elapsed_seconds=overhead,worker_seconds=0,attempted=False,controller_seconds=overhead)
                save(status,record);continue
            args=command(plan,c,out)
            if args!=c['command']:raise ValueError('Command drift')
            with (path.parent/(c['id']+'.log')).open('x') as log:
                proc=subprocess.run(args,cwd=HERE,env=dict(os.environ,PYTHONPATH=plan['pythonpath']),stdout=log,stderr=subprocess.STDOUT)
            record['returncode']=proc.returncode;save(path.parent/(c['id']+'-exit.json'),dict(record))
            try:verify(path,plan,digest)
            except Exception as exc:abort=str(exc);raise
            hp=path.parent/(c['id']+'-hardware.json');h=load(hp);record['hardware_sha256']=sha(hp)
            validate_hardware(h,args,proc.returncode,plan['timeout_seconds'])
            if h['status']=='worker-timeout':
                if proc.returncode!=124:raise ValueError('Timeout exit mismatch')
                record['status']='budgeted_computational_timeout'
            else:
                rp=out/('python-pymc-flow-report.json' if c['arm']=='owalnuts_continuation' else 'report.json');report=load(rp)
                record.update(status=report['status'],report_sha256=sha(rp),success=validate_result(plan,c,report,out) and proc.returncode==0 and h['status']=='completed')
        except Exception as exc:record.update(status='executor_or_validation_failed',error=str(exc))
        record['elapsed_seconds']=time.perf_counter()-tick;save(status,record)


def validate_plan(plan,directory):
    """Exact32-cell schema; called before freezing and every execution entry."""
    from asof_rolling_protocol import validate_seeds,origin_fixture,no_flow,build_cells
    directory=Path(directory).resolve()
    if plan['origins']!=ORIGINS or plan['window']!=128 or plan['expected']!=32 or plan['chains']!=4 or plan['warmup']!=1000 or plan['tiers']!=TIERS or plan['timeout_seconds']!=600 or plan['relative_mcse']!=.02:
        raise ValueError('Prospective schedule/configuration changed')
    if plan['schema']!=dict(dimension=140,precision_names=list(__import__('masked_market_comparison_plan').NAMES),forecast_groups=[0,1,2,3],forecast_eligibility='feature_and_known_anchor'):raise ValueError('Precision scope changed')
    validate_seeds(plan['seed_rows'],plan['seed_audit_path'])
    if plan['python']!=str(Path(plan['python']).resolve()):raise ValueError('Interpreter must be canonical')
    panel=load(plan['panel_path']);protocol=load(plan['protocol_path']);fixtures={}
    for row in plan['seed_rows']:
        base=origin_fixture(panel,protocol,origin_index=row['origin'],window=128,init_seed=row['init_seed'])
        for kind,expected in [('flow',base),('no-flow',no_flow(base))]:
            path=directory/'fixtures'/f'{row["origin"]}-{kind}.json'
            if path.resolve().parent!=(directory/'fixtures').resolve() or load(path)!=expected:raise ValueError('As-of fixture/start transport changed')
            fixtures[(row['origin'],kind)]=path
    expected=build_cells(fixtures,plan['seed_rows'],directory,plan)
    if plan['cells']!=expected:raise ValueError('Cell identity/order/seeds/commands/fixtures changed')
    if len({c['id'] for c in expected})!=32:raise ValueError('Duplicate output IDs')
    if any((directory/c['id']).resolve().parent!=directory for c in expected):raise ValueError('Output escaped experiment')
    for c in expected:
        if any((directory/(c['id']+suffix)).exists() for suffix in ['', '-status.json','-started.json','-exit.json','-hardware.json','.log']):raise ValueError('Existing output/attempt; no overwrite or retry')
    if {str(p.resolve()):sha(p) for p in HERE.glob('*.py')}!=plan['study_bindings']:raise ValueError('Study source changed since preparation')
    if any(sha(p)!=v for p,v in plan['bound_files'].items()) or runtime_versions(plan['python'])!=plan['runtime']:raise ValueError('Bound inputs/runtime changed')


def freeze(directory):
    """Separate explicit action; validation never samples or overwrites."""
    directory=Path(directory).resolve();plan=load(directory/'plan-draft.json')
    if plan.get('frozen') is not False:raise ValueError('Unfrozen draft required')
    if (directory/'plan.json').exists() or (directory/'plan.sha256').exists():raise ValueError('Already frozen')
    if sha(directory/'intent.json')!=plan['intent_sha256']:raise ValueError('Prospective intent changed')
    intent=load(directory/'intent.json')
    if any(plan.get(k)!=v for k,v in intent.items()):raise ValueError('Draft differs from pre-generation intent')
    validate_plan(plan,directory);plan['frozen']=True
    save(directory/'plan.json',plan)
    with (directory/'plan.sha256').open('x') as handle:handle.write(sha(directory/'plan.json'))
    return plan


def validate_hardware(h,args,returncode,timeout):
    if h['job_active_processes_after_cleanup']!=0 or h['realized_cpus']!=[0] or h.get('enforced_before_worker_launch') is not True:raise ValueError('Containment/affinity failed')
    if h.get('command')!=args[args.index('--')+1:] or h.get('returncode')!=returncode:raise ValueError('Hardware command/exit mismatch')
    if h.get('containment',{}).get('kind')!='windows-job-object' or h['containment'].get('assigned_before_worker_execution') is not True:raise ValueError('Expected Windows pre-execution job containment')
    elapsed=h.get('elapsed_seconds')
    if type(elapsed) not in (int,float) or not math.isfinite(elapsed) or elapsed<0:raise ValueError('Invalid hardware elapsed')
    if h['status']=='worker-timeout' and (returncode!=124 or elapsed<timeout):raise ValueError('Timeout lacks elapsed/exit evidence')


def validate_checkpoint_continuity(checkpoints):
    for i,c in enumerate(checkpoints):
        before=c['start_iterations'];after=c['end_iterations']
        if len(before)!=4 or len(after)!=4 or any(b-a!=1000 for a,b in zip(before,after)) or (i and before!=checkpoints[i-1]['end_iterations']):raise ValueError('Reference checkpoint continuity mismatch')
