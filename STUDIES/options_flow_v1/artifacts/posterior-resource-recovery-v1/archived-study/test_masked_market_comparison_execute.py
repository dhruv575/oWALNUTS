"""Static-authored contract tests; no real sampler or numerical libraries used."""
import copy
import json
from types import SimpleNamespace
import pytest
import masked_market_comparison_execute as executor
from masked_market_comparison_plan import contract
from test_masked_market_comparison_plan import fixture


def healthy_report(source):
    schema=contract(source);diagnostic=dict(rhat=1.,bulk_ess=800.,tail_ess=700.)
    functions={name:dict(diagnostic,interval_90=[-1.,1.],endpoint_mcse=[.01,.01]) for name in schema['precision_names']}
    rows=[]
    for h,g in schema['forecast_cells']:
        observed=source['holdout']['observation_mask'][h-1][g]
        rows.append(dict(horizon=h,group=g,grid_index=source['holdout']['grid_index'][h-1],
            forecast_available=True,target_observed=observed,observed=source['holdout']['y'][h-1][g] if observed else None,
            lower=-1.,upper=1.,width=2.,endpoint_mcse=[.01,.01],covered=True if observed else None,interval_score=2. if observed else None))
    report=dict(status='completed',retained_divergences=0,evaluation=dict(chain_count=4,functionals=functions,
        canonical_parameter_diagnostics={f'q_{i}':dict(diagnostic) for i in range(108)},
        forecast=dict(rows=rows,available_forecast_cells=192,scored_cells=4,observed_target_cells=4)))
    return report,dict(schema=schema)


def test_independent_health_and_exact_horizon_family():
    source=fixture();report,plan=healthy_report(source)
    assert executor.fit_gate(report,plan,source)
    report['evaluation']['canonical_parameter_diagnostics']['q_107']['rhat']=1.02
    assert not executor.fit_gate(report,plan,source)
    report,_=healthy_report(source);report['evaluation']['forecast']['rows'][-1]['horizon']=1
    with pytest.raises(ValueError,match='family'):executor.fit_gate(report,plan,source)
    report,_=healthy_report(source);report['evaluation']['forecast']['rows'][-1]['endpoint_mcse']=[.05,.05]
    assert not executor.fit_gate(report,plan,source)


def test_labels_and_alpha_sign_do_not_choose_precision_gate():
    source=fixture();report,plan=healthy_report(source)
    for j in range(4):
        source['holdout']['y'][0][j]=100.
        row=report['evaluation']['forecast']['rows'][j]
        row.update(observed=100.,covered=False,interval_score=1982.)
        report['evaluation']['functionals'][f'alpha_{j}']['interval_90']=[-3.,-1.]
    assert executor.fit_gate(report,plan,source)
    report['evaluation']['forecast']['rows'][4]['covered']=False
    with pytest.raises(ValueError,match='Missing label'):executor.fit_gate(report,plan,source)


def mock_plan(tmp_path):
    plan=dict(frozen=True,expected=4,pythonpath='package',cells=[])
    for i in range(4):plan['cells'].append(dict(id=f'cell{i}',arm='owalnuts_continuation',command=['fake']))
    path=tmp_path/'plan.json';path.write_text(json.dumps(plan));return path,plan


@pytest.mark.parametrize('mode',['success','missing-report','timeout','exception'])
def test_terminal_records_charge_every_attempt_and_never_retry(tmp_path,monkeypatch,mode):
    path,plan=mock_plan(tmp_path);calls=[]
    monkeypatch.setattr(executor,'verify',lambda *a:None)
    monkeypatch.setattr(executor,'command',lambda *a:['fake'])
    monkeypatch.setattr(executor,'validate_report',lambda *a:True)
    def run(*args,**kwargs):
        i=len(calls);calls.append(i);cell=plan['cells'][i];out=tmp_path/cell['id']
        if mode=='exception':raise RuntimeError('worker launch failed')
        hardware=dict(status='worker-timeout' if mode=='timeout' else 'completed',job_active_processes_after_cleanup=0,realized_cpus=[0])
        (tmp_path/(cell['id']+'-hardware.json')).write_text(json.dumps(hardware))
        if mode=='success':
            out.mkdir();(out/'python-pymc-flow-report.json').write_text(json.dumps(dict(status='completed')))
        return SimpleNamespace(returncode=124 if mode=='timeout' else 0)
    monkeypatch.setattr(executor.subprocess,'run',run)
    executor.execute(path)
    assert len(calls)==4
    records=[json.loads((tmp_path/(c['id']+'-status.json')).read_text()) for c in plan['cells']]
    assert all(r['elapsed_seconds']>=0 and r['success']==(mode=='success') for r in records)
    if mode=='timeout':assert all(r['status']=='budgeted_computational_timeout' for r in records)
    with pytest.raises(ValueError,match='Already attempted'):executor.execute(path)


