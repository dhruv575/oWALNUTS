"""Nine-cell residual continuation development comparison. Plan does not run."""
import argparse,hashlib,json,math,os,subprocess,time
from pathlib import Path
ROOT=Path(__file__).resolve().parent
TIERS=[1000,2000,4000,8000]
ARMS=['restart','owalnuts_continuation','numpyro_continuation']
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def load(p):return json.loads(Path(p).read_text())
def save(p,v):
    with Path(p).open('x') as f:json.dump(v,f,indent=2,allow_nan=False)
def sources():return {str(p.resolve()):sha(p) for p in ROOT.glob('*.py')}
def norm(d):return {str(Path(k).resolve()).casefold():v for k,v in d.items()}
def verify(path,plan,original):
    if sha(path)!=original or path.with_suffix('.sha256').read_text().strip()!=original:raise ValueError('Plan drift')
    if sources()!=plan['study_bindings'] or any(sha(k)!=v for k,v in plan['bound_files'].items()):raise ValueError('Source/binary drift')
def command(plan,cell,out):
    common=['--fixture',cell['fixture'],'--out',str(out),'--seed',str(cell['seed']),'--warmup','1000','--chains','4','--tiers',*map(str,TIERS),'--coordinates','observation_residual']
    worker={'restart':'pymc_workflow.py','owalnuts_continuation':'pymc_continuation_workflow.py','numpyro_continuation':'continuation_precision.py'}[cell['arm']]
    if cell['arm']=='numpyro_continuation':common+=['--model','local_level','--batch-size','1000','--target-accept','0.9']
    return [plan['python'],str(ROOT/'hardware_control.py'),'--cpus','0','--record',str(out.parent/(cell['id']+'-hardware.json')),'--timeout','600','--',plan['python'],str(ROOT/worker),*common]
def attested_dependencies(attestation,python,package):
    a=load(attestation);manifest=load(a['manifest_path'])
    if a.get('status')!='attested' or manifest.get('status')!='attested' or sha(a['manifest_path'])!=a['manifest_sha256'] or manifest['source_before']!=manifest['source_after']:raise ValueError('Invalid build attestation')
    binary=sha(Path(package)/'owalnuts/_owalnuts.pyd')
    if binary!=a['installed_copy_sha256'] or binary!=manifest['binary']['sha256'] or sha(manifest['binary']['path'])!=binary:raise ValueError('Attested extension mismatch')
    if Path(a['python']['path']).resolve()!=Path(python).resolve() or sha(python)!=a['python']['sha256']:raise ValueError('Attested interpreter mismatch')
    adapter=Path(package)/'owalnuts/__init__.py';bindings=manifest['source_before']
    if norm(bindings).get(str(adapter.resolve()).casefold())!=sha(adapter):raise ValueError('Attested adapter mismatch')
    if any(sha(k)!=v for k,v in bindings.items()):raise ValueError('Attested source drift')
    return dict(bindings,**{a['manifest_path']:a['manifest_sha256'],manifest['binary']['path']:binary})

def create(out,python,package,attestation,fixture_root):
    out=Path(out).resolve();out.mkdir(parents=True,exist_ok=False);package=Path(package).resolve()
    bound={str(Path(p).resolve()):sha(p) for p in [python,package/'owalnuts/__init__.py',package/'owalnuts/_owalnuts.pyd',attestation]}
    bound.update(attested_dependencies(attestation,python,package))
    plan=dict(frozen=False,phase='development',qualified=False,python=str(Path(python).resolve()),pythonpath=str(package),bound_files=bound,study_bindings=sources(),attestation=str(Path(attestation).resolve()),cells=[],expected=9,timeout_seconds=600,policy='All nine attempted; provenance drift abort terminalizes remaining. Every failure cost retained. No successful ratio unless both pass.',cache_policy='Existing compiler caches retained; runtime parity,imports,compilation,allattempts charged',seed_audit='Pending historical exact-token review before freeze')
    for j,case in enumerate([0,3,5]):
        fixture=Path(fixture_root)/f'fixture-{case:02d}.json';data=load(fixture)['data'];starts=data['initial_positions']
        if len(starts)!=4 or any(len(q)!=130 or any(not math.isfinite(v) for v in q) for q in starts):raise ValueError('Invalid fourchain canonical starts')
        for arm in ARMS[j:]+ARMS[:j]:plan['cells'].append(dict(id=f'case{case:02d}-{arm}',case=case,arm=arm,fixture=str(fixture.resolve()),fixture_sha256=sha(fixture),seed=100510001+j,predictive_seed=100640001+j,starts=starts))
    save(out/'plan-draft.json',plan)
