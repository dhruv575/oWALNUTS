"""Draft six-cell T1000 implementation-matched mixed comparison; never auto-freeze."""
import argparse
import re
from pathlib import Path
from continuation_comparison import sha,load,save,attested_dependencies
from flow_continuation_comparison import fixture_contract
from mixed_flow_comparison import runtime,sources,command as base_command,validate as base_validate
HERE=Path(__file__).resolve().parent
SEEDS=[105110001,105110002]
ARMS=['ow_mixed','numpyro_nc','numpyro_mixed']
ORDERS=[ARMS,list(reversed(ARMS))]
TIERS=[1000,2000,4000,8000]

def audit_seeds(path):
    audit=load(path);expected=SEEDS+[s+130000 for s in SEEDS]
    if audit.get('status')!='passed' or sorted(audit.get('seeds',[]))!=sorted(expected) or audit.get('hits')!=[] or not audit.get('scope') or not audit.get('auditor') or not audit.get('inventory_files'):raise ValueError('Bound historical exact-token seed audit required')
    pattern=re.compile(r'(?<!\d)(?:'+ '|'.join(map(str,expected))+r')(?!\d)')
    for filename,digest in audit['inventory_files'].items():
        if sha(filename)!=digest or pattern.search(Path(filename).read_text(encoding='utf-8-sig')):raise ValueError('Historical seed audit mismatch/collision')
    return audit

def command(plan,cell,out):
    result=base_command(plan,cell,out)
    if cell['arm']=='numpyro_mixed':result+=['--implementation','associative']
    return result

def validate_report(plan,cell,report,out):
    if cell['arm']=='numpyro_mixed' and report.get('status')=='completed':
        if report.get('implementation')!='associative' or report.get('settings',{}).get('implementation')!='associative' or report.get('parity',{}).get('implementation')!='associative':raise ValueError('Actual associative target/runtime parity required')
    return base_validate(plan,cell,report,out)

def create(out,python,package,attestation,fixture,seed_audit):
    audit=audit_seeds(seed_audit);out=Path(out).resolve();fixture=Path(fixture).resolve();package=Path(package).resolve()
    shape=fixture_contract(load(fixture),1000)
    if shape['forecast_rows']!=4:raise ValueError('Exact four one-step forecast cells required')
    bound={str(Path(p).resolve()):sha(p) for p in [python,package/'owalnuts/__init__.py',package/'owalnuts/_owalnuts.pyd',attestation,seed_audit]}
    bound.update(audit['inventory_files']);bound.update(attested_dependencies(attestation,python,package))
    plan=dict(frozen=False,phase='development',qualified=False,expected=6,python=str(Path(python).resolve()),pythonpath=str(package),bound_files=bound,study_bindings=sources(),runtime=runtime(python),seed_audit=audit,cells=[],tiers=TIERS,chains=4,warmup=1000,relative_mcse=.02,reference_target_accept=.9,timeout_seconds=1800,sum_worker_timeout_allowances=10800,
        initialization_policy='Same existing canonical starts, same fixed development posterior, all six cells; only sampler/prediction seeds differ by pair',
        implementation_policy='Both NumPyro volatility targets use associative AR prefix; beta hierarchy coordinates remain the intended difference',
        parity_policy='Native mixed and associative mixed reference actual-target normalized parity charged separately and in full; optimized NC independently tested',
        order_policy='Forward and reverse orders; NC occupies middle twice. Two seeds cannot fully counterbalance three positions; no order-neutrality claim',
        cache_policy='Fresh CPU0 contained processes; existing disk caches retained; sequential execution only',
        comparison_policy='Only fresh within-seed passing-arm comparisons at identical full precision scope; no historical ratios, no broad reliability claim',
        failure_policy='All six expected outcomes retained, no automatic retry, source drift aborts remaining cells')
    for pair,order in enumerate(ORDERS):
        for arm in order:
            cell=dict(id=f'pair{pair}-{arm}',arm=arm,coordinates='mixed_slopes' if arm.endswith('mixed') else 'noncentered',fixture=str(fixture),fixture_sha256=sha(fixture),seed=SEEDS[pair],predictive_seed=SEEDS[pair]+130000,implementation='associative' if arm.startswith('numpyro') else 'pymc_block32',**shape)
            cell['command']=command(plan,cell,out/cell['id']);plan['cells'].append(cell)
    validate_plan(plan,out);out.mkdir(parents=True,exist_ok=False);save(out/'plan-draft.json',plan);return plan

def validate_plan(plan,directory):
    expected=[(i,a) for i,order in enumerate(ORDERS) for a in order]
    if plan.get('expected')!=6 or len(plan['cells'])!=6:raise ValueError('Six-cell denominator required')
    fixture_ids={(c['fixture'],c['fixture_sha256']) for c in plan['cells']}
    if len(fixture_ids)!=1:raise ValueError('One unchanged fixed posterior required')
    starts=plan['cells'][0]['starts']
    for cell,(pair,arm) in zip(plan['cells'],expected):
        if cell['id']!=f'pair{pair}-{arm}' or cell['arm']!=arm or cell['seed']!=SEEDS[pair] or cell['predictive_seed']!=SEEDS[pair]+130000 or cell['starts']!=starts:raise ValueError('Prespecified order/seeds/starts changed')
        if cell['coordinates']!=('mixed_slopes' if arm.endswith('mixed') else 'noncentered') or cell['implementation']!=('associative' if arm.startswith('numpyro') else 'pymc_block32'):raise ValueError('Coordinate/implementation recipe changed')
        if cell['command']!=command(plan,cell,Path(directory)/cell['id']):raise ValueError('Command changed')
    if plan['tiers']!=TIERS or plan['chains']!=4 or plan['warmup']!=1000 or plan['timeout_seconds']!=1800 or plan['reference_target_accept']!=.9 or plan['relative_mcse']!=.02:raise ValueError('Fixed matched procedure changed')

