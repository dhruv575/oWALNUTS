"""Four-fit T1000 resource pilot; explicit prepare/freeze/run, no import-time work."""
import argparse,copy,hashlib,json,os,subprocess,sys,time
from pathlib import Path
HERE=Path(__file__).resolve().parent


def sha(path):
    h=hashlib.sha256()
    with open(path,'rb') as f:
        for c in iter(lambda:f.read(1024*1024),b''):h.update(c)
    return h.hexdigest()

def save(path,value):
    with Path(path).open('x') as f:json.dump(value,f,indent=2,allow_nan=False)

def load(path):return json.loads(Path(path).read_text())
def digest(value):return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()

def posterior(fixture):
    data={k:v for k,v in fixture['data'].items() if k!='initial_positions'}
    return digest(dict(data=data,predictive_inputs={'x':fixture['holdout']['x']},forecast='one-step observed StudentT, all4group forecast stopping, primarygroup0 existingx'))


def validate_streams(rows):
    if len(rows)!=4 or [r['backend'] for r in rows]!=['public','reference','reference','public']:raise ValueError('Four fixed balanced-order fits required')
    seeds=[r[k] for r in rows for k in ['init_seed','seed','predictive_seed']]
    if len(set(seeds))!=12 or any(type(v) is not int or not 0<=v<2**32 for v in seeds) or any(r['predictive_seed']!=r['seed']+130000 for r in rows):raise ValueError('Twelve independent distinct uint32streams required')
    return seeds


def prepare(out,study,fixture_path,python,package,attestation,streams_path,seed_audit):
    study=Path(study).resolve();sys.path.insert(0,str(study))
    from continuation_comparison import attested_dependencies
    from masked_market_comparison_plan import dispersed_starts
    from asof_rolling_protocol import runtime_versions
    from production_calibration_feasibility import audited_seeds
    rows=load(streams_path);seeds=validate_streams(rows);audit=audited_seeds(seed_audit,seeds)
    supplemental=audit.get('supplemental_evidence',{})
    if not supplemental or set(seeds)&set(audit.get('reserved_seeds',[])) or not set(range(1970000000,1970003612)).issubset(set(audit.get('reserved_seeds',[]))):raise ValueError('Supplemental audit/reserved streams missing or colliding')
    if any(sha(p)!=h for p,h in supplemental.items()):raise ValueError('Supplemental seed evidence changed')
    fixture=load(fixture_path);data=fixture['data']
    if len(data['y'])!=1000 or any(len(v)!=4 for v in data['y']) or len(fixture['holdout']['x'])!=1 or len(fixture['holdout']['x'][0])!=4:raise ValueError('Exact T1000G4one-step target required')
    python=Path(python).resolve();package=Path(package).resolve();out=Path(out).resolve()
    bind={str(p.resolve()):sha(p) for p in [*study.glob('*.py'),*HERE.rglob('*.py'),python,Path(fixture_path),Path(attestation),Path(streams_path),Path(seed_audit),package/'owalnuts/__init__.py',package/'owalnuts/_owalnuts.pyd']}
    bind.update(attested_dependencies(attestation,python,package));bind.update(audit['inventory_files']);bind.update(supplemental)
    plan=dict(frozen=False,qualified=False,resource_only=True,expected=4,study=str(study),python=str(python),pythonpath=str(package),bindings=bind,
        package_inventory={str(p.resolve()):sha(p) for p in HERE.rglob('*.py')},worker_bindings={str(p.resolve()):sha(p) for p in [*study.glob('*.py'),python]},runtime=runtime_versions(python),posterior_sha256=posterior(fixture),
        original_fixture=str(Path(fixture_path).resolve()),original_fixture_sha256=sha(fixture_path),streams=rows,
        per_fit_seconds=1800,total_seconds=7200,cleanup_reserve_seconds=15,memory_bytes=8*1024**3,cpus=[0],warmup=1000,chains=4,retained=8000,checkpoints=[4000,8000],
        primary_endpoints={'functionals':['beta_bar','tau','mu_h','sigma_h','h_terminal'],'forecast':{'group':0,'horizon':1,'x_next':fixture['holdout']['x'][0][0]},'probabilities':[.05,.95]},
        full_gate=dict(coordinates=1012,functionals=14,functional_names=['beta_bar','tau','mu_h','sigma_h','h_terminal','h_mean']+[p+str(g) for g in range(4) for p in ['alpha_','beta_']],forecasts=4,rhat=1.01,bulk_ess=400,tail_ess=400,retained_divergences=0,relative_mcse=.02),
        interpretation='Two independent fits/backend: resource feasibility only, not a bank/accuracy/uncertainty qualification.4k/8k prefixes dependent withinfit. Allfour intended outcomes retained.',
        timing='Contained fit cap includes actualworker and extraction/CDF/diagnostics; totalcap includes verification and wrapper overhead with15second cleanupreserve; terminal bookkeeping overruns measured.',
        cache='Freshprocess perfit; retained disk caches; no overlapping measured jobs',cells=[])
    out.mkdir(parents=True,exist_ok=False);save(out/'intent.json',plan);(out/'fixtures').mkdir()
    for i,row in enumerate(rows):
        f=copy.deepcopy(fixture);f['data']['initial_positions']=dispersed_starts(1000,4,data['rho'],row['init_seed'])
        path=out/'fixtures'/f'fit-{i}.json';save(path,f)
        if posterior(f)!=plan['posterior_sha256']:raise ValueError('Initialization changed posterior')
        plan['cells'].append(dict(row,id=f'fit-{i}-{row["backend"]}',fixture=str(path),fixture_sha256=sha(path),out=str(out/f'fit-{i}-{row["backend"]}')))
    plan['intent_sha256']=sha(out/'intent.json');save(out/'plan-draft.json',plan);return plan


