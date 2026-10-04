import json,sys,copy
from pathlib import Path
from types import SimpleNamespace
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
from . import bank_controller as b


def streams():
 return [dict(backend=v,init_seed=1000+i,seed=2000+i,predictive_seed=132000+i) for i,v in enumerate(['public','reference','reference','public']*16)]


def test_exact_order_unique_streams_and_pilot_exclusion():
 rows=streams();pilot=dict(cells=[dict(init_seed=9,seed=19,predictive_seed=130019)])
 assert len(b.validate_streams(rows,pilot))==192
 for change in ['count','order','duplicate','pilot','prediction']:
  bad=copy.deepcopy(rows)
  if change=='count':bad.pop()
  elif change=='order':bad[0]['backend']='reference'
  elif change=='duplicate':bad[1]['init_seed']=bad[0]['seed']
  elif change=='pilot':bad[0]['init_seed']=9
  else:bad[0]['predictive_seed']+=1
  with pytest.raises(ValueError):b.validate_streams(bad,pilot)


@pytest.mark.parametrize('mode',['complete','timeout','missing'])
def test_all64_outcomes_costs_and_no_retry(tmp_path,monkeypatch,mode):
 cells=[dict(id=f'bank-{i:02d}',out=str(tmp_path/f'bank-{i:02d}')) for i in range(64)]
 plan=dict(frozen=True,expected=64,total_seconds=21600,per_fit_seconds=1800,cleanup_reserve_seconds=15,cells=cells,posterior_sha256='target',python='mock',pythonpath='mock',study='mock')
 path=tmp_path/'plan.json';path.write_text(json.dumps(plan));calls=[]
 monkeypatch.setattr(b,'verify_frozen',lambda *a:plan);monkeypatch.setattr(b,'validate_outputs',lambda *a:None)
 def run(args,**kwargs):
  calls.append(args);cid=args[-1];out=tmp_path/cid;out.mkdir();rc=124 if mode=='timeout' else 0;hp=args[args.index('--record')+1]
  b.save(hp,dict(command=args[args.index('--')+1:],returncode=rc,job_active_processes_after_cleanup=0,realized_cpus=[0],enforced_before_worker_launch=True,containment=dict(kind='windows-job-object',assigned_before_worker_execution=True),status='worker-timeout' if mode=='timeout' else 'completed',elapsed_seconds=1800))
  if mode!='missing':b.save(out/'resource-result.json',dict(status='resource_completed'))
  return SimpleNamespace(returncode=rc)
 monkeypatch.setattr(b.subprocess,'run',run);b.execute(path)
 terminal=b.load(tmp_path/'terminal.json');assert terminal['expected']==terminal['recorded']==len(calls)==64
 assert all(b.load(tmp_path/(c['id']+'-status.json'))['elapsed_seconds']>=0 for c in cells)
 with pytest.raises(ValueError):b.execute(path)
 assert len(calls)==64


def test_exhausted_global_cap_preserves64_unattempted(tmp_path,monkeypatch):
 cells=[dict(id=f'bank-{i:02d}',out=str(tmp_path/f'bank-{i:02d}')) for i in range(64)]
 plan=dict(frozen=True,expected=64,total_seconds=21600,per_fit_seconds=1800,cleanup_reserve_seconds=15,cells=cells)
 path=tmp_path/'plan.json';path.write_text(json.dumps(plan));monkeypatch.setattr(b,'verify_frozen',lambda *a:plan)
 times=iter([0,21600]);monkeypatch.setattr(b.time,'perf_counter',lambda:next(times,21600));monkeypatch.setattr(b.subprocess,'run',lambda *a,**k:pytest.fail('Deadline exhausted'))
 b.execute(path)
 assert b.load(tmp_path/'terminal.json')['recorded']==64
 assert all(b.load(tmp_path/(c['id']+'-status.json'))['status']=='unattempted_global_budget' for c in cells)


@pytest.mark.parametrize('suffix',['-exit.json','-started.json','-status.json','-hardware.json','.log',''])
def test_existing_artifact_prevents_any_worker(tmp_path,monkeypatch,suffix):
 cells=[dict(id=f'bank-{i:02d}',out=str(tmp_path/f'bank-{i:02d}')) for i in range(64)]
 plan=dict(frozen=True,expected=64,total_seconds=21600,cells=cells);path=tmp_path/'plan.json';path.write_text(json.dumps(plan));old=tmp_path/('bank-00'+suffix)
 if suffix:old.write_text('{}')
 else:old.mkdir()
 monkeypatch.setattr(b.subprocess,'run',lambda *a,**k:pytest.fail('No retry'))
 with pytest.raises(ValueError,match='Never retry'):b.execute(path)


def test_actual_cli_help_and_string_path_admission(tmp_path):
 import subprocess,os
 env=dict(os.environ,PYTHONPATH=str(Path(__file__).resolve().parent.parent))
 script=Path(__file__).parent/'bank_controller.py'
 help_result=subprocess.run([sys.executable,'-m','posterior_resource.bank_controller','--help'],env=env,capture_output=True,text=True,timeout=30)
 assert help_result.returncode==0 and 'prepare' in help_result.stdout
 path=tmp_path/'bad.json';path.write_text(json.dumps(dict(frozen=False,total_seconds=21600)))
 result=subprocess.run([sys.executable,'-m','posterior_resource.bank_controller','run',str(path)],env=env,capture_output=True,text=True,timeout=30)
 assert result.returncode!=0 and 'Explicit frozen plan required' in result.stderr and 'AttributeError' not in result.stderr
