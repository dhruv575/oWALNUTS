"""Static authored tests; run only after the parent's timing hold ends."""
import copy
import pytest
from market_flow_features import digest_json
from asof_market_fixture import prepare,delayed_scores


def inputs():
    protocol=dict(start_utc='1970-01-01T00:00:00+00:00',selection_hours=0,contracts=4,
        forecast=dict(origin_stride_minutes=30,availability_lag_seconds=60,horizon_minutes=30,feature_bin_minutes=15))
    records=[];names=['A','B','C','D']
    for i in range(6):
        decision=i*1800000+60000
        groups=[dict(instrument_name=n,x=.2,y=.03,x_available=True,y_available=True,observation_mask=True,
            feature_available_ms=decision,target_available_ms=decision+1860000) for n in names]
        records.append(dict(grid_index=i,decision_ms=decision,cutoff_ms=decision-60000,target_end_ms=decision+1800000,
            selection_available=True,stabilizer_available=True,phase='development' if i<3 else 'validation',groups=groups))
    return dict(protocol_sha256=digest_json(protocol),acquisition_binding={'manifest_sha256':'test'},instruments=names,
        stabilizer=dict(estimated_through_ms=0,value=1e-8),records=records),protocol


def test_preserves_immature_predecessor_and_cross_phase_history():
    panel,protocol=inputs();f=prepare(panel,protocol,origin_index=4,window=3,init_seed=5)
    assert f['provenance']['original_grid_indices']==[1,2,3]
    assert f['data']['observation_mask']==[[True]*4,[True]*4,[False]*4]
    assert f['holdout']['grid_index']==[3] and f['holdout']['y']==[[None]*4]
    assert len(f['data']['initial_positions'])==4


def test_unavailable_labels_never_change_fixture_starts_or_gate():
    panel,protocol=inputs();before=prepare(panel,protocol,origin_index=4,window=3,init_seed=5)
    changed=copy.deepcopy(panel)
    for row in changed['records'][3:]:
        for g in row['groups']:g.update(y=999.,y_available=False,observation_mask=False)
    assert prepare(changed,protocol,origin_index=4,window=3,init_seed=5)==before
    with pytest.raises(ValueError):delayed_scores(before,panel,as_of_ms=before['provenance']['issuance_ms'])
    score=delayed_scores(before,panel,as_of_ms=panel['records'][4]['groups'][0]['target_available_ms'])
    assert len(score)==4 and score[0]['observed']==.03
    assert before['holdout']['y']==[[None]*4]


@pytest.mark.parametrize('mutation',[
    lambda p:p['records'][3].update(decision_ms=1),
    lambda p:p['records'][4].update(selection_available=False),
    lambda p:p['stabilizer'].update(estimated_through_ms=99999999),
    lambda p:p['records'][4]['groups'][0].update(feature_available_ms=99999999),
    lambda p:p['records'][2]['groups'][0].update(target_available_ms=0),
    lambda p:p['records'][2]['groups'][0].update(instrument_name='unexpected'),
    lambda p:p['records'].pop(2),
])
def test_time_availability_and_universe_negatives(mutation):
    panel,protocol=inputs();mutation(panel)
    with pytest.raises(ValueError):prepare(panel,protocol,origin_index=4,window=3,init_seed=5)


def test_phase_purge_retained_without_reset_and_unavailable_x_explicit():
    panel,protocol=inputs();panel['records'][2]['groups'][0]['observation_mask']=False
    panel['records'][4]['groups'][1].update(x=None,x_available=False)
    f=prepare(panel,protocol,origin_index=4,window=3,init_seed=5)
    assert not f['data']['observation_mask'][1][0]
    assert f['precision_family']==[[1,0],[1,2],[1,3]]
    assert not f['holdout']['x_available'][0][1]


def test_actual_public_and_reference_fixture_contracts():
    # Delayed import: this test is queued until the numerical timing hold ends.
    import numpy as np
    from pymc_flow_continuation_workflow import validate_fixture
    import masked_flow_reference as reference
    panel,protocol=inputs();f=prepare(panel,protocol,origin_index=4,window=3,init_seed=5)
    data,names,family=validate_fixture(f,'masked-flow')
    assert len(names)==14 and family==[(1,g) for g in range(4)]
    assert callable(reference.target(f['data']))
    starts=reference.canonical_starts(f['data'],4)
    assert starts.shape==(4,15)  # Four globals, eight group coordinates, three latent rows.
    assert np.isfinite(reference.to_noncentered(starts,f['data'])).all()
    # The reference's actual predictor validates all future masks/grid without fit.
    prediction=reference.forecast(np.repeat(starts[:,None,:],8,axis=1),f['data'],f['holdout'])
    assert prediction['available_forecast_cells']==4 and prediction['scored_cells']==0


def test_delayed_scoring_phase_eligibility_and_nonfinite_labels():
    panel,protocol=inputs();f=prepare(panel,protocol,origin_index=4,window=3,init_seed=5)
    panel['records'][4]['groups'][0].update(phase_boundary_purged=True,observation_mask=False)
    labels=delayed_scores(f,panel,as_of_ms=99999999)
    assert labels[0]['phase_boundary_purged'] and not labels[0]['scoring_eligible']
    assert labels[0]['observed'] is None and labels[0]['target_observed']
    panel['records'][4]['groups'][1]['y']=float('nan')
    with pytest.raises(ValueError):delayed_scores(f,panel,as_of_ms=99999999)
