"""Draft four-process/twelve-fit persistent development comparison controller.

No seed generation. Prepare/freeze/execute are separate explicit Python APIs.
"""
import json,os,subprocess,time,re,math
from pathlib import Path
from continuation_comparison import sha,load,save,attested_dependencies
from mixed_flow_comparison import runtime,sources
HERE=Path(__file__).resolve().parent
TIERS=[1000,2000,4000,8000]
INIT_POLICY='Two freshly audited initialization streams create fixed fixture starts, reused across paired arms and A repeats; no posterior carryover.'


def reviewed_seeds(rows,audit_path,initialization_seeds=()):
    if len(rows)!=2 or any(len(r)!=3 for r in rows):raise ValueError('Two reviewed three-seed sets required')
    values=[s for row in rows for s in row];values += [s+130000 for s in values];values += list(initialization_seeds)
    if any(type(s)!=int or not 0<=s<2**32 for s in values) or len(set(values))!=12+len(initialization_seeds):raise ValueError('Distinct sampler/prediction streams required')
    audit=load(audit_path)
    if audit.get('status')!='passed' or sorted(audit.get('seeds',[]))!=sorted(values) or audit.get('hits')!=[] or not audit.get('scope') or not audit.get('auditor') or not audit.get('inventory_files'):raise ValueError('Reviewed bounded seed audit required')
    pattern=re.compile(r'(?<!\d)(?:'+'|'.join(map(str,values))+r')(?!\d)')
    for p,h in audit['inventory_files'].items():
        if sha(p)!=h or pattern.search(Path(p).read_text(encoding='utf-8-sig')):raise ValueError('Historical seed binding/collision')
    for p,h in audit.get('supplemental_evidence',{}).items():
        if sha(p)!=h:raise ValueError('Supplemental seed evidence changed')
    return audit


def fixture_contract(path,origin):
    f=load(path);d=f['data'];h=f['holdout'];p=f['provenance']
    def matrix(value,n,m,predicate):
        return isinstance(value,list) and len(value)==n and all(isinstance(row,list) and len(row)==m and all(predicate(v) for v in row) for row in value)
    finite=lambda v:type(v) in (int,float) and math.isfinite(v)
    boolean=lambda v:type(v) is bool
    if type(p['init_seed']) is not int or not 0<=p['init_seed']<2**32:raise ValueError('Invalid archived initialization seed')
    if type(p['origin_index']) is not int or p['origin_index']!=origin or d['grid_index']!=list(range(128)) or h['grid_index']!=[128]:raise ValueError('Fixed rolling timeline mismatch')
    if not all(matrix(d.get(k),128,4,boolean if k=='observation_mask' else finite) for k in ['x','y','observation_mask']):raise ValueError('Complete finite regular training grid required')
    if not matrix(h.get('x'),1,4,finite) or not matrix(h.get('x_available'),1,4,boolean) or not matrix(h.get('observation_mask'),1,4,boolean) or h['y']!=[[None]*4] or h['observation_mask']!=[[False]*4]:raise ValueError('Strict future shape/mask/absent-label contract required')
    if not finite(d.get('rho')) or abs(d['rho'])>=1 or not finite(d.get('nu')) or d['nu']!=5:raise ValueError('Model constants invalid')
    starts=d['initial_positions']
    if not matrix(starts,4,140,finite):raise ValueError('Four finite canonical starts required')
    cells=[[1,g] for g,v in enumerate(h['x_available'][0]) if v]
    if not cells or f['precision_family']!=cells:raise ValueError('Exact known-anchor forecast family required')
    return dict(path=str(Path(path).resolve()),sha256=sha(path),origin=origin,init_seed=p['init_seed'],starts=starts,forecast_cells=cells,observed_count=sum(map(sum,d['observation_mask'])))


def command(plan,cohort,out):
    worker=[plan['python'],str(HERE/'persistent_comparison_plan.py'),'--worker-plan',str(Path(out).parent/'plan.json'),'--cohort',cohort['id'],'--worker-out',str(out)]
    return [plan['python'],str(HERE/'hardware_control.py'),'--cpus','0','--record',str(Path(out).parent/(cohort['id']+'-hardware.json')),'--timeout','1800','--',*worker]


