"""Prospective six-cell development flow comparison; draft plans do not execute."""
import argparse, hashlib, json, math, os, re, subprocess, time
from pathlib import Path
from continuation_comparison import sha, load, save, norm, attested_dependencies, validate_raw_starts
ROOT=Path(__file__).resolve().parent
TIERS=[1000,2000,4000,8000]
EXPECTED_BINARY='e1331c8dabb4d5f8c3915b0ea7f699d6a7d4b49d05ee8282237a35a122429ac5'
NAMES=['beta_bar','tau','mu_h','sigma_h','h_terminal','h_mean']+[s+str(g) for g in range(4) for s in ['alpha_','beta_']]

def sources():return {str(p.resolve()):sha(p) for p in ROOT.glob('*.py')}
def verify(path,plan,original):
    if sha(path)!=original or path.with_suffix('.sha256').read_text().strip()!=original:raise ValueError('Plan drift')
    if sources()!=plan['study_bindings'] or any(sha(k)!=v for k,v in plan['bound_files'].items()):raise ValueError('Source/binary drift')

def fixture_contract(fixture,periods):
    data=fixture['data'];y=data['y'];x=data['x'];future=fixture['holdout'];starts=data['initial_positions']
    if 'observation_mask' in data or 'observation_mask' in future:raise ValueError('Dense fixtures only')
    def finite(v):return not isinstance(v,bool) and isinstance(v,(int,float)) and math.isfinite(v)
    for values,length in [(y,periods),(x,periods),(future['y'],len(future['y'])),(future['x'],len(future['y']))]:
        if not length or len(values)!=length or any(len(row)!=4 or not all(map(finite,row)) for row in values):raise ValueError('Expected finite four-group panel')
    dimension=periods+12
    if len(starts)!=4 or any(len(row)!=dimension or not all(map(finite,row)) for row in starts):raise ValueError('Invalid canonical starts')
    if len({tuple(row) for row in starts})!=4:raise ValueError('Starts must be dispersed')
    return dict(periods=periods,dimension=dimension,forecast_rows=len(future['y'])*4,starts=starts,precision_names=NAMES)

def seed_history(root,seeds):
    # Bounded metadata search, never posterior arrays. Record exclusions honestly.
    hits=[];checked=0;excluded=[];pattern=re.compile(r'(?<![0-9])(?:'+ '|'.join(map(str,seeds))+r')(?![0-9])')
    for p in sorted(Path(root).rglob('*.json')):
        if 'raw' in p.name.lower() or p.stat().st_size>2000000:excluded.append(str(p));continue
        checked+=1
        raw=p.read_bytes();text=raw.decode('utf-16' if raw[:2] in [b'\xff\xfe',b'\xfe\xff'] else 'utf-8-sig')
        if pattern.search(text):hits.append(str(p))
    return dict(seeds=seeds,checked_metadata_files=checked,hits=hits,excluded_large_or_raw_files=excluded,scope='Bounded metadata exact numeric-token search; excludes posterior raw arrays')

def create(out,python,package,attestation,fixtures,history_root):
    package=Path(package).resolve();out=Path(out).resolve()
    if sha(package/'owalnuts/_owalnuts.pyd')!=EXPECTED_BINARY:raise ValueError('Wrong prospective release binary')
    bound={str(Path(p).resolve()):sha(p) for p in [python,package/'owalnuts/__init__.py',package/'owalnuts/_owalnuts.pyd',attestation]}
    bound.update(attested_dependencies(attestation,python,package))
    seeds=[100710001,100710002,100840001,100840002]
    audit=seed_history(history_root,seeds)
    if audit['hits']:raise ValueError('Historical seed collision: '+str(audit['hits']))
    plan=dict(frozen=False,phase='development',qualified=False,expected=6,python=str(Path(python).resolve()),pythonpath=str(package),bound_files=bound,study_bindings=sources(),attestation=str(Path(attestation).resolve()),cells=[],timeout_seconds=1800,seed_audit=audit,cache_policy='Existing disk caches retained; fresh processes. Both CFunc arms repeat runtime parity; compilation, parity, imports, every attempt, diagnostics and serialization charged.',policy='Same posterior and physical starts; different declared best execution policies. All six outcomes and failed costs retained; ratios only if both succeed. No historical timing comparison.',initialization_policy='Existing explicit canonical starts reused unchanged in all arms; no truth used to choose or alter starts.',tiers=TIERS,chains=4,warmup=1000,relative_mcse=.02,forecast_scope='Every finite observed holdout outcome',reference_target_accept=.9)
    orders=[['numpyro_continuation','owalnuts_continuation','restart'],['restart','owalnuts_continuation','numpyro_continuation']]
    for j,(fixture,periods) in enumerate(zip(fixtures,[128,1000])):
        fixture=Path(fixture).resolve();contract=fixture_contract(load(fixture),periods)
        for arm in orders[j]:plan['cells'].append(dict(id=f'T{periods}-{arm}',arm=arm,fixture=str(fixture),fixture_sha256=sha(fixture),seed=seeds[j],predictive_seed=seeds[j+2],**contract))
    out.mkdir(parents=True,exist_ok=False);save(out/'plan-draft.json',plan)
    return plan

