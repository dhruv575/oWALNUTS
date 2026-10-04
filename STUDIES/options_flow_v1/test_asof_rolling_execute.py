"""Queued only: no subprocess or numerical job in these contracts."""
import copy
import pytest
from asof_rolling_execute import gate
from masked_market_comparison_plan import NAMES


def valid():
    diagnostic=dict(rhat=1.,bulk_ess=500.,tail_ess=500.,interval_90=[-1.,1.],endpoint_mcse=[.01,.01])
    report=dict(status='completed',retained_divergences=0,evaluation=dict(chain_count=4,
        functionals={k:copy.deepcopy(diagnostic) for k in NAMES},canonical_parameter_diagnostics={f'q_{i}':copy.deepcopy(diagnostic) for i in range(140)},
        forecast=dict(scored_cells=0,observed_target_cells=0,available_forecast_cells=4,rows=[dict(horizon=1,group=g,grid_index=128,forecast_available=True,target_observed=False,observed=None,covered=None,interval_score=None,lower=-1.,upper=1.,width=2.,endpoint_mcse=[.01,.01]) for g in range(4)])))
    return report,dict(precision_names=NAMES,forecast_cells=[[1,g] for g in range(4)])


def test_full_gate_and_no_future_labels():
    report,cell=valid();assert gate(report,cell)
    report['evaluation']['forecast']['rows'][0]['observed']=.2
    with pytest.raises(ValueError):gate(report,cell)


@pytest.mark.parametrize('mutation',[
    lambda r:r.update(retained_divergences=1),
    lambda r:r['evaluation']['canonical_parameter_diagnostics']['q_139'].update(rhat=1.02),
    lambda r:r['evaluation']['functionals']['tau'].update(endpoint_mcse=[.1,.1]),
    lambda r:r['evaluation']['forecast']['rows'][3].update(endpoint_mcse=[.1,.1]),
])
def test_no_subset_health_or_precision_pass(mutation):
    report,cell=valid();mutation(report);assert not gate(report,cell)


def lifecycle(tmp_path,monkeypatch,mode='completed'):
    import json
    from types import SimpleNamespace
    import asof_rolling_execute as e
    from asof_rolling_protocol import ORIGINS
    cells=[dict(id=f'cell-{i}',arm='owalnuts_continuation',fixture_sha256='fixture',command=['wrapper','--','mock',str(i)]) for i in range(32)]
    plan=dict(frozen=True,origins=ORIGINS,expected=32,cells=cells,pythonpath='mock',timeout_seconds=600)
    path=tmp_path/'plan.json';path.write_text(json.dumps(plan));path.with_suffix('.sha256').write_text(e.sha(path))
    # Lifecycle isolated from schema tests: workers and validation are mocks.
    monkeypatch.setattr(e,'validate_plan',lambda *a:None)
    monkeypatch.setattr(e,'verify',lambda *a:None)
    monkeypatch.setattr(e,'command',lambda p,c,o:c['command'])
    monkeypatch.setattr(e,'validate_result',lambda *a:True)
    calls=[]
    def run(args,**kwargs):
        i=int(args[-1]);calls.append(i);cid=cells[i]['id'];out=tmp_path/cid;out.mkdir()
        hardware=dict(command=args[args.index('--')+1:],returncode=124 if mode=='timeout' else 0,elapsed_seconds=600.1,containment=dict(kind='windows-job-object',assigned_before_worker_execution=True),enforced_before_worker_launch=True,job_active_processes_after_cleanup=0,realized_cpus=[0],status='worker-timeout' if mode=='timeout' else 'completed')
        (tmp_path/(cid+'-hardware.json')).write_text(json.dumps(hardware))
        if mode!='missing':(out/'python-pymc-flow-report.json').write_text(json.dumps(dict(status='completed')))
        if mode=='exception':raise RuntimeError('worker launch error')
        return SimpleNamespace(returncode=124 if mode=='timeout' else 0)
    monkeypatch.setattr(e.subprocess,'run',run)
    return e,path,calls


