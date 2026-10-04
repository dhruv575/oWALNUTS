import copy,json
from types import SimpleNamespace
import pytest
import persistent_comparison_plan as p
from test_asof_rolling_execute import valid


def report_fixture():
    r,_=valid();f=dict(sha256='fixture',starts=[[0.]*140]*4,forecast_cells=[[1,g] for g in range(4)])
    r.update(seed=9,predictive_seed=130009,fixture_sha256='fixture',initial_positions=f['starts'],fresh_adaptation=True,posterior_continuation=False,precision_pass=True,attempts=[dict(draws=1000,screen={'pass':True})])
    return r,f


def test_gate_complete_family_and_malformed_status():
    r,f=report_fixture();assert p.fit_gate(r,f,9)
    for mutate in [lambda q:q.update(status='garbage'),lambda q:q.update(fresh_adaptation=False),lambda q:q['evaluation']['canonical_parameter_diagnostics'].pop('q_139'),lambda q:q['evaluation']['forecast']['rows'].__setitem__(3,copy.deepcopy(q['evaluation']['forecast']['rows'][2]))]:
        bad=copy.deepcopy(r);mutate(bad)
        with pytest.raises(ValueError):p.fit_gate(bad,f,9)


def test_firstpass_and_failed_cap():
    r,f=report_fixture();r['evaluation']['functionals']['tau']['endpoint_mcse']=[1.,1.];r['precision_pass']=False;r['attempts'][0]['screen']['pass']=False
    with pytest.raises(ValueError):p.fit_gate(r,f,9)
    assert not p.fit_gate(r,f,9,enforce_cap=False)
    r['attempts']=[dict(draws=n,screen={'pass':False}) for n in p.TIERS]
    assert not p.fit_gate(r,f,9)
    r['attempts'][0]['screen']['pass']=True
    with pytest.raises(ValueError):p.fit_gate(r,f,9)


@pytest.mark.parametrize('drift',['unfrozen','sidecar','draft'])
def test_worker_preflight_fails_before_worker(tmp_path,monkeypatch,drift):
    draft=tmp_path/'plan-draft.json';draft.write_text('{}');path=tmp_path/'plan.json'
    path.write_text(json.dumps(dict(frozen=drift!='unfrozen',reviewed_draft_sha256=p.sha(draft))))
    path.with_suffix('.sha256').write_text('bad' if drift=='sidecar' else p.sha(path))
    if drift=='draft':draft.write_text('{"changed":true}')
    monkeypatch.setattr(p,'validate_plan',lambda *a:pytest.fail('validation reached before integrity rejection'))
    with pytest.raises(ValueError):p.worker_preflight(path)