def prepare(out,python,package,attestation,panel,anchors,protocol,fixtures,seed_rows,seed_audit,archive_directory):
    if len(fixtures)!=2:raise ValueError('Explicit existing A168/B216 fixtures required')
    contracts=[fixture_contract(p,o) for p,o in zip(fixtures,[168,216])]
    audit=reviewed_seeds(seed_rows,seed_audit,[c['init_seed'] for c in contracts])
    if contracts[0]['observed_count']==contracts[1]['observed_count']:raise ValueError('A/B observed counts must differ')
    # Rebuild transport from the bound derived panel, without touching labels
    # in its issued forecasts. No posterior or outcome-based origin selection.
    from asof_market_fixture import prepare as origin_fixture,attach_archived_anchors
    derived=load(anchors);original=load(panel);rules=load(protocol)
    if derived!=attach_archived_anchors(original,archive_directory):raise ValueError('Derived anchor panel differs from archived trade reconstruction')
    for item in contracts:
        fixture=load(item['path']);expected=origin_fixture(derived,rules,origin_index=item['origin'],window=128,init_seed=fixture['provenance']['init_seed'])
        if fixture!=expected:raise ValueError('Fixture differs from bound as-of replay')
    python=Path(python).resolve();package=Path(package).resolve();out=Path(out).resolve()
    bound={str(Path(p).resolve()):sha(p) for p in [python,package/'owalnuts/__init__.py',package/'owalnuts/_owalnuts.pyd',attestation,panel,anchors,protocol,seed_audit,*fixtures]};bound.update(attested_dependencies(attestation,python,package));bound.update(audit['inventory_files']);bound.update(audit.get('supplemental_evidence',{}))
    bound.update({str((Path(archive_directory)/name).resolve()):digest for name,digest in original['acquisition_binding']['trade_files'].items()})
    plan=dict(initialization_policy=INIT_POLICY,panel=str(Path(panel).resolve()),anchors=str(Path(anchors).resolve()),protocol=str(Path(protocol).resolve()),archive_directory=str(Path(archive_directory).resolve()),seed_audit_path=str(Path(seed_audit).resolve()),frozen=False,qualified=False,expected_processes=4,expected_fits=12,python=str(python),pythonpath=str(package),bound_files=bound,study_bindings=sources(),runtime=runtime(python),fixtures=contracts,seed_rows=seed_rows,seed_audit=audit,chains=4,warmup=1000,tiers=TIERS,batch=1000,relative_mcse=.02,reference_target_accept=.9,timeout_seconds=1800,cohorts=[],policy='Fresh adaptation each posterior; immutable A/B/A, process/cache reuse only. Candidate target compiles anew each fit. No posterior carryover or historical timing ratios.')
    for pair,order in enumerate([['pymc','numpyro'],['numpyro','pymc']]):
        for backend in order:
            c=dict(id=f'pair{pair}-{backend}',backend=backend,seeds=seed_rows[pair],fixture_indices=[0,1,0],fit_ids=[f'pair{pair}-{backend}-fit{i}' for i in range(3)])
            c['command']=command(plan,c,out/c['id']);plan['cohorts'].append(c)
    out.mkdir(parents=True,exist_ok=False);save(out/'plan-draft.json',plan);return plan


