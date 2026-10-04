"""Authored during live dense timing; run only after the coordinated quiet window."""
import copy
import pytest
from masked_market_comparison_plan import dispersed_starts,contract,command,matched_fixture


def fixture():
    mask=[[False]*4 for _ in range(96)]
    for cell in range(18):mask[cell//4][cell%4]=True
    labels=[[False]*4 for _ in range(48)];labels[0]=[True]*4
    return dict(data=dict(y=[[.1]*4 for _ in range(96)],x=[[.2]*4 for _ in range(96)],
        observation_mask=mask,grid_index=list(range(96)),rho=.95,nu=5.),
        holdout=dict(y=[[.1]*4]+[[None]*4 for _ in range(47)],x=[[0.]*4 for _ in range(48)],
            observation_mask=labels,x_available=[[True]*4 for _ in range(48)],grid_index=list(range(96,144))))


def test_seeded_starts_are_dispersed_and_no_data_argument():
    starts=dispersed_starts(96,4,.95,782)
    assert starts==dispersed_starts(96,4,.95,782)
    assert starts!=dispersed_starts(96,4,.95,783)
    assert len(starts)==4 and all(len(row)==108 for row in starts)
    assert len(set(map(tuple,starts)))==4


def test_exact_sparse_contract_and_masks():
    source=fixture();result=contract(source)
    assert len(result['precision_names'])==14 and len(result['forecast_cells'])==192
    assert result['training_observed']==18 and result['forecast_observed']==4
    bad=copy.deepcopy(source);bad['holdout']['x'][1][0]=None
    with pytest.raises(ValueError):contract(bad)
    bad=copy.deepcopy(source);bad['data']['observation_mask'][0][0]=1
    with pytest.raises(ValueError):contract(bad)


def test_candidate_and_reference_commands_share_budget_and_fixture(tmp_path):
    plan=dict(python='python.exe',timeout_seconds=900)
    base=dict(id='test',fixture='fixture.json',seed=192)
    candidate=command(plan,dict(base,arm='owalnuts_continuation'),tmp_path/'candidate')
    reference=command(plan,dict(base,arm='numpyro_continuation'),tmp_path/'reference')
    for cmd in [candidate,reference]:
        assert cmd[cmd.index('--timeout')+1]=='900'
        assert cmd[cmd.index('--warmup')+1]=='1000'
        assert cmd[cmd.index('--chains')+1]=='4'
        assert cmd[cmd.index('--fixture')+1]=='fixture.json'
    assert candidate[candidate.index('--model')+1]=='masked-flow'
    assert reference[reference.index('--target-accept')+1]=='0.9'


def test_placeholder_normalization_preserves_all_likelihood_inputs_and_future_labels():
    source=fixture();source['data']['y'][95][3]=None;source['data']['x'][95][3]=None
    before=copy.deepcopy(source);matched=matched_fixture(source)
    assert source==before and matched['holdout']==source['holdout']
    assert matched['data']['observation_mask']==source['data']['observation_mask']
    for i,row in enumerate(source['data']['observation_mask']):
        for j,observed in enumerate(row):
            for key in ['x','y']:
                assert matched['data'][key][i][j]==(source['data'][key][i][j] if observed else 0.)
    assert 'not full prior draws' in matched['initialization_contract']['distribution_note']
