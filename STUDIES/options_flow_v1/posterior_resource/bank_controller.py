"""Prospective64-fit controller prototype. No import-time preparation/execution."""
import argparse,copy,json,os,subprocess,sys,time
from pathlib import Path
from .controller import sha,save,load,posterior,validate_outputs
from .bank_adapter import PARAMETERS,FUNCTIONALS,ENDPOINTS
EXPECTED=64


def validate_streams(rows,pilot):
    order=['public','reference','reference','public']*16
    if len(rows)!=64 or [r['backend'] for r in rows]!=order:raise ValueError('Fixed64 balanced cyclic order required')
    streams=[r[k] for r in rows for k in ['init_seed','seed','predictive_seed']]
    if len(set(streams))!=192 or any(type(v)is not int or not 0<=v<2**32 for v in streams):raise ValueError('192 distinct uint32 streams required')
    if any(r['predictive_seed']!=r['seed']+130000 for r in rows):raise ValueError('Prediction stream policy differs')
    excluded={c[k] for c in pilot['cells'] for k in ['init_seed','seed','predictive_seed']}
    if set(streams)&excluded:raise ValueError('Pilot streams excluded even when renamed')
    return streams


def validate(plan,directory):
    if plan.get('phase')!='prospective_reference_bank' or plan.get('qualified') is not False:raise ValueError('Explicit nonqualified bank phase required')
    required=dict(expected=64,warmup=1000,chains=4,retained=8000,checkpoints=[4000,8000],cpus=[0],per_fit_seconds=1800,total_seconds=21600,cleanup_reserve_seconds=15,memory_bytes=8*1024**3)
    if any(plan.get(k)!=v for k,v in required.items()):raise ValueError('Exact fixed bank resource recipe differs')
    pilot=load(plan['excluded_pilot_manifest'])
    if sha(plan['excluded_pilot_manifest'])!=plan['excluded_pilot_manifest_sha256']:raise ValueError('Pilot exclusion manifest changed')
    validate_streams(plan['streams'],pilot)
    if len(plan['cells'])!=64:raise ValueError('All64 outcomes required')
    study=Path(plan['study']);package=Path(__file__).resolve().parent
    if {str(p.resolve()):sha(p) for p in package.rglob('*.py')}!=plan['package_inventory']:raise ValueError('Package inventory drift')
    if any(sha(p)!=h for p,h in plan['bindings'].items()):raise ValueError('Source/runtime/metadata drift')
    if {str(p.resolve()) for p in study.glob('*.py')}!={p for p in plan['worker_bindings'] if p.endswith('.py')}:raise ValueError('Worker source inventory drift')
    from production_calibration_feasibility import runtime_versions
    from masked_market_comparison_plan import dispersed_starts
    if runtime_versions(plan['python'])!=plan['runtime']:raise ValueError('Runtime version drift')
    original=load(plan['original_fixture']);target=posterior(original)
    if target!=plan['posterior_sha256'] or len(original['data']['y'])!=1000 or len(original['data']['y'][0])!=4:raise ValueError('Fixed T1000 target differs')
    gate=dict(coordinates=1012,functionals=14,functional_names=list(FUNCTIONALS),forecasts=4,rhat=1.01,bulk_ess=400,tail_ess=400,retained_divergences=0,relative_mcse=.02)
    if plan['full_gate']!=gate or plan['bank_endpoints']!=ENDPOINTS:raise ValueError('Health/accuracy family differs')
    if plan['primary_endpoints']!=dict(functionals=list(PARAMETERS),forecast=dict(group=0,horizon=1,x_next=original['holdout']['x'][0][0]),probabilities=[.05,.95]):raise ValueError('Predictive scenario differs')
    for i,(c,r) in enumerate(zip(plan['cells'],plan['streams'])):
        name=f'bank-{i:02d}-{r["backend"]}'
        if c['id']!=name or c['out']!=str(directory/name) or c['fixture']!=str(directory/'fixtures'/f'{name}.json') or any(c[k]!=v for k,v in r.items()):raise ValueError('Exact cell identity/path differs')
        f=load(c['fixture']);expected=copy.deepcopy(original);expected['data']['initial_positions']=dispersed_starts(1000,4,original['data']['rho'],r['init_seed'])
        if sha(c['fixture'])!=c['fixture_sha256'] or f!=expected or posterior(f)!=target:raise ValueError('Fresh starts/target differ')


def verify_frozen(path,original=None):
    path=Path(path).resolve();digest=sha(path);p=load(path)
    if original is not None and digest!=original:raise ValueError('Frozen plan changed')
    if p.get('frozen') is not True or path.with_suffix('.sha256').read_text().strip()!=digest:raise ValueError('Explicit bank freeze required')
    intent=path.parent/'intent.json'
    if sha(intent)!=p['intent_sha256'] or any(p.get(k)!=v for k,v in load(intent).items() if k not in ['cells','frozen']):raise ValueError('Bank intent changed')
    validate(p,path.parent);return p