def fit_gate(report,fixture,seed,enforce_cap=True):
    import math
    from masked_market_comparison_plan import NAMES
    if report.get('status') not in ('completed','failed'):raise ValueError('Malformed fit status')
    if report.get('status')!='completed':return False
    if report['seed']!=seed or report['predictive_seed']!=seed+130000 or report['fixture_sha256']!=fixture['sha256'] or report['initial_positions']!=fixture['starts'] or report.get('fresh_adaptation') is not True or report.get('posterior_continuation') is not False:raise ValueError('Fit identity/start/reset mismatch')
    e=report['evaluation'];fs=e['functionals'];qs=e['canonical_parameter_diagnostics'];rows=e['forecast']['rows']
    if set(fs)!=set(NAMES) or set(qs)!={f'q_{i}' for i in range(140)} or e['chain_count']!=4:raise ValueError('Full diagnostic family required')
    available=[r for r in rows if r['forecast_available']]
    if len(rows)!=4 or {(r['horizon'],r['group']) for r in rows}!={(1,g) for g in range(4)} or {(r['horizon'],r['group']) for r in available}!={tuple(c) for c in fixture['forecast_cells']} or any(r['target_observed'] or r['observed'] is not None for r in rows):raise ValueError('Forecast family/label drift')
    def healthy(d):return all(math.isfinite(d[k]) for k in ['rhat','bulk_ess','tail_ess']) and 0<d['rhat']<=1.01 and min(d['bulk_ess'],d['tail_ess'])>=400
    def precise(bounds,errors):return len(bounds)==len(errors)==2 and all(math.isfinite(v) for v in bounds+errors) and bounds[1]>bounds[0] and min(errors)>=0 and max(errors)/(bounds[1]-bounds[0])<=.02
    passed=report['retained_divergences']==0 and all(healthy(d) for d in [*fs.values(),*qs.values()]) and all(precise(d['interval_90'],d['endpoint_mcse']) for d in fs.values()) and all(precise([r['lower'],r['upper']],r['endpoint_mcse']) for r in available)
    counts=[a['draws'] for a in report['attempts']]
    if not counts or counts!=TIERS[:len(counts)] or any(a['screen']['pass'] for a in report['attempts'][:-1]) or (enforce_cap and not passed and counts[-1]!=8000) or report['precision_pass']!=passed:raise ValueError('First-pass/cap mismatch')
    return passed


def validate_plan(plan,directory):
    from asof_market_fixture import attach_archived_anchors,prepare as origin_fixture
    directory=Path(directory).resolve()
    if any(plan.get(k)!=v for k,v in dict(expected_processes=4,expected_fits=12,chains=4,warmup=1000,tiers=TIERS,batch=1000,relative_mcse=.02,reference_target_accept=.9,timeout_seconds=1800).items()):raise ValueError('Fixed persistent recipe changed')
    if plan.get('initialization_policy')!=INIT_POLICY or len(plan['fixtures'])!=2:raise ValueError('Exactly two deterministic archived initialization fixtures required')
    reviewed_seeds(plan['seed_rows'],plan['seed_audit_path'],[c['init_seed'] for c in plan['fixtures']])
    original=load(plan['panel']);derived=load(plan['anchors'])
    if derived!=attach_archived_anchors(original,plan['archive_directory']):raise ValueError('Anchor archive reconstruction mismatch')
    for item,origin in zip(plan['fixtures'],[168,216]):
        if item['origin']!=origin:raise ValueError('Fixed earliest eligible origins changed')
        f=load(item['path'])
        if f['provenance']['init_seed']!=item['init_seed']:raise ValueError('Initialization stream changed')
        expected=origin_fixture(derived,load(plan['protocol']),origin_index=origin,window=128,init_seed=f['provenance']['init_seed'])
        if f!=expected:raise ValueError('Initialization/as-of fixture changed')
    if len(plan['fixtures'])!=2:raise ValueError('A/B fixture family changed')
    expected=[]
    for pair,order in enumerate([['pymc','numpyro'],['numpyro','pymc']]):
        for backend in order:
            c=dict(id=f'pair{pair}-{backend}',backend=backend,seeds=plan['seed_rows'][pair],fixture_indices=[0,1,0],fit_ids=[f'pair{pair}-{backend}-fit{i}' for i in range(3)])
            c['command']=command(plan,c,directory/c['id']);expected.append(c)
    if plan['cohorts']!=expected:raise ValueError('Exact cohort/order/seed/command contract changed')


def validate_fit(report,fixture,seed,backend,directory):
    passed=fit_gate(report,fixture,seed)
    validate_transport_proofs(report,fixture,seed,backend,directory)
    return passed


