"""No-sampler prospective comparison contracts."""
import copy
import json
from pathlib import Path
from types import SimpleNamespace
import pytest
import mixed_flow_comparison as comparison


def setup_report(tmp_path,arm):
    fixture=tmp_path/'fixture.json';fixture.write_text('{}');python=tmp_path/'python.exe';python.write_text('dummy')
    starts=[[float(i)]*140 for i in range(4)]
    cell=dict(id=arm,arm=arm,coordinates='mixed_slopes' if arm.endswith('mixed') else 'noncentered',
        fixture=str(fixture),fixture_sha256=comparison.sha(fixture),seed=31,predictive_seed=130031,
        dimension=140,forecast_rows=4,starts=starts)
    plan=dict(python=str(python),study_bindings={},bound_files={str(python):comparison.sha(python)})
    diagnostic=dict(rhat=1.,bulk_ess=800.,tail_ess=700.)
    evaluation=dict(chain_count=4,functionals={n:dict(diagnostic,interval_90=[-1.,1.],endpoint_mcse=[.01,.01]) for n in comparison.NAMES},
        canonical_parameter_diagnostics={f'q_{i}':dict(diagnostic) for i in range(140)},
        forecast=dict(rows=[dict(horizon=1,group=g,lower=-1.,upper=1.,endpoint_mcse=[.01,.01]) for g in range(4)]))
    metadata=[dict(mass_diagonal=[1.]*140,final_step_size=.1)]*4
    checkpoint=dict(draws_per_chain=1000,start_iterations=[1000]*4,end_iterations=[2000]*4,adaptation_sha256='fixed')
    report=dict(status='completed',model='flow',seed=31,predictive_seed=130031,coordinates=cell['coordinates'],
        source_sha256={},fixture_sha256=cell['fixture_sha256'],
        bindings={str(fixture):cell['fixture_sha256'],str(python):comparison.sha(python)},
        settings=dict(chains=4,warmup=1000,target_accept=.9,block_size=32,threads=1,batch=1000,tiers=comparison.TIERS),
        evaluation=evaluation,retained_divergences=0,precision_pass=True,
        initial_positions=starts,hardware_control=dict(realized_cpus=[0]),
        precision_plan=dict(names=comparison.NAMES,forecast_rows=4),
        parity=dict(passed=True,jax_enable_x64=True,normalized_canonical_jacobian_value_and_gradient=True,cases=[{}]),
        attempts=[dict(draws=1000,added_draws=1000,added_target_calls=10,cumulative_target_calls=20,
            screen={'pass':True,'parameter_functionals':comparison.NAMES,'forecast_rows':4,'threshold':.02})],
        checkpoints=[checkpoint],warmup_target_calls=10,initialization_target_calls=2,total_target_calls=20,
        adapted_metadata=metadata,session_progress_before_close=dict(target_calls=20,completed_transitions=[2000]*4))
    out=tmp_path/'out';out.mkdir()
    candidate=arm.startswith('ow_')
    if candidate:
        (out/'draws-1000').mkdir();fit=out/'draws-1000/fit-report.json';raw=out/'draws-1000/python-pymc-flow-raw.json'
    else:
        fit=out/'draws-1000-report.json';raw=out/('draws-1000-raw.json' if arm=='numpyro_mixed' else 'numpyro-continuation-raw.json')
    fit.write_text(json.dumps(report));raw.write_text(json.dumps(dict(adapted_metadata=metadata,initial_positions=starts)))
    return plan,cell,report,out


@pytest.mark.parametrize('arm',comparison.ARMS)
def test_all_four_report_schemas_and_commands(tmp_path,arm):
    plan,cell,report,out=setup_report(tmp_path,arm)
    assert comparison.validate(plan,cell,report,out)
    cmd=comparison.command(plan,cell,out)
    assert cmd[cmd.index('--timeout')+1]=='1800'
    if arm.startswith('ow_'):assert cmd[cmd.index('--coordinates')+1]==cell['coordinates']
    else:assert cmd[cmd.index('--target-accept')+1]=='0.9'