def test_plan_digest_change_detected_before_source_or_runtime_reads(tmp_path):
    path=tmp_path/'plan.json';path.write_text('{}');original=executor.sha(path)
    path.write_text('{"mutated":true}');path.with_suffix('.sha256').write_text(executor.sha(path))
    with pytest.raises(ValueError,match='Plan drift'):executor.verify(path,{},original)


def test_stale_source_terminalizes_all_unstarted_cells(tmp_path,monkeypatch):
    path,plan=mock_plan(tmp_path)
    def reject(*args):raise ValueError('Source drift')
    monkeypatch.setattr(executor,'verify',reject)
    monkeypatch.setattr(executor.subprocess,'run',lambda *a,**k:pytest.fail('Must not launch'))
    executor.execute(path)
    statuses=[json.loads((tmp_path/(c['id']+'-status.json')).read_text()) for c in plan['cells']]
    assert statuses[0]['status']=='executor_or_validation_failed'
    assert all(s['status']=='unattempted_provenance_abort' for s in statuses[1:])


def test_candidate_callback_frozen_state_and_first_pass_contract(tmp_path):
    source=fixture();fit,plan=healthy_report(source)
    fixture_path=tmp_path/'fixture.json';fixture_path.write_text(json.dumps(source))
    starts=[[0.]*108 for _ in range(4)]
    cell=dict(arm='owalnuts_continuation',seed=91,predictive_seed=130091,
        fixture=str(fixture_path),fixture_sha256=executor.sha(fixture_path),starts=starts)
    plan.update(study_bindings={},bound_files={})
    metadata=[dict(mass_diagonal=[1.]*108,final_step_size=.1)]*4
    report=dict(fit,seed=91,model='masked-flow',settings=dict(chains=4,warmup=1000,threads=1,block_size=32),
        bindings={str(fixture_path):cell['fixture_sha256']},parity=dict(passed=True),
        initial_positions=starts,predictive_seed=130091,precision_plan=dict(names=plan['schema']['precision_names'],forecast_expected_cells=plan['schema']['forecast_cells']),
        hardware_control=dict(realized_cpus=[0]),adapted_metadata=metadata,precision_pass=True,
        warmup_target_calls=10,initialization_target_calls=2,total_target_calls=20,
        session_progress_before_close=dict(target_calls=20,completed_transitions=[2000]*4),
        attempts=[dict(draws=1000,added_draws=1000,added_target_calls=10,cumulative_target_calls=20,screen={'pass':True})])
    tier=tmp_path/'draws-1000';tier.mkdir()
    (tier/'fit-report.json').write_text(json.dumps(fit))
    raw=tier/'python-pymc-flow-raw.json';raw.write_text(json.dumps(dict(adapted_metadata=metadata,initial_positions=starts)))
    assert executor.validate_report(plan,cell,report,tmp_path)
    bad=copy.deepcopy(report);bad['attempts'][0]['added_target_calls']=9
    with pytest.raises(ValueError,match='callback'):executor.validate_report(plan,cell,bad,tmp_path)
    bad=copy.deepcopy(report);bad['adapted_metadata'][0]['final_step_size']=.2
    with pytest.raises(ValueError,match='frozen'):executor.validate_report(plan,cell,bad,tmp_path)
    bad=copy.deepcopy(report);bad['attempts'].append(dict(draws=2000,screen={'pass':True}))
    with pytest.raises(ValueError,match='first passing'):executor.validate_report(plan,cell,bad,tmp_path)
