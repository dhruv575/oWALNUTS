"""Queued reporter-only contracts; all reports mocked, no samplers."""
import json
from pathlib import Path
import pytest
import asof_rolling_report as r


def artifacts(tmp_path,monkeypatch,success=True):
    panel=tmp_path/'panel.json';panel.write_text('{}');fixture=tmp_path/'fixture.json';fixture.write_text('{}')
    cells=[]
    for origin in r.ORIGINS:
        for arm in r.ARMS:
            cid=f'{origin}-{arm}';public=arm.startswith('public')
            c=dict(id=cid,origin=origin,comparison_arm=arm,arm='owalnuts_continuation' if public else 'numpyro_continuation',fixture=str(fixture),fixture_sha256=r.sha(fixture))
            cells.append(c);out=tmp_path/cid;out.mkdir()
            rp=out/('python-pymc-flow-report.json' if public else 'report.json')
            rp.write_text(json.dumps(dict(status='completed',evaluation=dict(forecast=dict(rows=[dict(horizon=1,group=g,lower=-1.,upper=1.) for g in range(4)])))))
            status=dict(status='completed',success=success,elapsed_seconds=2. if public else 4.,report_sha256=r.sha(rp))
            (tmp_path/(cid+'-status.json')).write_text(json.dumps(status))
    plan=dict(frozen=True,expected=32,cells=cells,panel_path=str(panel),bound_files={str(panel.resolve()):r.sha(panel)})
    path=tmp_path/'plan.json';path.write_text(json.dumps(plan));path.with_suffix('.sha256').write_text(r.sha(path))
    labels=[dict(horizon=1,group=g,observed=0. if g<2 else None,scoring_eligible=g<2,target_observed=g<2,protocol_observation_mask=g<2,phase_boundary_purged=g==2,forecast_available=True) for g in range(4)]
    monkeypatch.setattr(r,'gate',lambda *a:True)
    monkeypatch.setattr(r,'delayed_scores',lambda *a,**k:labels)
    monkeypatch.setattr(r,'delayed_join',lambda *a,**k:dict(labels=labels))
    return plan


def test_complete_denominators_pairs_and_sparse_scoring(tmp_path,monkeypatch):
    artifacts(tmp_path,monkeypatch);result=r.summarize(tmp_path,as_of_ms=999)
    assert len(result['outcomes'])==32 and len(result['paired_sampler_costs'])==16 and len(result['paired_ablation_scores'])==64
    assert all(v['reference_over_public_seconds']==2 for v in result['paired_sampler_costs'])
    assert all(v['intended_forecasts']==32 and v['eligible_observed_cells']==16 and v['scored_forecasts']==16 and v['coverage']==1 for v in result['arms'].values())
    assert not result['qualified']


def test_failures_and_unknown_costs_not_dropped_or_compared(tmp_path,monkeypatch):
    plan=artifacts(tmp_path,monkeypatch,success=False)
    (tmp_path/(plan['cells'][0]['id']+'-status.json')).unlink()
    result=r.summarize(tmp_path,as_of_ms=999)
    assert len(result['outcomes'])==32 and all(not v['success'] for v in result['outcomes'])
    assert all(v['reference_over_public_seconds'] is None for v in result['paired_sampler_costs'])
    assert sum(v['missing_cost_records'] for v in result['arms'].values())==1
    assert all(v['coverage'] is None for v in result['arms'].values())


def test_postterminal_output_mutation_is_failure(tmp_path,monkeypatch):
    plan=artifacts(tmp_path,monkeypatch);cell=plan['cells'][0]
    (tmp_path/cell['id']/'python-pymc-flow-report.json').write_text('{}')
    result=r.summarize(tmp_path,as_of_ms=999)
    assert not result['outcomes'][0]['success'] and 'changed' in result['outcomes'][0]['validation_error']
    assert result['paired_sampler_costs'][0]['reference_over_public_seconds'] is None