@pytest.mark.parametrize('mode,expected',[('completed','completed'),('timeout','budgeted_computational_timeout'),('missing','executor_or_validation_failed'),('exception','executor_or_validation_failed')])
def test_full32_terminal_lifecycle_and_charged_failures(tmp_path,monkeypatch,mode,expected):
    import json
    e,path,calls=lifecycle(tmp_path,monkeypatch,mode);e.execute(path)
    statuses=[json.loads(p.read_text()) for p in tmp_path.glob('*-status.json')]
    assert len(calls)==len(statuses)==32
    assert all(s['status']==expected and s['elapsed_seconds']>=0 for s in statuses)
    assert all(s['success']==(mode=='completed') for s in statuses)
    with pytest.raises(ValueError):e.execute(path)
    assert len(calls)==32


def test_provenance_failure_preserves32_denominator(tmp_path,monkeypatch):
    import json
    e,path,calls=lifecycle(tmp_path,monkeypatch)
    def stale(*a):raise ValueError('source drift')
    monkeypatch.setattr(e,'verify',stale);e.execute(path)
    statuses=[json.loads(p.read_text()) for p in tmp_path.glob('*-status.json')]
    assert len(statuses)==32 and not calls
    assert sum(s['status']=='unattempted_provenance_abort' for s in statuses)==31


def test_preexisting_output_prevents_any_launch(tmp_path,monkeypatch):
    e,path,calls=lifecycle(tmp_path,monkeypatch)
    (tmp_path/'cell-31').mkdir()
    with pytest.raises(ValueError):e.execute(path)
    assert not calls


def test_plan_and_sidecar_simultaneous_mutation_rejected(tmp_path):
    import json
    from asof_rolling_execute import verify,sha
    path=tmp_path/'plan.json';path.write_text('{}');old=sha(path)
    path.write_text('{"changed":true}');path.with_suffix('.sha256').write_text(sha(path))
    with pytest.raises(ValueError,match='Plan drift'):verify(path,{},old)


@pytest.mark.parametrize('value',[0.,-1.])
def test_nonpositive_rhat_rejected(value):
    r,c=valid();r['evaluation']['canonical_parameter_diagnostics']['q_0']['rhat']=value
    assert not gate(r,c)

@pytest.mark.parametrize('mutation',[
 lambda h:h.update(command=['wrong']),lambda h:h.update(returncode=0),
 lambda h:h.update(elapsed_seconds=599.),lambda h:h['containment'].update(assigned_before_worker_execution=False),
 lambda h:h.update(enforced_before_worker_launch=False)])
def test_hardware_evidence_gaps(mutation):
    from asof_rolling_execute import validate_hardware
    h=dict(command=['worker'],returncode=124,elapsed_seconds=600.,realized_cpus=[0],job_active_processes_after_cleanup=0,enforced_before_worker_launch=True,containment=dict(kind='windows-job-object',assigned_before_worker_execution=True),status='worker-timeout')
    validate_hardware(h,['wrapper','--','worker'],124,600)
    mutation(h)
    with pytest.raises(ValueError):validate_hardware(h,['wrapper','--','worker'],124,600)


@pytest.mark.parametrize('bad',[
 [{'start_iterations':[0]*4,'end_iterations':[999]*4}],
 [{'start_iterations':[0]*4,'end_iterations':[1000]*4},{'start_iterations':[1001]*4,'end_iterations':[2001]*4}],
 [{'start_iterations':[0]*3,'end_iterations':[1000]*3}],
])
def test_reference_checkpoint_gaps(bad):
    from asof_rolling_execute import validate_checkpoint_continuity
    validate_checkpoint_continuity([{'start_iterations':[0]*4,'end_iterations':[1000]*4}])
    with pytest.raises(ValueError):validate_checkpoint_continuity(bad)