def validate(plan,directory):
    if plan['warmup']!=1000 or plan['chains']!=4 or plan['cpus']!=[0] or plan.get('resource_only') is not True or plan['expected']!=4 or len(plan['cells'])!=4 or plan['retained']!=8000 or plan['checkpoints']!=[4000,8000] or plan['per_fit_seconds']!=1800 or plan['total_seconds']!=7200 or plan['cleanup_reserve_seconds']!=15 or plan['memory_bytes']!=8*1024**3:raise ValueError('Resource policy drift')
    if plan['primary_endpoints']['functionals']!=['beta_bar','tau','mu_h','sigma_h','h_terminal'] or plan['primary_endpoints']['probabilities']!=[.05,.95]:raise ValueError('Primary family drift')
    validate_streams(plan['streams'])
    if {str(p.resolve()):sha(p) for p in HERE.rglob('*.py')}!=plan['package_inventory']:raise ValueError('Resource package inventory drift')
    if any(sha(p)!=v for p,v in plan['bindings'].items()):raise ValueError('Source/runtime drift')
    sys.path.insert(0,plan['study']);from masked_market_comparison_plan import dispersed_starts
    from production_calibration_feasibility import runtime_versions
    if runtime_versions(plan['python'])!=plan['runtime']:raise ValueError('Package version drift')
    if {str(p.resolve()) for p in Path(plan['study']).glob('*.py')}!={p for p in plan['worker_bindings'] if p.endswith('.py')}:raise ValueError('Study source inventory drift')
    original=load(plan['original_fixture'])
    names=['beta_bar','tau','mu_h','sigma_h','h_terminal','h_mean']+[p+str(g) for g in range(4) for p in ['alpha_','beta_']]
    expected_gate=dict(coordinates=1012,functionals=14,functional_names=names,forecasts=4,rhat=1.01,bulk_ess=400,tail_ess=400,retained_divergences=0,relative_mcse=.02)
    if plan['full_gate']!=expected_gate or plan['primary_endpoints']['forecast']!=dict(group=0,horizon=1,x_next=original['holdout']['x'][0][0]):raise ValueError('Exact diagnostic/forecast recipe drift')
    for i,(c,row) in enumerate(zip(plan['cells'],plan['streams'])):
        expected_id=f'fit-{i}-{row["backend"]}'
        if c['id']!=expected_id or c['out']!=str(directory/expected_id) or c['fixture']!=str(directory/'fixtures'/f'fit-{i}.json') or any(c[k]!=v for k,v in row.items()):raise ValueError('Cell identity/path drift')
        f=load(c['fixture']);expected=copy.deepcopy(original);expected['data']['initial_positions']=dispersed_starts(1000,4,f['data']['rho'],row['init_seed'])
        if sha(c['fixture'])!=c['fixture_sha256'] or f!=expected or posterior(f)!=plan['posterior_sha256']:raise ValueError('Fixture/start/posterior drift')


def freeze(directory):
    directory=Path(directory).resolve();p=load(directory/'plan-draft.json');intent=load(directory/'intent.json')
    if p.get('frozen') is not False or sha(directory/'intent.json')!=p['intent_sha256'] or any(p.get(k)!=v for k,v in intent.items() if k!='cells'):raise ValueError('Draft intent changed')
    validate(p,directory);p['frozen']=True;save(directory/'plan.json',p)
    with (directory/'plan.sha256').open('x') as f:f.write(sha(directory/'plan.json'))
    return p


def execute(path):
    path=Path(path).resolve();plan=load(path);original=sha(path);started=time.perf_counter();deadline=started+plan['total_seconds'];abort=None
    if plan.get('frozen') is not True:raise ValueError('Explicit frozen plan required')
    if (path.parent/'terminal.json').exists():raise ValueError('Existing terminal record; no overwrite')
    if plan.get('expected')!=4 or len(plan.get('cells',[]))!=4 or len({c['id'] for c in plan['cells']})!=4:raise ValueError('Four-cell intent required')
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
    save(path.parent/'terminal.json',dict(expected=4,recorded=sum((path.parent/(c['id']+'-status.json')).exists() for c in plan['cells']),elapsed_seconds=time.perf_counter()-started,qualified=False,resource_only=True))