def validate_worker(plan,cell,report):
    if report.get('seed')!=cell['seed'] or report.get('coordinates')!='observation_residual':raise ValueError('Report identity mismatch')
    settings=report['settings']
    if settings['warmup']!=1000 or settings['chains']!=4:raise ValueError('Sampling configuration mismatch')
    if cell['arm']=='owalnuts_continuation':
        actual=norm(report['bindings']);expected=norm(plan['study_bindings'])
        expected.update({k:v for k,v in norm(plan['bound_files']).items() if Path(k).name in ['python.exe','__init__.py','_owalnuts.pyd']})
        # Attestation is an executor dependency, not a worker import.
        expected.pop(str(Path(plan['attestation']).resolve()).casefold(),None)
        expected[str(Path(cell['fixture']).resolve()).casefold()]=cell['fixture_sha256']
        if any(actual.get(k)!=v for k,v in expected.items()):raise ValueError('Continuation binding mismatch')
        if report.get('initial_positions')!=cell['starts']:raise ValueError('Continuation physical starts mismatch')
    else:
        if report.get('source_sha256')!={Path(k).name:v for k,v in plan['study_bindings'].items()} or report.get('fixture_sha256')!=cell['fixture_sha256']:raise ValueError('Legacy source/fixture mismatch')
        if cell['arm']=='restart':
            for key,filename in [('extension_sha256','_owalnuts.pyd'),('adapter_source_sha256','__init__.py')]:
                expected=next(v for k,v in plan['bound_files'].items() if Path(k).name==filename)
                if report.get(key)!=expected:raise ValueError('Runtime package mismatch')
        elif settings.get('target_accept')!=.9:raise ValueError('Reference acceptance mismatch')
    if report.get('status')!='completed':return False
    attempts=report['attempts'];draws=[a['draws'] for a in attempts]
    if not draws or draws!=TIERS[:len(draws)] or any(a['screen']['pass'] for a in attempts[:-1]):raise ValueError('First-pass tier mismatch')
    final=attempts[-1]['screen']['pass']
    if final!=report.get('precision_pass') or (not final and draws[-1]!=8000):raise ValueError('Failed fit stopped before cap')
    for a in attempts:
        screen=a['screen']
        if set(screen['parameter_functionals'])!={'h_initial','h_terminal','h_mean','sigma_obs','sigma_rw'} or screen['forecast_rows']!=1 or screen['threshold']!=.02:raise ValueError('Precision scope mismatch')
    e=report['evaluation'];diagnostics=list(e['functionals'].values())+list(e['canonical_parameter_diagnostics'].values())
    health=e['chain_count']==4 and len(e['canonical_parameter_diagnostics'])==130 and report['retained_divergences']==0 and all(math.isfinite(v[k]) and (v[k]<=1.01 if k=='rhat' else v[k]>=400) for v in diagnostics for k in ['rhat','bulk_ess','tail_ess'])
    ratios=[max(v['endpoint_mcse'])/(v['interval_90'][1]-v['interval_90'][0]) for v in e['functionals'].values()]
    ratios.extend(max(v['endpoint_mcse'])/(v['upper']-v['lower']) for v in e['forecast']['rows'])
    passed=health and all(math.isfinite(v) and 0<=v<=.02 for v in ratios)
    if passed!=final:raise ValueError('Stored gate inconsistent with diagnostics')
    return passed

def fit_gate(fit):
    e=fit['evaluation'];ds=list(e['functionals'].values())+list(e['canonical_parameter_diagnostics'].values())
    health=e['chain_count']==4 and len(e['canonical_parameter_diagnostics'])==130 and fit['retained_divergences']==0 and all(math.isfinite(v[k]) and (v[k]<=1.01 if k=='rhat' else v[k]>=400) for v in ds for k in ['rhat','bulk_ess','tail_ess'])
    ratios=[max(v['endpoint_mcse'])/(v['interval_90'][1]-v['interval_90'][0]) for v in e['functionals'].values()]
    ratios.extend(max(v['endpoint_mcse'])/(v['upper']-v['lower']) for v in e['forecast']['rows'])
    return health and len(e['forecast']['rows'])==1 and set(e['functionals'])=={'h_initial','h_terminal','h_mean','sigma_obs','sigma_rw'} and all(math.isfinite(v) and 0<=v<=.02 for v in ratios)

