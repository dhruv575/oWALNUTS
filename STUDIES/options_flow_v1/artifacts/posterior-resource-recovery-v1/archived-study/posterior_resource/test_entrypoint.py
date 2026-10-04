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