@pytest.mark.parametrize('public',[True,False])
def test_identity_wrong_completed_output_is_never_scored(tmp_path,monkeypatch,public):
    import asof_rolling_protocol as protocol
    plan=artifacts(tmp_path,monkeypatch);cell=plan['cells'][0 if public else 1]
    # Use the real identity-bound join, keeping only delayed label lookup mocked.
    monkeypatch.setattr(r,'delayed_join',protocol.delayed_join)
    fixture=dict(provenance=dict(origin_index=cell['origin']))
    fp=Path(cell['fixture']);fp.write_text(json.dumps(fixture))
    for c in plan['cells']:
        c.update(fixture_sha256=r.sha(fp),seed=50,predictive_seed=130050,forecast_cells=[[1,g] for g in range(4)])
    path=tmp_path/'plan.json';path.write_text(json.dumps(plan));path.with_suffix('.sha256').write_text(r.sha(path))
    rp=tmp_path/cell['id']/('python-pymc-flow-report.json' if public else 'report.json')
    report=json.loads(rp.read_text());report.update(seed=50,predictive_seed=130050,arm='python-pymc-masked-flow-noncentered-continuation',model='masked-flow',bindings={str(fp.resolve()):'another-origin-fixture-hash'},
        plan=dict(arm='numpyro-masked-noncentered-continuation',model='masked_flow',fixture_sha256='another-origin-fixture-hash',predictive_seed=130050))
    rp.write_text(json.dumps(report));sp=tmp_path/(cell['id']+'-status.json');status=json.loads(sp.read_text());status['report_sha256']=r.sha(rp);sp.write_text(json.dumps(status))
    result=r.summarize(tmp_path,as_of_ms=999);item=next(x for x in result['outcomes'] if x['id']==cell['id'])
    assert not item['success'] and 'validation_error' in item
    assert all(f['covered'] is None and f['interval_score'] is None for f in item['forecasts'])


def test_missing_purged_and_failure_labels_have_separate_counts(tmp_path,monkeypatch):
    plan=artifacts(tmp_path,monkeypatch,success=False)
    result=r.summarize(tmp_path,as_of_ms=999)
    for arm in result['arms'].values():
        assert arm['eligible_observed_cells']==16 and arm['missing_or_purged_cells']==16
        assert arm['unknown_label_eligibility_cells']==0 and arm['scored_forecasts']==0
        assert arm['failed_or_unverified_fits']==8



def test_coverage_conditioning_and_unconditional_usable_counts(tmp_path,monkeypatch):
    plan=artifacts(tmp_path,monkeypatch)
    sp=tmp_path/(plan['cells'][0]['id']+'-status.json');status=json.loads(sp.read_text());status['success']=False;sp.write_text(json.dumps(status))
    result=r.summarize(tmp_path,as_of_ms=999);a=result['arms']['public-flow']
    assert a['coverage']==1 and 'Conditional' in a['coverage_scope']
    assert a['usable_and_covering_count']==14
    assert a['usable_and_covering_over_all_intended']==14/32
    assert a['usable_and_covering_over_eligible_observed']==14/16


def test_report_preserves_unavailable_anchor_covariate_and_future_missing(tmp_path,monkeypatch):
    plan=artifacts(tmp_path,monkeypatch)
    labels=[dict(horizon=1,group=g,observed=.0 if g==0 else None,scoring_eligible=g==0,target_observed=g==0,
        protocol_observation_mask=g==0,phase_boundary_purged=False,forecast_available=g in [0,3],anchor_available=g!=1,
        feature_available=g!=2,future_outcome_unobserved=g==3) for g in range(4)]
    monkeypatch.setattr(r,'delayed_scores',lambda *a,**k:labels)
    monkeypatch.setattr(r,'delayed_join',lambda *a,**k:dict(labels=labels))
    for c in plan['cells']:
        out=tmp_path/c['id']/('python-pymc-flow-report.json' if c['arm']=='owalnuts_continuation' else 'report.json')
        report=json.loads(out.read_text())
        for row in report['evaluation']['forecast']['rows']:
            if row['group'] in [1,2]:row.update(lower=None,upper=None)
        out.write_text(json.dumps(report));sp=tmp_path/(c['id']+'-status.json');status=json.loads(sp.read_text());status['report_sha256']=r.sha(out);sp.write_text(json.dumps(status))
    result=r.summarize(tmp_path,as_of_ms=999)
    for a in result['arms'].values():
        assert a['known_anchor_cells']==24 and a['missing_anchor_cells']==8
        assert a['missing_covariate_cells']==8 and a['future_unobserved_cells']==8
        assert a['scored_forecasts']==8 and a['usable_and_covering_over_all_intended']==8/32
    assert result['outcomes'][0]['forecasts'][1]['forecast_usable'] is False
