"""Terminal-safe executor for a reviewed sparse-market draft plan.

Static prototype: do not launch until contract tests pass and a prospective plan
is independently frozen. All four outcomes remain in the denominator.
"""
import argparse
import json
import math
import os
from pathlib import Path
import subprocess
import time
from continuation_comparison import sha,load,save,norm,validate_raw_starts
from masked_market_comparison_plan import HERE,command,contract

TIERS=[1000,2000,4000,8000]


def verify(path,plan,original):
    if sha(path)!=original or path.with_suffix('.sha256').read_text().strip()!=original:raise ValueError('Plan drift')
    if {str(p.resolve()):sha(p) for p in HERE.glob('*.py')}!=plan['study_bindings']:raise ValueError('Study source drift')
    if any(sha(p)!=value for p,value in plan['bound_files'].items()):raise ValueError('Bound source/runtime drift')
    if sha(plan['fixture'])!=plan['fixture_sha256']:raise ValueError('Matched fixture drift')
    if contract(load(plan['fixture']))!=plan['schema']:raise ValueError('Fixture schema drift')
    runtime=json.loads(subprocess.check_output([plan['python'],'-c',
        "import sys,json,importlib.metadata as m; print(json.dumps(dict(python=sys.version,packages={p:m.version(p) for p in ['numpy','scipy','pymc','pytensor','numba','jax','jaxlib','numpyro','arviz']})))"],text=True))
    if runtime!=plan['runtime']:raise ValueError('Interpreter/package runtime drift')


def fit_gate(report,plan,fixture):
    """Independent gate; labels validate scoring identity but never select intervals."""
    e=report['evaluation'];functions=e['functionals'];coordinates=e['canonical_parameter_diagnostics']
    if set(functions)!=set(plan['schema']['precision_names']) or set(coordinates)!={f'q_{i}' for i in range(108)}:raise ValueError('Diagnostic family mismatch')
    if e['chain_count']!=4:raise ValueError('Chain count mismatch')
    def finite(v):return not isinstance(v,bool) and isinstance(v,(int,float)) and math.isfinite(v)
    def healthy(d):
        return all(finite(d[k]) for k in ['rhat','bulk_ess','tail_ess']) and d['rhat']<=1.01 and d['bulk_ess']>=400 and d['tail_ess']>=400
    health=report['retained_divergences']==0 and all(healthy(d) for d in [*functions.values(),*coordinates.values()])
    def precise(interval,mcse):
        return isinstance(interval,list) and isinstance(mcse,list) and len(interval)==len(mcse)==2 and all(finite(v) for v in interval+mcse) and interval[1]>interval[0] and min(mcse)>=0 and max(mcse)/(interval[1]-interval[0])<=.02
    forecast=e['forecast'];rows=forecast['rows'];indexed={(r['horizon'],r['group']):r for r in rows}
    expected={tuple(v) for v in plan['schema']['forecast_cells']}
    if len(rows)!=192 or len(indexed)!=192 or set(indexed)!=expected:raise ValueError('Forecast horizon/group family mismatch')
    future=fixture['holdout'];ym=future.get('y_available',future.get('observation_mask'));xm=future['x_available']
    for (h,g),row in indexed.items():
        observed=ym[h-1][g];available=xm[h-1][g]
        if row.get('target_observed') is not observed or row.get('forecast_available') is not available:raise ValueError('Forecast availability mismatch')
        if row['grid_index']!=future['grid_index'][h-1]:raise ValueError('Forecast grid mismatch')
        if row['observed']!=(future['y'][h-1][g] if observed else None):raise ValueError('Forecast label mismatch')
        if not observed and (row['covered'] is not None or row['interval_score'] is not None):raise ValueError('Missing label scored')
        if row['width']!=row['upper']-row['lower']:raise ValueError('Forecast width mismatch')
    if forecast['available_forecast_cells']!=192 or forecast['scored_cells']!=4 or forecast['observed_target_cells']!=4:raise ValueError('Forecast denominators mismatch')
    precision=all(precise(v['interval_90'],v['endpoint_mcse']) for v in functions.values()) and all(precise([r['lower'],r['upper']],r['endpoint_mcse']) for r in rows)
    return report.get('status')=='completed' and health and precision


