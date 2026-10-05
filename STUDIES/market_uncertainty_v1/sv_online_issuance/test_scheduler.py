import json
from types import SimpleNamespace
import pytest
import scheduler


def setup(tmp_path):
    capture = tmp_path/'capture'; capture.mkdir()
    first = 1000
    (capture/'receipts.jsonl').write_text(json.dumps({'receipt_monotonic_ns':first})+'\n')
    origins = [first+scheduler.WINDOW+i*scheduler.HORIZON for i in range(3)]
    cfg = dict(bindings={}, origin_streams={str(o):dict(initialization_seed=10+3*i,
               sampler_seed=11+3*i,predictive_seed=12+3*i) for i,o in enumerate(origins)})
    return capture, origins, cfg


def test_missed_origins_never_replayed_and_each_seed_role_used(tmp_path, monkeypatch):
    capture, origins, cfg = setup(tmp_path); now=[origins[0]+scheduler.LAG+1]; calls=[]
    monkeypatch.setattr(scheduler.shutil,'disk_usage',lambda p:SimpleNamespace(free=100*1024**3))
    def issue(capture,out,origin,config):
        calls.append((origin,config['sampler_seed'])); out.mkdir()
        result=dict(status='issued_no_forecast',reason='insufficient_mature_history')
        (out/'issuance.json').write_text(json.dumps(result)); return result
    def sleep(seconds):now[0]+=int(seconds*1e9)
    result=scheduler.run(capture,tmp_path/'run',cfg,capture_end_ns=origins[-1]+scheduler.HORIZON,
                         clock=lambda:now[0],utc=lambda:1,sleep=sleep,issue_fn=issue)
    assert result['expected']==3 and result['outcomes'][0]['reason']=='missed_origin'
    assert calls==[(origins[1],14),(origins[2],17)]
    assert all(row['issuance_sha256']==scheduler.digest(row['path']) for row in result['outcomes'])


def test_terminal_capture_preserves_entire_denominator(tmp_path):
    capture,origins,cfg=setup(tmp_path);(capture/'summary.json').write_text('{}')
    result=scheduler.run(capture,tmp_path/'run',cfg,capture_end_ns=origins[-1]+scheduler.HORIZON,
                         clock=lambda:origins[0],utc=lambda:1,
                         issue_fn=lambda *a:pytest.fail('Must not issue'))
    assert len(result['outcomes'])==3
    assert all(r['reason']=='capture_terminated' for r in result['outcomes'])


def test_worker_exception_preserves_original_record_and_latches(tmp_path,monkeypatch):
    capture,origins,cfg=setup(tmp_path)
    monkeypatch.setattr(scheduler.shutil,'disk_usage',lambda p:SimpleNamespace(free=100*1024**3))
    def issue(capture,out,origin,config):
        out.mkdir();(out/'issuance.json').write_text('{"status":"not_issued"}')
        raise OSError('storage error after record')
    result=scheduler.run(capture,tmp_path/'run',cfg,capture_end_ns=origins[-1]+scheduler.HORIZON,
                         clock=lambda:origins[0]+3_000_000_000,utc=lambda:1,issue_fn=issue)
    assert result['outcomes'][0]['path'].endswith('scheduler-error.json')
    assert all(r['reason']=='scheduler_error' for r in result['outcomes'])
    assert json.loads((tmp_path/'run'/str(origins[0])/'issuance.json').read_text())=={'status':'not_issued'}


def test_reused_stream_rejected_before_launch(tmp_path):
    capture,origins,cfg=setup(tmp_path)
    cfg['origin_streams'][str(origins[1])]['sampler_seed']=11
    with pytest.raises(ValueError,match='Distinct'):
        scheduler.run(capture,tmp_path/'run',cfg,capture_end_ns=origins[-1]+scheduler.HORIZON)


@pytest.mark.parametrize('reason,latch',[
    ('Worker containment failed', 'worker_containment_failure'),
    ('Actual native runtime differs', 'worker_provenance_failure'),
])
def test_unsafe_worker_result_latches_remaining_origins(tmp_path, monkeypatch, reason, latch):
    capture, origins, cfg = setup(tmp_path); calls=[]
    monkeypatch.setattr(scheduler.shutil,'disk_usage',lambda p:SimpleNamespace(free=100*1024**3))
    def issue(capture,out,origin,config):
        calls.append(origin);out.mkdir()
        result=dict(status='not_issued',reason=reason)
        (out/'issuance.json').write_text(json.dumps(result));return result
    result=scheduler.run(capture,tmp_path/'run',cfg,capture_end_ns=origins[-1]+scheduler.HORIZON,
                         clock=lambda:origins[0]+3_000_000_000,utc=lambda:1,issue_fn=issue)
    assert calls==[origins[0]]
    assert all(row['reason']==latch for row in result['outcomes'][1:])