@pytest.mark.parametrize('mode',['completed','truncated','timeout','bad_hardware','launch_error','partial'])
def test_full_denominator_and_hardware_failures(tmp_path,monkeypatch,mode):
    cohorts=[dict(id=f'c{i}',backend='numpyro',seeds=[1,2,3],fixture_indices=[0,1,0],fit_ids=[f'c{i}-f{j}' for j in range(3)],command=['wrapper','--','worker',str(i)]) for i in range(4)]
    draft=tmp_path/'plan-draft.json';draft.write_text('{}');path=tmp_path/'plan.json'
    plan=dict(frozen=True,reviewed_draft_sha256=p.sha(draft),cohorts=cohorts,fixtures=[{},{}],pythonpath='unused')
    path.write_text(json.dumps(plan));path.with_suffix('.sha256').write_text(p.sha(path))
    monkeypatch.setattr(p,'validate_plan',lambda *a:None);monkeypatch.setattr(p,'verify',lambda *a:None);monkeypatch.setattr(p,'command',lambda a,c,o:c['command']);monkeypatch.setattr(p,'validate_fit',lambda r,*a:r.get('precision_pass',False))
    def run(args,**kw):
        i=int(args[-1]);c=cohorts[i]
        if mode=='launch_error':raise RuntimeError('launch')
        for j in range(3):
            d=tmp_path/c['id']/f'fit-{j}';d.mkdir(parents=True)
            (d/'report.json').write_text('{' if mode=='truncated' and j==1 else json.dumps(dict(status='completed',precision_pass=not(mode=='partial' and j==1))))
        h=dict(command=args[2:],returncode=124 if mode=='timeout' else (2 if mode=='partial' else 0),elapsed_seconds=1800.1,enforced_before_worker_launch=True,job_active_processes_after_cleanup=0,realized_cpus=[0],containment=dict(kind='windows-job-object',assigned_before_worker_execution=mode!='bad_hardware'),status='worker-timeout' if mode=='timeout' else ('worker-failed' if mode=='partial' else 'completed'))
        (tmp_path/(c['id']+'-hardware.json')).write_text(json.dumps(h));return SimpleNamespace(returncode=h['returncode'])
    monkeypatch.setattr(p.subprocess,'run',run);p.execute(path)
    summary=p.load(tmp_path/'execution-summary.json');assert len(summary['cohorts'])==4
    assert sum(len(c['fits']) for c in summary['cohorts'])==12
    assert all(c['success']==(mode=='completed') for c in summary['cohorts'])
    if mode in ('bad_hardware','launch_error'):assert not any(f['usable'] for c in summary['cohorts'] for f in c['fits'])
    if mode=='partial':assert sum(f['usable'] for c in summary['cohorts'] for f in c['fits'])==8
    assert (tmp_path/'timing-report.json').exists()
    if mode=='truncated':assert sum(f['status']=='validation_failed' for c in summary['cohorts'] for f in c['fits'])==4
    with pytest.raises(ValueError):p.execute(path)

@pytest.mark.parametrize('mutation',[lambda p:p.update(fixtures=[{}, {}, {}]),lambda p:p.update(initialization_policy='fresh unreviewed'),lambda p:p.update(warmup=0)])
def test_schema_rejects_before_archive_replay(tmp_path,monkeypatch,mutation):
    plan=dict(expected_processes=4,expected_fits=12,chains=4,warmup=1000,tiers=p.TIERS,batch=1000,relative_mcse=.02,reference_target_accept=.9,timeout_seconds=1800,initialization_policy=p.INIT_POLICY,fixtures=[{},{}])
    mutation(plan)
    with pytest.raises(ValueError):p.validate_plan(plan,tmp_path)


@pytest.mark.parametrize('mutation',[lambda r:r.update(warmup_iterations=[0]*4),lambda r:r['checkpoints'][0].update(start_iterations=[0]*4,end_iterations=[1000]*4),lambda r:r['checkpoints'][0].update(end_iterations=[2000]),lambda r:r['checkpoints'].append(dict(draws=2000,adaptation_sha256='changed',start_iterations=[2000]*4,end_iterations=[3000]*4))])
def test_reference_rejects_fake_fresh_warmup_and_truncated_checkpoint(tmp_path,monkeypatch,mutation):
    import continuation_comparison,masked_market_comparison_execute
    r,f=report_fixture();f['path']=str(tmp_path/'fixture.json');(tmp_path/'fixture.json').write_text('{"data":{"rho":0.95}}')
    r.update(backend='numpyro',sampling_initial_positions=f['starts'],warmup_iterations=[1000]*4,checkpoints=[dict(draws=1000,adaptation_sha256='fixed',start_iterations=[1000]*4,end_iterations=[2000]*4)])
    (tmp_path/'draws-1000-report.json').write_text(json.dumps(r))
    monkeypatch.setattr(continuation_comparison,'validate_raw_starts',lambda *a:None)
    monkeypatch.setattr(masked_market_comparison_execute,'tail_field',lambda *a:r['sampling_initial_positions'])
    assert p.validate_fit(r,f,9,'numpyro',tmp_path)
    mutation(r)
    with pytest.raises(ValueError):p.validate_fit(r,f,9,'numpyro',tmp_path)