def validate_transport_proofs(report,fixture,seed,backend,directory):
    """Transport/reset proof only; NEVER grants production cap eligibility."""
    from continuation_comparison import validate_raw_starts
    from masked_market_comparison_execute import tail_field
    passed=fit_gate(report,fixture,seed,enforce_cap=False)
    if report.get('status')!='completed':return False
    if report['backend']!=backend:raise ValueError('Backend mismatch')
    import math
    data=load(fixture['path'])['data'];expected=[]
    for q in fixture['starts']:
        u=list(q);mu=q[2];sigma=math.exp(q[3]);rho=data['rho'];u[12]=(q[12]-mu)*math.sqrt(1-rho*rho)/sigma
        for j in range(13,140):u[j]=(q[j]-mu-rho*(q[j-1]-mu))/sigma
        expected.append(u)
    actual=report['sampling_initial_positions']
    if len(actual)!=4 or any(len(a)!=140 or any(not math.isclose(x,y,rel_tol=1e-12,abs_tol=1e-12) for x,y in zip(a,b)) for a,b in zip(actual,expected)):raise ValueError('Exact canonical-to-NC start transform mismatch')
    counts=[a['draws'] for a in report['attempts']];calls=report.get('warmup_target_calls',0)
    for i,n in enumerate(counts):
        fit=load(directory/(f'draws-{n}/fit-report.json' if backend=='pymc' else f'draws-{n}-report.json'))
        # Tier files omit invocation identity; attach only frozen verified
        # identities, retaining tier diagnostics and comparing first-pass flags.
        merged=dict(report);merged.update(fit);merged['attempts']=report['attempts'][:i+1];merged['precision_pass']=report['attempts'][i]['screen']['pass']
        actual=fit_gate(merged,fixture,seed,enforce_cap=False)
        if actual!=report['attempts'][i]['screen']['pass'] or (actual and i!=len(counts)-1):raise ValueError('Tier first-pass mismatch')
        if backend=='pymc':
            raw=directory/f'draws-{n}/raw.json';validate_raw_starts(raw,fixture['starts'])
            if tail_field(raw,'adapted_metadata')!=report['adapted_metadata'] or tail_field(raw,'sampling_initial_positions')!=report['sampling_initial_positions']:raise ValueError('Native adaptation/start transport changed')
            a=report['attempts'][i];calls+=a['added_target_calls']
            if a['added_draws']!=n-(counts[i-1] if i else 0) or calls!=a['cumulative_target_calls']:raise ValueError('Native retained work mismatch')
    if backend=='numpyro':
        validate_raw_starts(directory/'raw.json',fixture['starts'])
        if tail_field(directory/'raw.json','sampling_initial_positions')!=report['sampling_initial_positions'] or report['warmup_iterations']!=[1000]*4:raise ValueError('Reference fresh adaptation/start mismatch')
        checks=report['checkpoints']
        if [v['draws'] for v in checks]!=list(range(1000,counts[-1]+1,1000)) or len({v['adaptation_sha256'] for v in checks})!=1:raise ValueError('Reference frozen adaptation mismatch')
        for i,v in enumerate(checks):
            if len(v['start_iterations'])!=4 or len(v['end_iterations'])!=4 or (i==0 and v['start_iterations']!=[1000]*4) or any(b-a!=1000 for a,b in zip(v['start_iterations'],v['end_iterations'])) or (i and v['start_iterations']!=checks[i-1]['end_iterations']):raise ValueError('Reference checkpoint continuity mismatch')
    else:
        if calls!=report['total_target_calls'] or calls!=report['session_progress_before_close']['target_calls'] or report['session_progress_before_close']['completed_transitions']!=[1000+counts[-1]]*4:raise ValueError('Native totalwork mismatch')
    return passed