def tail_field(path,field):
    path=Path(path)
    with path.open('rb') as handle:
        handle.seek(max(0,path.stat().st_size-1000000));tail=handle.read().decode()
    token=json.dumps(field)+':';start=tail.rfind(token)
    if start<0:raise ValueError('Missing raw tail field: '+field)
    return json.JSONDecoder().raw_decode(tail[start+len(token):].lstrip())[0]


def validate_report(plan,cell,report,out):
    if report.get('status')!='completed':return False
    fixture=load(cell['fixture']);candidate=cell['arm']=='owalnuts_continuation'
    if report.get('seed')!=cell['seed']:raise ValueError('Worker seed mismatch')
    if candidate:
        settings=report['settings'];bound=norm(report['bindings']);expected=norm(plan['study_bindings'])
        expected.update({k:v for k,v in norm(plan['bound_files']).items() if Path(k).name in ['python.exe','__init__.py','_owalnuts.pyd']})
        expected[str(Path(cell['fixture']).resolve()).casefold()]=cell['fixture_sha256']
        if any(bound.get(k)!=v for k,v in expected.items()):raise ValueError('Candidate runtime/source bindings mismatch')
        if report.get('model')!='masked-flow' or settings.get('block_size')!=32 or settings.get('threads')!=1 or report.get('parity',{}).get('passed') is not True:raise ValueError('Candidate target/parity mismatch')
        if report['initial_positions']!=cell['starts'] or report['predictive_seed']!=cell['predictive_seed']:raise ValueError('Candidate starts/predictive seed mismatch')
        precision=report['precision_plan']
        if set(precision['names'])!=set(plan['schema']['precision_names']) or precision['forecast_expected_cells']!=plan['schema']['forecast_cells']:raise ValueError('Candidate precision scope mismatch')
        if report['hardware_control']['realized_cpus']!=[0]:raise ValueError('Candidate affinity mismatch')
    else:
        settings=report['plan']
        if settings['fixture_sha256']!=cell['fixture_sha256'] or settings['source']!={Path(k).name:v for k,v in plan['study_bindings'].items()}:raise ValueError('Reference source/fixture mismatch')
        if settings['seed']!=cell['seed'] or settings['predictive_seed']!=cell['predictive_seed'] or settings['target_accept']!=.9 or settings['batch']!=1000 or settings['tiers']!=TIERS:raise ValueError('Reference sampler configuration mismatch')
        if settings['cpu_affinity']!=[0] or set(settings['parameter_functionals'])!=set(plan['schema']['precision_names']) or settings['forecast_cells']!=plan['schema']['forecast_cells']:raise ValueError('Reference gate/affinity mismatch')
        if any(settings['runtime'].get(k)!=v for k,v in plan['runtime']['packages'].items() if k in ['numpy','scipy','jax','jaxlib','numpyro','arviz']):raise ValueError('Reference package versions changed')
    if settings['chains']!=4 or settings['warmup']!=1000:raise ValueError('Warmup/chain mismatch')
    attempts=report['attempts'];draws=[a['draws'] for a in attempts]
    if not draws or draws!=TIERS[:len(draws)]:raise ValueError('Tier sequence mismatch')
    for i,attempt in enumerate(attempts):
        fit_path=out/(f'draws-{attempt["draws"]}/fit-report.json' if candidate else f'draws-{attempt["draws"]}-report.json')
        passing=fit_gate(load(fit_path),plan,fixture)
        if attempt['screen']['pass']!=passing or (passing and i!=len(attempts)-1):raise ValueError('Not exactly first passing tier')
        if candidate:
            raw=out/f'draws-{attempt["draws"]}/python-pymc-flow-raw.json'
            validate_raw_starts(raw,cell['starts'])
            if tail_field(raw,'adapted_metadata')!=report['adapted_metadata']:raise ValueError('Candidate frozen state changed')
    final=fit_gate(report,plan,fixture)
    if report['precision_pass']!=final or (not final and draws[-1]!=8000):raise ValueError('Final gate mismatch or early unsuccessful stop')
    if candidate:
        if [a['added_draws'] for a in attempts]!=[n-(draws[i-1] if i else 0) for i,n in enumerate(draws)]:raise ValueError('Candidate draw increments mismatch')
        total=report['warmup_target_calls']
        if not 0<=report['initialization_target_calls']<=total:raise ValueError('Invalid initialization callback accounting')
        for attempt in attempts:
            total+=attempt['added_target_calls']
            if total!=attempt['cumulative_target_calls']:raise ValueError('Cumulative callback mismatch')
        if total!=report['total_target_calls'] or total!=report['session_progress_before_close']['target_calls']:raise ValueError('Terminal callback mismatch')
        if report['session_progress_before_close']['completed_transitions']!=[1000+draws[-1]]*4:raise ValueError('Session transition accounting mismatch')
    else:
        validate_raw_starts(out/'raw.json',cell['starts']);checkpoints=report['checkpoints']
        if [v['draws_per_chain'] for v in checkpoints]!=list(range(1000,draws[-1]+1,1000)) or len({v['adaptation_sha256'] for v in checkpoints})!=1:raise ValueError('Reference continuation/frozen state mismatch')
        for i,checkpoint in enumerate(checkpoints):
            before=checkpoint['start_iterations'];after=checkpoint['end_iterations']
            if len(before)!=4 or len(after)!=4 or any(b-a!=1000 for a,b in zip(before,after)):raise ValueError('Reference chain iteration increments mismatch')
            if i and before!=checkpoints[i-1]['end_iterations']:raise ValueError('Reference chain iteration continuity mismatch')
    return final