def validate_raw_starts(path,expected):
    path=Path(path)
    with path.open('rb') as f:f.seek(max(0,path.stat().st_size-1000000));tail=f.read().decode()
    token='"initial_positions":';i=tail.rfind(token)
    if i<0:raise ValueError('Raw start matrix missing')
    actual=json.JSONDecoder().raw_decode(tail[i+len(token):].lstrip())[0]
    if len(actual)!=len(expected) or any(len(a)!=len(b) for a,b in zip(actual,expected)):raise ValueError('Raw start shape mismatch')
    if max(abs(x-y) for a,b in zip(actual,expected) for x,y in zip(a,b))>1e-12:raise ValueError('Raw physical starts mismatch')

def execute(path):
    path=Path(path).resolve();plan=load(path);original=sha(path)
    if not plan.get('frozen'):raise ValueError('Freeze reviewed plan before run')
    verify(path,plan,original);abort=None
    for cell in plan['cells']:
        out=path.parent/cell['id'];status=path.parent/(cell['id']+'-status.json');marker=path.parent/(cell['id']+'-started.json')
        if out.exists() or status.exists() or marker.exists():raise ValueError('Already attempted cell')
        if abort:save(status,dict(id=cell['id'],status='unattempted_provenance_abort',reason=abort,success=False,elapsed_seconds=0));continue
        save(marker,dict(id=cell['id'],plan_sha256=original));start=time.perf_counter();record=dict(id=cell['id'],success=False,returncode=None)
        try:
            try:verify(path,plan,original)
            except Exception as exc:abort=str(exc);raise
            if sha(cell['fixture'])!=cell['fixture_sha256']:raise ValueError('Fixture drift')
            env=dict(os.environ,PYTHONPATH=plan['pythonpath']);args=command(plan,cell,out);record.update(command=args,pythonpath=plan['pythonpath'])
            with (path.parent/(cell['id']+'.log')).open('x') as log:r=subprocess.run(args,env=env,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT)
            record['returncode']=r.returncode;save(path.parent/(cell['id']+'-exit.json'),dict(record))
            try:
                verify(path,plan,original)
                if sha(cell['fixture'])!=cell['fixture_sha256']:raise ValueError('Fixture drift')
            except Exception as exc:abort=str(exc);raise
            hp=path.parent/(cell['id']+'-hardware.json');hardware=load(hp);record.update(hardware_sha256=sha(hp),hardware_status=hardware['status'])
            if hardware.get('job_active_processes_after_cleanup')!=0 or hardware.get('realized_cpus')!=[0]:raise ValueError('Containment/affinity failure')
            if hardware['status']=='worker-timeout':record['status']='budgeted_computational_timeout'
            else:
                rp=out/('numpyro-continuation-report.json' if cell['arm']=='numpyro_continuation' else 'python-pymc-report.json');report=load(rp);record['report_sha256']=sha(rp)
                passed=validate_worker(plan,cell,report)
                if report.get('status')=='completed':
                    for attempt in report['attempts']:
                        tier=attempt['draws'];fp=out/(f'draws-{tier}-report.json' if cell['arm']=='numpyro_continuation' else f'draws-{tier}/fit-report.json')
                        if fit_gate(load(fp))!=attempt['screen']['pass']:raise ValueError('Per-tier gate mismatch')
                    n=report['attempts'][-1]['draws']
                    raw=out/'numpyro-continuation-raw.json' if cell['arm']=='numpyro_continuation' else out/f'draws-{n}/python-pymc-raw.json'
                    validate_raw_starts(raw,cell['starts'])
                record.update(status='completed',success=passed and r.returncode==0 and hardware['status']=='completed')
        except Exception as exc:record.update(status='executor_or_validation_failed',error=str(exc))
        record['elapsed_seconds']=time.perf_counter()-start;save(status,record)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=['plan','run']);p.add_argument('--out');p.add_argument('--python');p.add_argument('--package');p.add_argument('--attestation');p.add_argument('--fixture-root');p.add_argument('--plan');a=p.parse_args()
    if a.action=='plan':create(a.out,a.python,a.package,a.attestation,a.fixture_root)
    else:execute(a.plan)
