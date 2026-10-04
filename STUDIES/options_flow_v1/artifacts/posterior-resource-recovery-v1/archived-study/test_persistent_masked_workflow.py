"""Queued persistent A/B/A actual-worker checks; no execution during timing holds."""
import copy
import json
import numpy as np
import pytest


def fixtures(tmp_path):
    data=dict(y=[[.1]*4,[0.]*4,[.2]*4],x=[[.2]*4,[0.]*4,[-.1]*4],observation_mask=[[True]*4,[False]*4,[True]*4],grid_index=[0,1,2],rho=.8,nu=5.)
    a=dict(data=data,precision_family=[[1,0]],holdout=dict(x=[[.3]*4],y=[[None]*4],x_available=[[True,False,False,False]],observation_mask=[[False]*4],grid_index=[3]))
    b=copy.deepcopy(a);b['precision_family']=[[1,1]];b['holdout']['x_available']=[[False,True,False,False]];b['data']['observation_mask'][1]=[True]*4;b['data']['y'][1]=[-.3]*4;b['data']['x'][1]=[.6]*4
    paths=[]
    for i,f in enumerate([a,b,a]):
        path=tmp_path/f'fixture-{i}.json';path.write_text(json.dumps(f));paths.append(path)
    return paths


@pytest.mark.parametrize('backend',['pymc','numpyro'])
def test_actual_fresh_adaptation_a_b_a_density_starts_costs(tmp_path,backend):
    from persistent_masked_workflow import execute
    from continuation_comparison import sha
    paths=fixtures(tmp_path);out=tmp_path/'out'
    reports=execute(paths,out,[731,732,733],backend,warmup=12,tiers=(8,),batch=8)
    assert len(reports)==3 and all(r['status']=='completed' for r in reports),[r.get('error') for r in reports]
    assert all(r['precision_pass'] is False for r in reports)  # Short draws cannot qualify.
    assert [r['observed_count'] for r in reports]==[8,12,8]
    assert [r['forecast_cells'] for r in reports]==[[[1,0]],[[1,1]],[[1,0]]]
    np.testing.assert_array_equal(reports[0]['common_gradient'],reports[2]['common_gradient'])
    assert reports[0]['common_logp']==reports[2]['common_logp']
    assert reports[0]['common_logp']!=reports[1]['common_logp']
    for i,r in enumerate(reports):
        assert r['fresh_adaptation'] and not r['posterior_continuation']
        assert r['seed']==731+i and r['predictive_seed']==130731+i
        assert r['fixture_sha256']==sha(paths[i]) and r['bindings']
        assert r['initial_positions']==reports[0]['initial_positions']
        assert r['sampling_initial_positions']==reports[0]['sampling_initial_positions']
        assert r['fit_seconds_before_final_report_write']>0 and r['parity_seconds']>=0
        assert r['evaluation']['forecast']['scored_cells']==0
        assert len(r['evaluation']['functionals'])==14 and len(r['evaluation']['canonical_parameter_diagnostics'])==15
        assert r['evaluation']['forecast']['scheduled_cells']==4 and r['evaluation']['forecast']['available_forecast_cells']==1
        for row in r['evaluation']['forecast']['rows']:
            if not row['forecast_available']:assert all(row[k] is None for k in ['lower','upper','width','endpoint_mcse'])
        if backend=='pymc':
            assert r['native_parity']['passed'] and r['compile_seconds']>=0
            assert r['session_progress_before_close']['completed_transitions']==[20]*4
            assert r['total_target_calls']==r['session_progress_before_close']['target_calls']
        else:
            assert r['warmup_admission']['previous_posterior_state_cleared']
            assert r['warmup_iterations']==[12]*4
            assert r['checkpoints'][0]['start_iterations']==[12]*4
            assert r['checkpoints'][0]['end_iterations']==[20]*4
    cohort=json.loads((out/'cohort.json').read_text())
    assert len(cohort['fit_costs'])==3
    for i,cost in enumerate(cohort['fit_costs']):
        assert cost['report_sha256']==sha(out/f'fit-{i}'/'report.json')
        assert cost['fit_seconds_including_final_report_write']>=reports[i]['fit_seconds_before_final_report_write']
        assert cost['final_report_write_seconds']>=0
    assert cohort['execute_seconds_before_cohort_write']>=sum(c['fit_seconds_including_final_report_write'] for c in cohort['fit_costs'])


def test_failed_native_parity_never_starts_sampler_and_costs_retained(tmp_path,monkeypatch):
    import persistent_masked_workflow as worker
    import pymc_flow_continuation_workflow as target_worker
    paths=fixtures(tmp_path)
    monkeypatch.setattr(target_worker,'compile_target',lambda *a:(object(),{'mock':True}))
    monkeypatch.setattr(target_worker,'parity',lambda *a,**k:{'passed':False})
    monkeypatch.setattr(worker,'run_session',lambda *a,**k:pytest.fail('No admission after failed parity'))
    reports=worker.execute(paths,tmp_path/'out',[741,742,743],'pymc',warmup=12,tiers=(8,),batch=8)
    assert len(reports)==3 and all(r['status']=='failed' and not r['precision_pass'] for r in reports)
    assert all('parity failed' in r['error'] and r['fit_seconds_before_final_report_write']>0 for r in reports)
    assert len(json.loads((tmp_path/'out'/'cohort.json').read_text())['fit_costs'])==3


def test_empty_or_mismatched_forecast_family_rejected_before_output(tmp_path):
    from persistent_masked_workflow import execute
    paths=fixtures(tmp_path)
    for path in [paths[0],paths[2]]:
        f=json.loads(path.read_text());f['holdout']['x_available']=[[False]*4];f['precision_family']=[];path.write_text(json.dumps(f))
    with pytest.raises(ValueError,match='At least one'):
        execute(paths,tmp_path/'out',[751,752,753],'numpyro',warmup=12,tiers=(8,),batch=8)
    assert not (tmp_path/'out').exists()