def execute(path):
    path=Path(path).resolve();plan=load(path);original=sha(path);started=time.perf_counter();deadline=started+plan['total_seconds'];abort=None
    if plan.get('frozen') is not True:raise ValueError('Explicit frozen plan required')
    if (path.parent/'terminal.json').exists():raise ValueError('Existing terminal record; no overwrite')
    if plan.get('expected')!=64 or len(plan.get('cells',[]))!=64 or len({c['id'] for c in plan['cells']})!=64:raise ValueError('64-cell bank intent required')
    for c in plan['cells']:
        if any((path.parent/(c['id']+s)).exists() for s in ['', '-started.json','-status.json','-hardware.json','-exit.json','.log']):raise ValueError('Never retry/overwrite any attempted cell')
    for c in plan['cells']:
        status=path.parent/(c['id']+'-status.json');record=dict(id=c['id'],success=False,resource_only=True)
        if abort:save(status,dict(record,status='unattempted_provenance_abort',error=abort,elapsed_seconds=0));continue
        tick=time.perf_counter()
        try:
            if verify_frozen(path,original)!=plan:raise ValueError('Loaded frozen plan changed')
        except Exception as exc:abort=str(exc);save(status,dict(record,status='unattempted_provenance_abort',error=abort,elapsed_seconds=time.perf_counter()-tick));continue
        remaining=deadline-time.perf_counter()-plan['cleanup_reserve_seconds']
        if remaining<=0:save(status,dict(record,status='unattempted_global_budget',elapsed_seconds=time.perf_counter()-tick));continue
        timeout=min(plan['per_fit_seconds'],remaining);save(path.parent/(c['id']+'-started.json'),dict(id=c['id'],plan_sha256=original,timeout_seconds=timeout,posterior_sha256=plan['posterior_sha256']))
        hp=path.parent/(c['id']+'-hardware.json');args=[plan['python'],str(Path(plan['study'])/'hardware_control.py'),'--cpus','0','--record',str(hp),'--timeout',str(timeout),'--',plan['python'],'-m','posterior_resource.resource_worker','--plan',str(path),'--cell',c['id']]
        try:
            with (path.parent/(c['id']+'.log')).open('x') as log:r=subprocess.run(args,cwd=plan['study'],env=dict(os.environ,PYTHONPATH=os.pathsep.join([plan['study'],plan['pythonpath']])),stdout=log,stderr=subprocess.STDOUT)
            record['returncode']=r.returncode;save(path.parent/(c['id']+'-exit.json'),dict(record))
            h=load(hp)
            from asof_rolling_execute import validate_hardware
            validate_hardware(h,args,r.returncode,timeout)
            if h['command']!=args[args.index('--')+1:] or h['returncode']!=r.returncode or h['job_active_processes_after_cleanup']!=0 or h['realized_cpus']!=[0] or not h['enforced_before_worker_launch'] or not h['containment']['assigned_before_worker_execution']:raise ValueError('Containment/affinity/exit evidence mismatch')
            if h['status'] not in ['completed','worker-failed','worker-timeout']:raise ValueError('Unknown hardware terminal status')
            if h['status']=='completed' and r.returncode!=0 or h['status']=='worker-failed' and r.returncode==0:raise ValueError('Hardware terminal status/exit mismatch')
            if h['status']=='worker-timeout':
                if r.returncode!=124 or h['elapsed_seconds']<timeout:raise ValueError('Invalid timeout evidence')
                record['status']='budgeted_timeout'
            else:
                rp=Path(c['out'])/'resource-result.json';result=load(rp);validate_outputs(plan,c,result);record.update(status=result['status'],resource_result_sha256=sha(rp),success=result['status']=='resource_completed' and r.returncode==0,resources=result.get('resources'))
            if verify_frozen(path,original)!=plan:raise ValueError('Postworker frozen plan drift')
        except Exception as exc:record.update(status='worker_or_validation_failed',error=str(exc));abort=str(exc) if 'drift' in str(exc).lower() or 'changed' in str(exc).lower() else None
        record['elapsed_seconds']=time.perf_counter()-tick;save(status,record)
    save(path.parent/'terminal.json',dict(expected=64,recorded=sum((path.parent/(c['id']+'-status.json')).exists() for c in plan['cells']),elapsed_seconds=time.perf_counter()-started,qualified=False,resource_only=True))