@pytest.mark.parametrize('change',['none','order','command','anchor','init'])
def test_deterministic_plan_archive_and_cohort_binding(tmp_path,monkeypatch,change):
    import asof_market_fixture as a
    for name,obj in [('panel',{'raw':'bound'}),('anchors',{'price':2}),('protocol',{})]:
        (tmp_path/name).write_text(json.dumps(obj))
    fixtures=[]
    for origin in [168,216]:
        path=tmp_path/str(origin);path.write_text(json.dumps({'provenance':{'init_seed':7},'origin':origin}))
        fixtures.append(dict(path=str(path),origin=origin,init_seed=7))
    plan=dict(expected_processes=4,expected_fits=12,chains=4,warmup=1000,tiers=p.TIERS,batch=1000,relative_mcse=.02,reference_target_accept=.9,timeout_seconds=1800,initialization_policy=p.INIT_POLICY,fixtures=fixtures,seed_rows=[[1,2,3],[4,5,6]],seed_audit_path='mock',panel=str(tmp_path/'panel'),anchors=str(tmp_path/'anchors'),protocol=str(tmp_path/'protocol'),archive_directory='archive',python='python',cohorts=[])
    monkeypatch.setattr(p,'reviewed_seeds',lambda *args:None)
    monkeypatch.setattr(a,'attach_archived_anchors',lambda original,archive:{'price':2})
    monkeypatch.setattr(a,'prepare',lambda derived,rules,origin_index,window,init_seed:{'provenance':{'init_seed':init_seed},'origin':origin_index})
    for pair,order in enumerate([['pymc','numpyro'],['numpyro','pymc']]):
        for backend in order:
            c=dict(id=f'pair{pair}-{backend}',backend=backend,seeds=plan['seed_rows'][pair],fixture_indices=[0,1,0],fit_ids=[f'pair{pair}-{backend}-fit{i}' for i in range(3)])
            c['command']=p.command(plan,c,tmp_path/c['id']);plan['cohorts'].append(c)
    if change=='order':plan['cohorts'].reverse()
    if change=='command':plan['cohorts'][0]['command'].append('--bad')
    if change=='anchor':(tmp_path/'anchors').write_text('{"price":999}')
    if change=='init':plan['fixtures'][0]['init_seed']=8
    if change=='none':p.validate_plan(plan,tmp_path)
    else:
        with pytest.raises(ValueError):p.validate_plan(plan,tmp_path)

@pytest.mark.parametrize('change',['none','calls','transitions','adaptation'])
def test_native_work_and_frozen_adaptation(tmp_path,monkeypatch,change):
    import continuation_comparison,masked_market_comparison_execute
    r,f=report_fixture();f['path']=str(tmp_path/'fixture.json');(tmp_path/'fixture.json').write_text('{"data":{"rho":0.95}}')
    r.update(backend='pymc',sampling_initial_positions=f['starts'],warmup_target_calls=30,total_target_calls=50,adapted_metadata={'mass':'fixed'},session_progress_before_close={'target_calls':50,'completed_transitions':[2000]*4})
    r['attempts'][0].update(added_target_calls=20,cumulative_target_calls=50,added_draws=1000)
    d=tmp_path/'draws-1000';d.mkdir();(d/'fit-report.json').write_text(json.dumps(r))
    monkeypatch.setattr(continuation_comparison,'validate_raw_starts',lambda *a:None)
    monkeypatch.setattr(masked_market_comparison_execute,'tail_field',lambda path,key:({'mass':'changed'} if change=='adaptation' else r['adapted_metadata']) if key=='adapted_metadata' else r['sampling_initial_positions'])
    if change=='calls':r['attempts'][0]['cumulative_target_calls']=49
    if change=='transitions':r['session_progress_before_close']['completed_transitions']=[1000]*4
    if change=='none':assert p.validate_fit(r,f,9,'pymc',tmp_path)
    else:
        with pytest.raises(ValueError):p.validate_fit(r,f,9,'pymc',tmp_path)

