import json
from types import SimpleNamespace
import pytest
from . import controller as c


def setup(tmp_path,monkeypatch,mode):
    cells=[dict(id=f'fit-{i}',out=str(tmp_path/f'fit-{i}')) for i in range(4)]
    p=dict(frozen=True,expected=4,cells=cells,total_seconds=7200,cleanup_reserve_seconds=15,per_fit_seconds=1800,python='mock',pythonpath='mock',study='mock',posterior_sha256='fixed')
    path=tmp_path/'plan.json';path.write_text(json.dumps(p));path.with_suffix('.sha256').write_text(c.sha(path))
    monkeypatch.setattr(c,'validate',lambda *a:None)
    monkeypatch.setattr(c,'verify_frozen',lambda *a:(c.validate(p,tmp_path),p)[1])
    monkeypatch.setattr(c,'validate_outputs',lambda *a:None);calls=[]
    def run(args,**kwargs):
        cid=args[-1];calls.append(cid);hp=args[args.index('--record')+1:][0];timeout=float(args[args.index('--timeout')+1]);out=tmp_path/cid;out.mkdir()
        rc=124 if mode=='timeout' else 0
        h=dict(command=args[args.index('--')+1:],returncode=rc,job_active_processes_after_cleanup=0,realized_cpus=[0],enforced_before_worker_launch=True,containment=dict(kind='windows-job-object',assigned_before_worker_execution=True),status='worker-timeout' if mode=='timeout' else 'completed',elapsed_seconds=timeout)
        c.save(hp,h)
        if mode!='missing':c.save(out/'resource-result.json',dict(status='resource_completed',resources={'peak_committed_bytes':1000}))
        return SimpleNamespace(returncode=rc)
    monkeypatch.setattr(c.subprocess,'run',run)
    return path,p,calls


@pytest.mark.parametrize('mode,status',[('completed','resource_completed'),('timeout','budgeted_timeout'),('missing','worker_or_validation_failed')])
def test_allfour_outcomes_costs_no_retry(tmp_path,monkeypatch,mode,status):
    path,p,calls=setup(tmp_path,monkeypatch,mode);c.execute(path)
    reports=[c.load(tmp_path/(r['id']+'-status.json')) for r in p['cells']]
    assert len(calls)==len(reports)==4 and all(r['status']==status and r['elapsed_seconds']>=0 for r in reports)
    assert c.load(tmp_path/'terminal.json')['recorded']==4
    with pytest.raises(ValueError):c.execute(path)
    assert len(calls)==4


def test_source_abort_and_global_budget_keep_four(tmp_path,monkeypatch):
    path,p,calls=setup(tmp_path,monkeypatch,'completed')
    def drift(*a):raise ValueError('Source drift')
    monkeypatch.setattr(c,'validate',drift);c.execute(path)
    assert not calls and all(c.load(tmp_path/(r['id']+'-status.json'))['status']=='unattempted_provenance_abort' for r in p['cells'])


def test_cleanup_reserve_prevents_launch(tmp_path,monkeypatch):
    path,p,calls=setup(tmp_path,monkeypatch,'completed');times=iter([0,7200,7200,7200,7200,7200,7200,7200,7200,7200,7200,7200,7200,7200,7200,7200])
    monkeypatch.setattr(c.time,'perf_counter',lambda:next(times,7200));c.execute(path)
    assert not calls and all(c.load(tmp_path/(r['id']+'-status.json'))['status']=='unattempted_global_budget' for r in p['cells'])


def test_seed_independence_and_fixed_order():
    rows=[dict(backend=b,init_seed=100+i,seed=200+i,predictive_seed=130200+i) for i,b in enumerate(['public','reference','reference','public'])]
    assert len(c.validate_streams(rows))==12
    rows[3]['init_seed']=rows[0]['init_seed']
    with pytest.raises(ValueError):c.validate_streams(rows)


@pytest.mark.parametrize('suffix',['-exit.json','-started.json','-status.json','-hardware.json','.log',''])
def test_existing_artifact_never_retried(tmp_path,monkeypatch,suffix):
    path,p,calls=setup(tmp_path,monkeypatch,'completed')
    existing=tmp_path/(p['cells'][0]['id']+suffix)
    if suffix:existing.write_text('{}')
    else:existing.mkdir()
    with pytest.raises(ValueError):c.execute(path)
    assert not calls


def test_frozen_sidecar_and_original_digest_independent(tmp_path,monkeypatch):
    intent=dict(frozen=False,policy='fixed',cells=[])
    c.save(tmp_path/'intent.json',intent)
    plan=dict(intent,frozen=True,intent_sha256=c.sha(tmp_path/'intent.json'))
    path=tmp_path/'plan.json';c.save(path,plan);digest=c.sha(path)
    path.with_suffix('.sha256').write_text(digest)
    monkeypatch.setattr(c,'validate',lambda *a:None)
    assert c.verify_frozen(path,digest)==plan
    plan['policy']='changed';path.write_text(json.dumps(plan))
    path.with_suffix('.sha256').write_text(c.sha(path))
    with pytest.raises(ValueError,match='digest'):c.verify_frozen(path,digest)
    with pytest.raises(ValueError,match='intent'):c.verify_frozen(path)


@pytest.mark.parametrize('field,value',[
    ('status','invented'),('cell_id','wrong'),('backend','wrong'),('posterior_sha256','wrong'),
    ('qualified',True),('memory_cap_bytes',1),
    ('process_cpu_seconds_before_final_report',float('nan')),
    ('worker_seconds_before_final_report',-1),
    ('resources',{'measurement':'mock','peak_committed_bytes':True}),
])
def test_result_identity_and_resources_rejected(tmp_path,field,value):
    cell=dict(id='fit',backend='public',out=str(tmp_path))
    plan=dict(posterior_sha256='posterior',memory_bytes=8*1024**3)
    result=dict(status='failed',cell_id='fit',backend='public',posterior_sha256='posterior',qualified=False,
        memory_cap_bytes=8*1024**3,process_cpu_seconds_before_final_report=1.,worker_seconds_before_final_report=2.,
        resources={'measurement':'process','peak_committed_bytes':1000})
    c.validate_outputs(plan,cell,result)
    result[field]=value
    with pytest.raises(ValueError):c.validate_outputs(plan,cell,result)


def test_terminal_without_other_artifacts_is_immutable(tmp_path,monkeypatch):
    path,p,calls=setup(tmp_path,monkeypatch,'completed')
    (tmp_path/'terminal.json').write_text('{}')
    with pytest.raises(ValueError):c.execute(path)
    assert not calls