def verify_bindings(plan):
    if sources()!=plan['study_bindings'] or any(sha(path)!=digest for path,digest in plan['bound_files'].items()):raise ValueError('Bound source/runtime/audit drift')
    if runtime(plan['python'])!=plan['runtime']:raise ValueError('Runtime versions drift')
    for cell in plan['cells']:
        if sha(cell['fixture'])!=cell['fixture_sha256']:raise ValueError('Fixture drift')
        actual=fixture_contract(load(cell['fixture']),1000)
        if any(cell.get(k)!=v for k,v in actual.items()):raise ValueError('Physical fixture/start contract changed')

def freeze(directory):
    directory=Path(directory).resolve();draft=directory/'plan-draft.json';plan=load(draft)
    if plan.get('frozen') is not False:raise ValueError('Unfrozen reviewed draft required')
    validate_plan(plan,directory);verify_bindings(plan)
    # Freeze records the exact reviewed draft; no recipe generation or selection.
    plan.update(frozen=True,reviewed_draft_sha256=sha(draft));path=directory/'plan.json';save(path,plan)
    with path.with_suffix('.sha256').open('x') as handle:handle.write(sha(path))

def execute(path):
    import os,subprocess,time
    path=Path(path).resolve();plan=load(path);original=sha(path)
    if plan.get('frozen') is not True:raise ValueError('Frozen six-cell plan required')
    validate_plan(plan,path.parent)
    def check():
        if sha(path)!=original or path.with_suffix('.sha256').read_text().strip()!=original or sha(path.parent/'plan-draft.json')!=plan['reviewed_draft_sha256']:raise ValueError('Frozen plan/draft drift')
        verify_bindings(plan)
    # Reject all existing attempts before making any new mutation.
    for c in plan['cells']:
        for name in [c['id'],c['id']+'-status.json',c['id']+'-started.json',c['id']+'-hardware.json',c['id']+'-exit.json',c['id']+'.log']:
            if (path.parent/name).exists():raise ValueError('Existing attempt; no retry/overwrite')
    abort=None;records=[];begin=time.perf_counter()
    for cell in plan['cells']:
        out=path.parent/cell['id'];status=path.parent/(cell['id']+'-status.json')
        record=dict(id=cell['id'],plan_sha256=original,fixture_sha256=cell['fixture_sha256'],seed=cell['seed'],predictive_seed=cell['predictive_seed'],success=False,returncode=None,elapsed_seconds=0.)
        if abort:
            record.update(status='unattempted_provenance_abort',error=abort);save(status,record);records.append(record);continue
        save(path.parent/(cell['id']+'-started.json'),record);tick=time.perf_counter()
        try:
            try:check()
            except Exception as exc:abort=str(exc);raise
            args=command(plan,cell,out)
            if args!=cell['command']:raise ValueError('Frozen command mismatch')
            record['command']=args
            with (path.parent/(cell['id']+'.log')).open('x') as log:
                result=subprocess.run(args,cwd=HERE,env=dict(os.environ,PYTHONPATH=plan['pythonpath']),stdout=log,stderr=subprocess.STDOUT)
            record['returncode']=result.returncode;save(path.parent/(cell['id']+'-exit.json'),dict(record))
            try:check()
            except Exception as exc:abort=str(exc);raise
            hp=path.parent/(cell['id']+'-hardware.json');hardware=load(hp)
            record.update(hardware_sha256=sha(hp),wrapper_seconds=hardware.get('elapsed_seconds'),hardware_status=hardware.get('status'))
            if hardware.get('job_active_processes_after_cleanup')!=0 or hardware.get('realized_cpus')!=[0] or hardware.get('command')!=args[args.index('--')+1:] or hardware.get('returncode')!=result.returncode or hardware.get('containment',{}).get('assigned_before_worker_execution') is not True:raise ValueError('Containment/command/exit mismatch')
            if hardware['status']=='worker-timeout':
                if result.returncode!=124:raise ValueError('Invalid timeout exit')
                record['status']='budgeted_computational_timeout'
            else:
                name={'ow_mixed':'python-pymc-flow-report.json','numpyro_nc':'numpyro-continuation-report.json','numpyro_mixed':'report.json'}[cell['arm']]
                rp=out/name
                if not rp.exists():record['status']='missing_worker_report'
                else:
                    report=load(rp);record['report_sha256']=sha(rp);passed=validate_report(plan,cell,report,out)
                    record.update(status='completed' if report.get('status')=='completed' else 'worker_failed',success=bool(passed and result.returncode==0 and hardware['status']=='completed'))
        except Exception as exc:record.update(status='executor_or_validation_failed',error=f'{type(exc).__name__}: {exc}')
        record['elapsed_seconds']=time.perf_counter()-tick;save(status,record);records.append(record)
    save(path.parent/'execution-summary.json',dict(plan_sha256=original,expected=6,recorded=len(records),successful=sum(r['success'] for r in records),cells=records,total_seconds=time.perf_counter()-begin,qualified=False,cost_scope='All fresh contained invocations and controller validation; failed and unattempted cells remain explicit. No historical ratios.'))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=['draft','freeze','run']);p.add_argument('--out',type=Path,required=True)
    for name in ['python','package','attestation','fixture','seed-audit']:p.add_argument('--'+name,type=Path)
    a=p.parse_args()
    if a.action=='draft':create(a.out,a.python,a.package,a.attestation,a.fixture,a.seed_audit)
    elif a.action=='freeze':freeze(a.out)
    else:execute(a.out/'plan.json')