def command(plan,cell,out):
    common=['--fixture',cell['fixture'],'--out',str(out),'--seed',str(cell['seed']),'--warmup','1000','--chains','4','--tiers',*map(str,TIERS)]
    worker={'restart':'pymc_flow_workflow.py','owalnuts_continuation':'pymc_flow_continuation_workflow.py','numpyro_continuation':'continuation_precision.py'}[cell['arm']]
    if cell['arm']=='numpyro_continuation':common+=['--model','flow','--batch-size','1000','--target-accept','0.9']
    else:
        common+=['--block-size','32','--expected-cpus','0']
        if cell['arm']=='restart':common+=['--precision-names',*NAMES]
        else:common+=['--model','flow']
    return [plan['python'],str(ROOT/'hardware_control.py'),'--cpus','0','--record',str(out.parent/(cell['id']+'-hardware.json')),'--timeout','1800','--',plan['python'],str(ROOT/worker),*common]

def fit_gate(fit,cell):
    e=fit['evaluation'];fs=e['functionals'];cs=e['canonical_parameter_diagnostics'];rows=e['forecast']['rows']
    if set(fs)!=set(NAMES) or len(cs)!=cell['dimension'] or len(rows)!=cell['forecast_rows']:raise ValueError('Gate scope mismatch')
    health=e['chain_count']==4 and fit['retained_divergences']==0 and all(math.isfinite(v[k]) and (v[k]<=1.01 if k=='rhat' else v[k]>=400) for v in [*fs.values(),*cs.values()] for k in ['rhat','bulk_ess','tail_ess'])
    intervals=[(v['interval_90'],v['endpoint_mcse']) for v in fs.values()]+[([v['lower'],v['upper']],v['endpoint_mcse']) for v in rows]
    precision=all(len(i)==len(m)==2 and all(math.isfinite(v) for v in [*i,*m]) and i[1]>i[0] and min(m)>=0 and max(m)/(i[1]-i[0])<=.02 for i,m in intervals)
    return fit.get('status')=='completed' and health and precision