def test_mixed_parity_scope_and_work_cannot_be_silently_skipped(tmp_path):
    plan,cell,report,out=setup_report(tmp_path,'ow_mixed')
    report['parity']['normalized_canonical_jacobian_value_and_gradient']=False
    with pytest.raises(ValueError,match='parity'):comparison.validate(plan,cell,report,out)
    report['parity']['normalized_canonical_jacobian_value_and_gradient']=True
    report['total_target_calls']=21
    with pytest.raises(ValueError,match='work'):comparison.validate(plan,cell,report,out)


def test_independent_forecast_and_coordinate_family(tmp_path):
    plan,cell,report,out=setup_report(tmp_path,'numpyro_mixed')
    report['evaluation']['forecast']['rows'][3]['group']=0
    with pytest.raises(ValueError,match='Forecast'):comparison.gate(report,cell)
    report['evaluation']['forecast']['rows'][3]['group']=3
    report['evaluation']['canonical_parameter_diagnostics']['q_139']['tail_ess']=399
    assert not comparison.gate(report,cell)


@pytest.mark.parametrize('mode',['timeout','missing-report','exception'])
def test_all_eight_failures_remain_terminal_and_charged(tmp_path,monkeypatch,mode):
    cells=[dict(id=str(i),arm='ow_nc',command=['fake']) for i in range(8)]
    path=tmp_path/'plan.json';path.write_text(json.dumps(dict(frozen=True,expected=8,cells=cells,pythonpath='package')))
    monkeypatch.setattr(comparison,'verify',lambda *a:None);monkeypatch.setattr(comparison,'command',lambda *a:['fake'])
    calls=[]
    def run(*args,**kwargs):
        index=len(calls);calls.append(index)
        if mode=='exception':raise RuntimeError('launch failed')
        (tmp_path/f'{index}-hardware.json').write_text(json.dumps(dict(status='worker-timeout' if mode=='timeout' else 'worker-failed',job_active_processes_after_cleanup=0,realized_cpus=[0])))
        return SimpleNamespace(returncode=124 if mode=='timeout' else 3)
    monkeypatch.setattr(comparison.subprocess,'run',run);comparison.execute(path)
    assert len(calls)==8
    for index in range(8):
        record=json.loads((tmp_path/f'{index}-status.json').read_text())
        assert not record['success'] and record['elapsed_seconds']>=0
    with pytest.raises(ValueError,match='Already attempted'):comparison.execute(path)


def test_plan_has_two_fresh_paired_baselines_and_balanced_order(tmp_path,monkeypatch):
    fixtures=[]
    for t in [128,1000]:
        path=tmp_path/f'f{t}.json';path.write_text(json.dumps(dict(data=dict(y=[[0.]*4]*t,x=[[0.]*4]*t,initial_positions=[[float(i)]*(t+12) for i in range(4)]),holdout=dict(y=[[0.]*4],x=[[0.]*4]))));fixtures.append(path)
    audit=tmp_path/'audit.json';audit.write_text(json.dumps(dict(status='passed',seeds=comparison.SEEDS+comparison.PREDICTIVE,hits=[],scope='bounded test')))
    python=tmp_path/'python.exe';python.write_text('dummy');attestation=tmp_path/'attestation.json';attestation.write_text('{}')
    package=tmp_path/'package';(package/'owalnuts').mkdir(parents=True)
    for name in ['__init__.py','_owalnuts.pyd']:(package/'owalnuts'/name).write_text('dummy')
    monkeypatch.setattr(comparison,'attested_dependencies',lambda *a:{})
    monkeypatch.setattr(comparison,'runtime',lambda *a:{})
    plan=comparison.create(tmp_path/'plan',python,package,attestation,fixtures,audit)
    assert not plan['frozen'] and plan['expected']==8
    assert [c['arm'] for c in plan['cells'][:4]]==list(reversed([c['arm'] for c in plan['cells'][4:]]))
    for group in [plan['cells'][:4],plan['cells'][4:]]:
        assert {c['arm'] for c in group}==set(comparison.ARMS)
        assert len({c['seed'] for c in group})==1
        assert all(c['starts']==group[0]['starts'] for c in group)
