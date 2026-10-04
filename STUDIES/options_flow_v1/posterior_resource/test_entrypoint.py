"""Actual module subprocess boundaries, without sampling or applying OS limits."""
import json,os,subprocess,sys
from pathlib import Path

STUDY=Path(__file__).resolve().parent.parent


def invoke(module,*args):
    return subprocess.run([sys.executable,'-m',module,*map(str,args)],cwd=STUDY,
        env=dict(os.environ,PYTHONPATH=str(STUDY)),capture_output=True,text=True,timeout=30)


def test_controller_cli_string_path_reaches_policy_guard(tmp_path):
    path=tmp_path/'unfrozen.json';path.write_text(json.dumps(dict(frozen=False,total_seconds=7200)))
    result=invoke('posterior_resource.controller','run',path)
    assert result.returncode!=0
    assert 'Explicit frozen plan required' in result.stderr
    assert 'AttributeError' not in result.stderr


def test_worker_cli_string_path_failure_has_charged_terminal_record(tmp_path):
    out=tmp_path/'cell';plan=tmp_path/'plan.json'
    plan.write_text(json.dumps(dict(study=str(STUDY),posterior_sha256='fixture',memory_bytes=1,
        cells=[dict(id='cell',backend='public',out=str(out))])))
    result=invoke('posterior_resource.resource_worker','--plan',plan,'--cell','cell')
    assert result.returncode==2,result.stderr
    report=json.loads((out/'resource-result.json').read_text())
    assert report['status']=='failed' and 'Unexpected memory policy' in report['error']
    assert report['worker_seconds_before_final_report']>0
    assert report['last_phase']=='admission'
    assert report['process_cpu_seconds_before_final_report']>=0
    assert report['resources']['measurement']
    assert not (out/'fit').exists()


def test_both_actual_module_help_entrypoints():
    for module in ['posterior_resource.controller','posterior_resource.resource_worker']:
        result=invoke(module,'--help')
        assert result.returncode==0,result.stderr
        assert 'usage:' in result.stdout


def test_contained_actual_worker_admission_failure(tmp_path):
    if os.name!='nt':
        import pytest
        pytest.skip('This resource protocol requires Windows job containment')
    out=tmp_path/'contained';plan=tmp_path/'plan.json';hardware=tmp_path/'hardware.json'
    plan.write_text(json.dumps(dict(study=str(STUDY),posterior_sha256='fixture',memory_bytes=1,
        cells=[dict(id='cell',backend='public',out=str(out))])))
    args=[sys.executable,str(STUDY/'hardware_control.py'),'--cpus','0','--record',str(hardware),'--timeout','30','--',
        sys.executable,'-m','posterior_resource.resource_worker','--plan',str(plan),'--cell','cell']
    result=subprocess.run(args,cwd=STUDY,env=dict(os.environ,PYTHONPATH=str(STUDY)),capture_output=True,text=True,timeout=45)
    assert result.returncode==2,result.stderr
    h=json.loads(hardware.read_text())
    assert h['command']==args[args.index('--')+1:]
    assert h['returncode']==2 and h['job_active_processes_after_cleanup']==0
    assert h['realized_cpus']==[0] and h['containment']['assigned_before_worker_execution'] is True
    r=json.loads((out/'resource-result.json').read_text())
    assert r['status']=='failed' and 'Unexpected memory policy' in r['error']
    assert not (out/'fit').exists()


def test_contained_bank_phase_routes_only_to_exact_bank_verifier(tmp_path):
    if os.name!='nt':
        import pytest
        pytest.skip('Windows job protocol')
    import hashlib
    out=tmp_path/'bank';plan=tmp_path/'plan.json';intent=tmp_path/'intent.json';hardware=tmp_path/'hardware.json'
    # Valid freeze envelope, deliberately invalid bank qualification flag.
    body=dict(frozen=False,phase='prospective_reference_bank',qualified=True,study=str(STUDY),posterior_sha256='fixture',memory_bytes=8*1024**3,cells=[dict(id='bank-00-public',backend='public',out=str(out))])
    intent.write_text(json.dumps(body));body.update(frozen=True,intent_sha256=hashlib.sha256(intent.read_bytes()).hexdigest())
    plan.write_text(json.dumps(body));plan.with_suffix('.sha256').write_text(hashlib.sha256(plan.read_bytes()).hexdigest())
    args=[sys.executable,str(STUDY/'hardware_control.py'),'--cpus','0','--record',str(hardware),'--timeout','30','--',sys.executable,'-m','posterior_resource.resource_worker','--plan',str(plan),'--cell','bank-00-public']
    result=subprocess.run(args,cwd=STUDY,env=dict(os.environ,PYTHONPATH=str(STUDY)),capture_output=True,text=True,timeout=45)
    assert result.returncode==2,result.stderr
    h=json.loads(hardware.read_text());r=json.loads((out/'resource-result.json').read_text())
    assert h['job_active_processes_after_cleanup']==0 and h['realized_cpus']==[0]
    assert h['containment']['assigned_before_worker_execution'] is True
    assert r['status']=='failed' and r['last_phase']=='admission'
    assert 'Explicit nonqualified bank phase required' in r['error']
    assert r['memory_cap_bytes']==8*1024**3 and r['worker_seconds_before_final_report']>0
    assert not (out/'fit').exists()