def execute(path):
    path=Path(path).resolve();plan=load(path);original=sha(path)
    if plan.get('frozen') is not True or plan['expected']!=4 or len(plan['cells'])!=4 or len({c['id'] for c in plan['cells']})!=4:raise ValueError('Reviewed frozen four-cell plan required')
    abort=None
    for cell in plan['cells']:
        out=path.parent/cell['id'];status=path.parent/(cell['id']+'-status.json');marker=path.parent/(cell['id']+'-started.json')
        if out.exists() or status.exists() or marker.exists():raise ValueError('Already attempted cell; no automatic retry')
        if abort:
            save(status,dict(id=cell['id'],status='unattempted_provenance_abort',reason=abort,success=False,elapsed_seconds=0));continue
        save(marker,dict(id=cell['id'],plan_sha256=original));tick=time.perf_counter()
        record=dict(id=cell['id'],success=False,returncode=None)
        try:
            try:verify(path,plan,original)
            except Exception as exc:abort=str(exc);raise
            args=command(plan,cell,out)
            if args!=cell['command']:raise ValueError('Frozen command mismatch')
            record['command']=args
            with (path.parent/(cell['id']+'.log')).open('x') as log:
                result=subprocess.run(args,cwd=HERE,env=dict(os.environ,PYTHONPATH=plan['pythonpath']),stdout=log,stderr=subprocess.STDOUT)
            record['returncode']=result.returncode;save(path.parent/(cell['id']+'-exit.json'),dict(record))
            try:verify(path,plan,original)
            except Exception as exc:abort=str(exc);raise
            hp=path.parent/(cell['id']+'-hardware.json');hardware=load(hp);record.update(hardware_sha256=sha(hp),hardware_status=hardware['status'])
            if hardware.get('job_active_processes_after_cleanup')!=0 or hardware.get('realized_cpus')!=[0]:raise ValueError('Containment or affinity failure')
            if hardware['status']=='worker-timeout':
                if result.returncode!=124:raise ValueError('Timeout exit mismatch')
                record['status']='budgeted_computational_timeout'
            else:
                rp=out/('python-pymc-flow-report.json' if cell['arm']=='owalnuts_continuation' else 'report.json')
                report=load(rp);record['report_sha256']=sha(rp);passed=validate_report(plan,cell,report,out)
                record.update(status='completed' if report.get('status')=='completed' else 'worker_failed',
                    success=passed and result.returncode==0 and hardware['status']=='completed')
        except Exception as exc:record.update(status='executor_or_validation_failed',error=str(exc))
        record['elapsed_seconds']=time.perf_counter()-tick;save(status,record)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--plan',type=Path,required=True);execute(p.parse_args().plan)