def timing_report(summary,directory):
    """Keep process costs authoritative; never impute missing per-fit timings."""
    directory=Path(directory);rows=[]
    for record in summary['cohorts']:
        if type(record['elapsed_seconds']) not in (int,float) or not math.isfinite(record['elapsed_seconds']) or record['elapsed_seconds']<0:raise ValueError('Invalid outer process time')
        result=dict(id=record['id'],success=record['success'],process_seconds=record['elapsed_seconds'],fit_seconds=[None]*3,timing_status='unavailable')
        path=directory/record['id']/'cohort.json'
        if path.exists():
            try:
                cohort=load(path);costs=cohort['fit_costs']
                if cohort['expected']!=3 or len(costs)!=3:raise ValueError('Complete timing family required')
                values=[]
                for i,cost in enumerate(costs):
                    report_path=directory/record['id']/f'fit-{i}'/'report.json'
                    if cost['fit_index']!=i or cost['report_sha256']!=sha(report_path) or cost['status']!=load(report_path)['status']:raise ValueError('Timing/report binding mismatch')
                    value=cost['fit_seconds_including_final_report_write'];write=cost['final_report_write_seconds'];before=load(report_path)['fit_seconds_before_final_report_write']
                    if any(type(v) not in (int,float) or not math.isfinite(v) or v<0 for v in [value,write,before]) or value+1e-6<before+write:raise ValueError('Invalid fit timing')
                    values.append(value)
                if sum(values)>record['elapsed_seconds']+1e-6:raise ValueError('Fit costs exceed outer process cost')
                result.update(fit_seconds=values,cold_first_fit_seconds=values[0],later_fit_seconds=values[1:],unallocated_process_seconds=record['elapsed_seconds']-sum(values),timing_status='bound')
            except Exception as exc:result.update(timing_status='invalid',error=str(exc))
        rows.append(result)
    ratios=[]
    for pair in range(2):
        arms={backend:next((r for r in rows if r['id']==f'pair{pair}-{backend}'),None) for backend in ['pymc','numpyro']}
        a,b=arms['pymc'],arms['numpyro'];eligible=bool(a and b and a['success'] and b['success'] and a['timing_status']==b['timing_status']=='bound' and a['process_seconds']>0 and b['process_seconds']>0 and min(a['fit_seconds'])>0 and min(b['fit_seconds'])>0)
        ratios.append(dict(pair=pair,eligible=eligible,reference_over_public_process=b['process_seconds']/a['process_seconds'] if eligible else None,reference_over_public_fits=[y/x for x,y in zip(a['fit_seconds'],b['fit_seconds'])] if eligible else None))
    return dict(cohorts=rows,paired_ratios=ratios,total_process_seconds=sum(r['process_seconds'] for r in rows),qualified=False,scope='Development performance only. First-fit timing includes fit work; outer process cost additionally includes imports/controller/serialization. Later fits reuse process caches but adapt freshly. Missing timings remain missing; all process failures charged.')


def verify(plan):
    if sources()!=plan['study_bindings'] or any(sha(p)!=v for p,v in plan['bound_files'].items()) or runtime(plan['python'])!=plan['runtime']:raise ValueError('Bound source/runtime/input changed')
    for c in plan['fixtures']:
        if fixture_contract(c['path'],c['origin'])!=c:raise ValueError('Fixture contract changed')


def freeze(directory):
    directory=Path(directory).resolve();p=load(directory/'plan-draft.json');verify(p)
    if p['frozen']:raise ValueError('Invalid draft')
    if any((directory/name).exists() for name in ['plan.json','plan.sha256']):raise ValueError('Frozen outputs already exist')
    validate_plan(p,directory)
    p.update(frozen=True,reviewed_draft_sha256=sha(directory/'plan-draft.json'));save(directory/'plan.json',p)
    with (directory/'plan.sha256').open('x') as f:f.write(sha(directory/'plan.json'))