@pytest.mark.parametrize('change',['none','short_x','integer_mask','nan_start','future_label','bool_seed'])
def test_strict_fixture_contract(tmp_path,change):
    f=dict(data=dict(x=[[0.]*4 for _ in range(128)],y=[[0.]*4 for _ in range(128)],observation_mask=[[False]*4 for _ in range(128)],grid_index=list(range(128)),rho=.95,nu=5,initial_positions=[[0.]*140 for _ in range(4)]),holdout=dict(x=[[0.]*4],x_available=[[True]*4],y=[[None]*4],observation_mask=[[False]*4],grid_index=[128]),provenance=dict(origin_index=168,init_seed=7),precision_family=[[1,g] for g in range(4)])
    if change=='short_x':f['data']['x'].pop()
    if change=='integer_mask':f['data']['observation_mask'][0][0]=1
    if change=='nan_start':f['data']['initial_positions'][0][0]=float('nan')
    if change=='future_label':f['holdout']['y'][0][0]=0.
    if change=='bool_seed':f['provenance']['init_seed']=True
    path=tmp_path/'fixture.json';path.write_text(json.dumps(f))
    if change=='none':assert p.fixture_contract(path,168)['observed_count']==0
    else:
        with pytest.raises(ValueError):p.fixture_contract(path,168)


@pytest.mark.parametrize('change',['none','missing','tamper','failed','negative'])
def test_timing_binding_all_costs_and_eligible_ratios(tmp_path,change):
    records=[]
    for backend in ['pymc','numpyro']:
        cid=f'pair0-{backend}';root=tmp_path/cid;root.mkdir();costs=[]
        for i in range(3):
            folder=root/f'fit-{i}';folder.mkdir();rp=folder/'report.json';rp.write_text(json.dumps(dict(status='completed',fit_seconds_before_final_report_write=1.)))
            costs.append(dict(fit_index=i,status='completed',report_sha256=p.sha(rp),fit_seconds_including_final_report_write=2.,final_report_write_seconds=.1))
        (root/'cohort.json').write_text(json.dumps(dict(expected=3,fit_costs=costs)))
        records.append(dict(id=cid,success=True,elapsed_seconds=10.))
    if change=='missing':(tmp_path/'pair0-pymc'/'cohort.json').unlink()
    if change=='tamper':(tmp_path/'pair0-pymc'/'fit-1'/'report.json').write_text('{}')
    if change=='failed':records[0]['success']=False
    if change=='negative':
        path=tmp_path/'pair0-pymc'/'cohort.json';v=p.load(path);v['fit_costs'][0]['fit_seconds_including_final_report_write']=-1;path.write_text(json.dumps(v))
    result=p.timing_report({'cohorts':records},tmp_path)
    assert result['total_process_seconds']==20
    assert result['paired_ratios'][0]['eligible']==(change=='none')
    if change=='none':assert result['cohorts'][0]['later_fit_seconds']==[2.,2.] and result['cohorts'][0]['unallocated_process_seconds']==4
    else:assert result['paired_ratios'][0]['reference_over_public_process'] is None

@pytest.mark.parametrize('value',[float('nan'),float('inf'),-1.,True])
def test_invalid_outer_cost_never_enters_ratios(tmp_path,value):
    with pytest.raises(ValueError,match='outer process'):
        p.timing_report(dict(cohorts=[dict(id='pair0-pymc',success=True,elapsed_seconds=value)]),tmp_path)


@pytest.mark.parametrize('initial',[ [1,9], [130001,9], [9,9] ])
def test_initialization_stream_collisions_rejected(initial):
    with pytest.raises(ValueError,match='Distinct'):
        p.reviewed_seeds([[1,2,3],[4,5,6]],'must-not-read',initial)