def verify_frozen(path,original=None):
    path=Path(path).resolve();actual=sha(path)
    if original is not None and actual!=original:raise ValueError('Frozen plan digest changed')
    plan=load(path)
    if plan.get('frozen') is not True or path.with_suffix('.sha256').read_text().strip()!=actual:raise ValueError('Frozen plan sidecar mismatch')
    if sha(path.parent/'intent.json')!=plan['intent_sha256']:raise ValueError('Frozen intent changed')
    intent=load(path.parent/'intent.json')
    if any(plan.get(k)!=v for k,v in intent.items() if k not in ['cells','frozen']):raise ValueError('Frozen plan/intent mismatch')
    validate(plan,path.parent);return plan


def validate_outputs(plan,cell,result):
    import math
    if result.get('status') not in ['resource_completed','failed']:raise ValueError('Unknown resource result status')
    if result.get('cell_id')!=cell['id'] or result.get('backend')!=cell['backend'] or result.get('posterior_sha256')!=plan['posterior_sha256'] or result.get('qualified') is not False or result.get('memory_cap_bytes')!=plan['memory_bytes']:raise ValueError('Resource output identity/config mismatch')
    for key in ['process_cpu_seconds_before_final_report','worker_seconds_before_final_report']:
        v=result.get(key)
        if type(v) not in (int,float) or not math.isfinite(v) or v<0:raise ValueError('Invalid measured resource timing')
    resources=result.get('resources',{})
    if not resources.get('measurement'):raise ValueError('Missing resource measurement scope')
    for key in ['peak_committed_bytes','peak_resident_bytes']:
        value=resources.get(key)
        if value is not None and (type(value) is not int or value<0):raise ValueError('Invalid measured peak memory')
    if all(resources.get(k) is None for k in ['peak_committed_bytes','peak_resident_bytes']):raise ValueError('No measured memory peak')
    if result['status']=='resource_completed':
        if result.get('accuracy_qualified') is not False or result.get('reference_bank_resolved') is not False or result.get('resource_only') is not True:raise ValueError('Resource pilot overclaims accuracy')
        extraction=result['extraction'];root=Path(cell['out'])/'extracted'
        if extraction['shape']!=[4,8000,1012] or extraction['predictive_contract']['x_next']!=plan['primary_endpoints']['forecast']['x_next']:raise ValueError('Extracted target/predictor mismatch')
        for name,key in [('canonical.npy','canonical_sha256'),('compact.npz','compact_sha256')]:
            if sha(root/name)!=extraction[key]:raise ValueError('Extracted artifact hash mismatch')
        if [v['draws'] for v in result['checkpoints']]!=[4000,8000]:raise ValueError('Missing4k/8kresource checkpoints')
        for row in result['checkpoints']:
            checkpoint=Path(cell['out'])/f"checkpoint-{row['draws']}.json"
            cdf_path=Path(cell['out'])/f"predictive-cdf-{row['draws']}.json"
            if sha(checkpoint)!=row['checkpoint_sha256'] or sha(cdf_path)!=row['predictive_cdf_sha256']:raise ValueError('Checkpoint artifact binding differs')
            saved=load(checkpoint)
            from pymc_flow_continuation_workflow import strict_screen
            diagnostics=[*saved['evaluation']['canonical_parameter_diagnostics'].values(),*saved['evaluation']['functionals'].values()]
            healthy=all(all(type(d[k]) in (int,float) and math.isfinite(d[k]) for k in ['rhat','bulk_ess','tail_ess']) and 0<d['rhat']<=1.01 and min(d['bulk_ess'],d['tail_ess'])>=400 for d in diagnostics) and saved['retained_divergences']==0
            if len(saved['evaluation']['canonical_parameter_diagnostics'])!=1012 or saved['healthy']!=healthy:raise ValueError('Checkpoint health scope/result differs')
            screen=strict_screen(saved,.02,plan['full_gate']['functional_names'],4)
            if saved['draws']!=row['draws'] or screen!=saved['screen'] or screen['pass']!=row['full_gate_pass'] or load(cdf_path)!=row['predictive_cdf']:raise ValueError('Checkpoint precision/CDF mismatch')
            if type(row['full_gate_pass']) is not bool:raise ValueError('Invalid actual health gate')
            for key in ['diagnostic_seconds','predictive_cdf_seconds']:
                if type(row[key]) not in (int,float) or not math.isfinite(row[key]) or row[key]<0:raise ValueError('Invalid checkpoint cost')
            cdf=row['predictive_cdf']
            if cdf['orders']!=[16,32,64,128] or cdf['probabilities']!=[.05,.95] or cdf['metadata']['x_next']!=plan['primary_endpoints']['forecast']['x_next']:raise ValueError('Predictive CDF policy differs')

if __name__=='__main__':
    p=argparse.ArgumentParser();sub=p.add_subparsers(dest='action',required=True)
    prep=sub.add_parser('prepare')
    for key in ['out','study','fixture','python','package','attestation','streams','seed-audit']:prep.add_argument('--'+key,required=True)
    for action in ['freeze','run']:sub.add_parser(action).add_argument('path')
    a=p.parse_args()
    if a.action=='prepare':prepare(a.out,a.study,a.fixture,a.python,a.package,a.attestation,a.streams,a.seed_audit)
    elif a.action=='freeze':freeze(a.path)
    else:execute(a.path)