def execute(path):
    path=Path(path).resolve();p=load(path);digest=sha(path)
    if not p['frozen']:raise ValueError('Frozen plan required')
    validate_plan(p,path.parent)
    def check():
        if sha(path)!=digest or path.with_suffix('.sha256').read_text().strip()!=digest or sha(path.parent/'plan-draft.json')!=p['reviewed_draft_sha256']:raise ValueError('Plan drift')
        verify(p)
    if any((path.parent/name).exists() for name in ['execution-summary.json','timing-report.json']):raise ValueError('No summary overwrite')
    for c in p['cohorts']:
        if any((path.parent/(c['id']+suffix)).exists() for suffix in ['', '-status.json','-started.json','-hardware.json','-exit.json','.log']):raise ValueError('No retry/overwrite')
    abort=None;rows=[]
    for c in p['cohorts']:
        record=dict(id=c['id'],success=False,elapsed_seconds=0.,fit_ids=c['fit_ids']);out=path.parent/c['id'];tick=time.perf_counter()
        if abort:record.update(status='unattempted_provenance_abort',error=abort)
        else:
            save(path.parent/(c['id']+'-started.json'),dict(plan_sha256=digest,cohort=c))
            try:
                try:check()
                except Exception as exc:abort=str(exc);raise
                args=command(p,c,out)
                if args!=c['command']:raise ValueError('Command changed')
                with (path.parent/(c['id']+'.log')).open('x') as log:r=subprocess.run(args,cwd=HERE,env=dict(os.environ,PYTHONPATH=p['pythonpath']),stdout=log,stderr=subprocess.STDOUT)
                record['returncode']=r.returncode;save(path.parent/(c['id']+'-exit.json'),dict(record))
                try:check()
                except Exception as exc:abort=str(exc);raise
                hardware=load(path.parent/(c['id']+'-hardware.json'))
                from asof_rolling_execute import validate_hardware
                validate_hardware(hardware,args,r.returncode,1800)
                record.update(hardware_validated=True,status=hardware['status'],hardware_sha256=sha(path.parent/(c['id']+'-hardware.json')))
            except Exception as exc:record.update(status='failed',error=str(exc))
            record['elapsed_seconds']=time.perf_counter()-tick
        fits=[]
        for i,identity in enumerate(c['fit_ids']):
            rp=out/f'fit-{i}'/'report.json';entry=dict(id=identity,index=i,status='missing',usable=False)
            if rp.exists():
                try:
                    report=load(rp);entry.update(status=report.get('status'),report_sha256=sha(rp),reported_precision_pass=report.get('precision_pass',False))
                    entry['independently_validated_precision_pass']=validate_fit(report,p['fixtures'][c['fixture_indices'][i]],c['seeds'][i],c['backend'],out/f'fit-{i}')
                    entry['usable']=entry['independently_validated_precision_pass'] and record.get('hardware_validated') is True
                except Exception as exc:entry.update(status='validation_failed',error=str(exc))
            fits.append(entry)
        record['fits']=fits;record['success']=record.get('status')=='completed' and record.get('returncode')==0 and all(v['usable'] for v in fits);rows.append(record);save(path.parent/(c['id']+'-status.json'),record)
    save(path.parent/'execution-summary.json',dict(expected_processes=4,expected_fits=12,cohorts=rows,total_process_seconds=sum(r['elapsed_seconds'] for r in rows),cost_policy='Charge cohort cost once; do not assign unavailable per-fit timing after timeout. Successful-fit diagnostic validation required separately.',qualified=False))
    save(path.parent/'timing-report.json',timing_report(dict(cohorts=rows),path.parent))

def worker_preflight(path):
    path=Path(path);p=load(path)
    if not p.get('frozen') or path.with_suffix('.sha256').read_text().strip()!=sha(path) or sha(path.parent/'plan-draft.json')!=p['reviewed_draft_sha256']:raise ValueError('Unfrozen/drifted worker plan')
    validate_plan(p,path.parent);verify(p)
    return p


if __name__=='__main__':
    import argparse
    a=argparse.ArgumentParser();a.add_argument('--worker-plan',type=Path,required=True);a.add_argument('--cohort',required=True);a.add_argument('--worker-out',type=Path,required=True);v=a.parse_args();p=worker_preflight(v.worker_plan)
    c=next(c for c in p['cohorts'] if c['id']==v.cohort)
    from persistent_masked_workflow import execute as fit
    reports=fit([p['fixtures'][i]['path'] for i in c['fixture_indices']],v.worker_out,c['seeds'],c['backend'],warmup=1000,tiers=TIERS,batch=1000)
    raise SystemExit(0 if all(r.get('status')=='completed' and r.get('precision_pass') for r in reports) else 2)