def validate_worker(plan,cell,report):
    if report.get('seed')!=cell['seed']:raise ValueError('Seed mismatch')
    settings=report['settings']
    if settings['warmup']!=1000 or settings['chains']!=4:raise ValueError('Sampling configuration mismatch')
    if cell['arm']=='owalnuts_continuation':
        actual=norm(report['bindings']);expected=norm(plan['study_bindings'])
        expected.update({k:v for k,v in norm(plan['bound_files']).items() if Path(k).name in ['python.exe','__init__.py','_owalnuts.pyd']})
        expected[str(Path(cell['fixture']).resolve()).casefold()]=cell['fixture_sha256']
        if any(actual.get(k)!=v for k,v in expected.items()):raise ValueError('Continuation bindings mismatch')
        if report.get('initial_positions')!=cell['starts'] or report.get('predictive_seed')!=cell['predictive_seed']:raise ValueError('Continuation starts/predictive seed mismatch')
    else:
        if report.get('source_sha256')!={Path(k).name:v for k,v in plan['study_bindings'].items()} or report.get('fixture_sha256')!=cell['fixture_sha256']:raise ValueError('Source/fixture mismatch')
        if cell['arm']=='restart':
            for key,filename in [('extension_sha256','_owalnuts.pyd'),('adapter_source_sha256','__init__.py')]:
                expected=next(v for k,v in plan['bound_files'].items() if Path(k).name==filename)
                if report.get(key)!=expected:raise ValueError('Runtime package mismatch')
            expected_path=Path(plan['pythonpath'])/'owalnuts/_owalnuts.pyd'
            if Path(report['extension_path']).resolve()!=expected_path.resolve():raise ValueError('Runtime extension path mismatch')
        elif settings.get('target_accept')!=.9:raise ValueError('Reference acceptance mismatch')
    if cell['arm']!='numpyro_continuation':
        if settings.get('block_size')!=32 or report.get('model')!='flow' or report.get('parity',{}).get('passed') is not True:raise ValueError('Target/parity mismatch')
        if report['precision_plan']['names']!=NAMES:raise ValueError('Precision names mismatch')
    elif report.get('coordinates')!='noncentered':raise ValueError('Reference coordinates mismatch')
    if report.get('status')!='completed':return False
    attempts=report['attempts'];draws=[a['draws'] for a in attempts]
    if not draws or draws!=TIERS[:len(draws)] or any(a['screen']['pass'] for a in attempts[:-1]):raise ValueError('First-pass tier mismatch')
    for a in attempts:
        s=a['screen']
        if set(s['parameter_functionals'])!=set(NAMES) or s['forecast_rows']!=cell['forecast_rows'] or s['threshold']!=.02:raise ValueError('Precision scope mismatch')
    final=attempts[-1]['screen']['pass']
    if final!=report.get('precision_pass') or (not final and draws[-1]!=8000):raise ValueError('Early unsuccessful stop')
    if fit_gate(report,cell)!=final:raise ValueError('Stored gate inconsistent')
    return final

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
            if sha(cell['fixture'])!=cell['fixture_sha256']:
                abort='Fixture drift';raise ValueError(abort)
            env=dict(os.environ,PYTHONPATH=plan['pythonpath']);args=command(plan,cell,out);record.update(command=args,pythonpath=plan['pythonpath'])
            with (path.parent/(cell['id']+'.log')).open('x') as log:r=subprocess.run(args,env=env,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT)
            record['returncode']=r.returncode;save(path.parent/(cell['id']+'-exit.json'),dict(record))
            try:
                verify(path,plan,original)
                if sha(cell['fixture'])!=cell['fixture_sha256']:raise ValueError('Fixture drift')
            except Exception as exc:abort=str(exc);raise
            hp=path.parent/(cell['id']+'-hardware.json');hardware=load(hp);record.update(hardware_sha256=sha(hp),hardware_status=hardware['status'])
            if hardware.get('job_active_processes_after_cleanup')!=0 or hardware.get('realized_cpus')!=[0]:raise ValueError('Containment/affinity failure')
            if hardware['status']=='worker-timeout':
                if r.returncode!=124:raise ValueError('Timeout exit mismatch')
                record['status']='budgeted_computational_timeout'
            else:
                rp=out/('numpyro-continuation-report.json' if cell['arm']=='numpyro_continuation' else 'python-pymc-flow-report.json');report=load(rp);record['report_sha256']=sha(rp)
                passed=validate_worker(plan,cell,report)
                if report.get('status')=='completed':
                    for attempt in report['attempts']:
                        tier=attempt['draws'];fp=out/(f'draws-{tier}-report.json' if cell['arm']=='numpyro_continuation' else f'draws-{tier}/fit-report.json')
                        if fit_gate(load(fp),cell)!=attempt['screen']['pass']:raise ValueError('Per-tier gate mismatch')
                    n=report['attempts'][-1]['draws']
                    raw=out/'numpyro-continuation-raw.json' if cell['arm']=='numpyro_continuation' else out/f'draws-{n}/python-pymc-flow-raw.json'
                    validate_raw_starts(raw,cell['starts'])
                record.update(status='completed',success=passed and r.returncode==0 and hardware['status']=='completed')
        except Exception as exc:record.update(status='executor_or_validation_failed',error=str(exc))
        record['elapsed_seconds']=time.perf_counter()-start;save(status,record)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=['plan','run']);p.add_argument('--out');p.add_argument('--python');p.add_argument('--package');p.add_argument('--attestation');p.add_argument('--fixtures',nargs=2);p.add_argument('--history-root');p.add_argument('--plan');a=p.parse_args()
    if a.action=='plan':create(a.out,a.python,a.package,a.attestation,a.fixtures,a.history_root)
    else:execute(a.plan)