def prepare(out,study,fixture,python,package,attestation,streams,audit_path,pilot_path):
    # Explicit invocation only. Inputs include all192 audited streams; no generation/selection of seeds.
    study=Path(study).resolve();out=Path(out).resolve();python=Path(python).resolve();package=Path(package).resolve();sys.path.insert(0,str(study))
    from production_calibration_feasibility import audited_seeds,runtime_versions
    from continuation_comparison import attested_dependencies
    from masked_market_comparison_plan import dispersed_starts
    pilot=load(pilot_path);rows=load(streams);values=validate_streams(rows,pilot);audit=audited_seeds(audit_path,values)
    supplemental=audit.get('supplemental_evidence',{})
    if not supplemental or any(sha(p)!=h for p,h in supplemental.items()) or set(values)&set(audit.get('reserved_seeds',[])):raise ValueError('Supplemental audit/reserved streams differ')
    original=load(fixture)
    if len(original['data']['y'])!=1000 or any(len(r)!=4 for r in original['data']['y']) or len(original['holdout']['x'])!=1 or len(original['holdout']['x'][0])!=4:raise ValueError('Exact target shape required')
    own=Path(__file__).resolve().parent;inventory={str(p.resolve()):sha(p) for p in own.rglob('*.py')}
    bound={str(Path(p).resolve()):sha(p) for p in [*study.glob('*.py'),*own.rglob('*.py'),python,fixture,attestation,streams,audit_path,pilot_path,package/'owalnuts/__init__.py',package/'owalnuts/_owalnuts.pyd']}
    bound.update(attested_dependencies(attestation,python,package));bound.update(audit['inventory_files']);bound.update(supplemental)
    plan=dict(frozen=False,qualified=False,resource_only=True,phase='prospective_reference_bank',expected=64,warmup=1000,chains=4,retained=8000,checkpoints=[4000,8000],cpus=[0],per_fit_seconds=1800,total_seconds=21600,cleanup_reserve_seconds=15,memory_bytes=8*1024**3,
        python=str(python),pythonpath=str(package),study=str(study),runtime=runtime_versions(python),package_inventory=inventory,bindings=bound,worker_bindings={str(p.resolve()):sha(p) for p in [*study.glob('*.py'),python]},
        original_fixture=str(Path(fixture).resolve()),posterior_sha256=posterior(original),excluded_pilot_manifest=str(Path(pilot_path).resolve()),excluded_pilot_manifest_sha256=sha(pilot_path),streams=rows,bank_endpoints=ENDPOINTS,
        full_gate=dict(coordinates=1012,functionals=14,functional_names=list(FUNCTIONALS),forecasts=4,rhat=1.01,bulk_ess=400,tail_ess=400,retained_divergences=0,relative_mcse=.02),
        primary_endpoints=dict(functionals=list(PARAMETERS),forecast=dict(group=0,horizon=1,x_next=original['holdout']['x'][0][0]),probabilities=[.05,.95]),
        policy='64 independent fixed8k fits; all failures retained; common-grid/cache/bootstrap separate prospective analysis; no accuracy qualification from execution completion',cells=[])
    out.mkdir(parents=True,exist_ok=False);save(out/'intent.json',plan);(out/'fixtures').mkdir()
    for i,row in enumerate(rows):
        name=f'bank-{i:02d}-{row["backend"]}';f=copy.deepcopy(original);f['data']['initial_positions']=dispersed_starts(1000,4,original['data']['rho'],row['init_seed']);path=out/'fixtures'/f'{name}.json';save(path,f)
        plan['cells'].append(dict(row,id=name,out=str(out/name),fixture=str(path),fixture_sha256=sha(path)))
    plan['intent_sha256']=sha(out/'intent.json');save(out/'plan-draft.json',plan);return plan


def freeze(directory):
    directory=Path(directory).resolve();p=load(directory/'plan-draft.json')
    if p.get('frozen') is not False or sha(directory/'intent.json')!=p['intent_sha256'] or any(p.get(k)!=v for k,v in load(directory/'intent.json').items() if k!='cells'):raise ValueError('Intent changed')
    validate(p,directory);p['frozen']=True;save(directory/'plan.json',p)
    with (directory/'plan.sha256').open('x') as f:f.write(sha(directory/'plan.json'))
    return p


if __name__=='__main__':
    parser=argparse.ArgumentParser();sub=parser.add_subparsers(dest='action',required=True);prep=sub.add_parser('prepare')
    for key in ['out','study','fixture','python','package','attestation','streams','audit-path','pilot-path']:prep.add_argument('--'+key,required=True)
    for action in ['freeze','run']:sub.add_parser(action).add_argument('path')
    a=parser.parse_args()
    if a.action=='prepare':prepare(a.out,a.study,a.fixture,a.python,a.package,a.attestation,a.streams,a.audit_path,a.pilot_path)
    elif a.action=='freeze':freeze(a.path)
    else:execute(a.path)
