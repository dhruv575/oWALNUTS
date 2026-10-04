import json,hashlib,zipfile,copy
from pathlib import Path
import pytest
from recover import verify_archive
from adapter import validate_report


def archive_fixture(tmp_path):
    root=tmp_path/'sources';root.mkdir();source=root/'helper.py';source.write_text('value=1\n');digest=hashlib.sha256(source.read_bytes()).hexdigest();original=tmp_path/'original/helper.py'
    archive=tmp_path/'source.zip'
    with zipfile.ZipFile(archive,'w') as z:z.writestr('study/helper.py',source.read_bytes())
    plan=tmp_path/'plan.json';plan.write_text(json.dumps(dict(bindings={str(original):digest})))
    return dict(archived_study_directory=str(root),original_plan=str(plan),source_archive=str(archive),source_manifest={'study/helper.py':dict(extracted=str(source),original=str(original),sha256=digest)})


def test_archive_correspondence_and_extra_source_rejected(tmp_path):
    spec=archive_fixture(tmp_path);verify_archive(spec)
    (Path(spec['archived_study_directory'])/'extra.py').write_text('')
    with pytest.raises(ValueError,match='inventory'):verify_archive(spec)


def test_archive_source_tamper_rejected(tmp_path):
    spec=archive_fixture(tmp_path);Path(spec['source_manifest']['study/helper.py']['extracted']).write_text('value=2')
    with pytest.raises(ValueError,match='mismatch'):verify_archive(spec)


def test_archive_escape_rejected(tmp_path):
    spec=archive_fixture(tmp_path);spec['source_manifest']['study/helper.py']['extracted']=str(tmp_path/'escape.py')
    with pytest.raises(ValueError,match='escapes'):verify_archive(spec)


def test_no_sampling_entrypoints_imported_or_called():
    import ast
    tree=ast.parse((Path(__file__).parent/'recover.py').read_text())
    names=[node.module or '' for node in ast.walk(tree) if isinstance(node,ast.ImportFrom)]
    assert not any(x in names for x in ['pymc_flow_continuation_workflow','mixed_flow_reference','numpyro','pymc','owalnuts'])
    calls=[node.func.attr for node in ast.walk(tree) if isinstance(node,ast.Call) and isinstance(node.func,ast.Attribute)]
    assert not set(calls)&{'sample','warmup','adapt','draw'}


@pytest.mark.parametrize('mode',['failed','timeout','missing_hardware'])
def test_launch_retains_exit_cost_and_no_retry(tmp_path,monkeypatch,mode):
    import launch,recover,sys,types
    out=tmp_path/'out';spec=dict(out=str(out),python='mock',archived_study_directory=str(tmp_path),memory_bytes=8*1024**3,timeout_seconds=1800,launcher_inputs={},cell_id='fit-0-public',original_status='original')
    path=tmp_path/'spec.json';path.write_text(json.dumps(spec));path.with_suffix('.sha256').write_text(launch.sha(path))
    monkeypatch.setitem(sys.modules,'asof_rolling_execute',types.SimpleNamespace(validate_hardware=lambda *a:None))
    monkeypatch.setattr(recover,'verify',lambda s:None)
    calls=[]
    def run(args,**kwargs):
        calls.append(args);rc=124 if mode=='timeout' else 2
        if mode!='missing_hardware':
            hp=Path(args[args.index('--record')+1]);hp.write_text(json.dumps(dict(command=args[args.index('--')+1:],returncode=rc,job_active_processes_after_cleanup=0,realized_cpus=[0],containment=dict(assigned_before_worker_execution=True),status='worker-timeout' if mode=='timeout' else 'worker-failed',elapsed_seconds=1800)))
            if mode=='failed':
                out.mkdir();(out/'recovery-result.json').write_text(json.dumps(dict(status='failed',cell_id='fit-0-public',posthoc=True,resampled=False)))
        return types.SimpleNamespace(returncode=rc)
    monkeypatch.setattr(launch.subprocess,'run',run)
    record=launch.launch(path)
    assert record['additional_outer_seconds']>=0 and Path(str(out)+'-exit.json').exists()
    assert record['status']==('budgeted_timeout' if mode=='timeout' else 'failed')
    with pytest.raises(ValueError):launch.launch(path)
    assert len(calls)==1


def test_two_cell_global_budget_preserves_denominator(tmp_path,monkeypatch):
    import cohort
    specs=[]
    for i in [0,3]:
        path=tmp_path/f'spec{i}.json';path.write_text(json.dumps(dict(cell_id=f'fit-{i}-public',out=str(tmp_path/f'fit{i}'))));specs.append(str(path))
    plan=tmp_path/'cohort.json';plan.write_text(json.dumps(dict(total_seconds=3600,cleanup_reserve_seconds=15,specs=specs,spec_hashes={p:cohort.sha(p) for p in specs})));plan.with_suffix('.sha256').write_text(cohort.sha(plan))
    values=iter([0,3600,3600,3600]);monkeypatch.setattr(cohort.time,'perf_counter',lambda:next(values,3600))
    monkeypatch.setattr(cohort,'launch',lambda *a:pytest.fail('Budget exhausted before launch'))
    cohort.run(plan)
    terminal=json.loads((tmp_path/'recovery-terminal.json').read_text())
    assert terminal['recorded']==2 and all(r['status']=='unattempted_global_budget' for r in terminal['results'])


def test_actual_contained_recovery_cli_rejects_before_analysis(tmp_path):
    import os,subprocess,sys
    if os.name!='nt':pytest.skip('Windows job protocol')
    study=Path(__file__).resolve().parents[2]/'STUDIES/options_flow_v1'
    spec=tmp_path/'spec.json';out=tmp_path/'out';hardware=tmp_path/'hardware.json'
    spec.write_text(json.dumps(dict(out=str(out),archived_study_directory=str(study),cell_id='fit-0-public',memory_bytes=1,timeout_seconds=1800)))
    args=[sys.executable,str(study/'hardware_control.py'),'--cpus','0','--record',str(hardware),'--timeout','30','--',sys.executable,str(Path(__file__).parent/'recover.py'),'--spec',str(spec)]
    result=subprocess.run(args,cwd=study,capture_output=True,text=True,timeout=45)
    assert result.returncode==2,result.stderr
    h=json.loads(hardware.read_text());r=json.loads((out/'recovery-result.json').read_text())
    assert h['job_active_processes_after_cleanup']==0 and h['realized_cpus']==[0]
    assert h['containment']['assigned_before_worker_execution'] is True
    assert r['status']=='failed' and 'resource policy' in r['error'] and r['resampled'] is False
    assert r['additional_worker_seconds_before_final_report']>0 and not (out/'extracted').exists()
