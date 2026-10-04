import copy
import json
import numpy as np
import pytest
from pymc_flow_continuation_workflow import validate_fixture,strict_screen,compile_target,parity,main


def fixture(groups=4,masked=False):
    data=dict(y=[[.1]*groups,[-.2]*groups],x=[[.3]*groups,[.4]*groups],rho=.8,nu=5.)
    if masked:data.update(observation_mask=[[True]*groups,[False]*groups],grid_index=[0,1])
    future=dict(y=[[.2]*groups],x=[[.5]*groups])
    if masked:future.update(observation_mask=[[True]*groups],x_available=[[True]*groups],grid_index=[2])
    return dict(data=data,holdout=future)


def test_complete_four_group_gate_and_no_silent_mask():
    f=fixture();_,names,count=validate_fixture(f,'flow')
    assert len(names)==14 and count==4 and 'h_mean' in names
    with pytest.raises(ValueError,match='mask'):validate_fixture(fixture(masked=True),'flow')
    bad=copy.deepcopy(f);bad['holdout']['x']=[]
    with pytest.raises(ValueError,match='Holdout'):validate_fixture(bad,'flow')
    with pytest.raises(ValueError,match='functional'):strict_screen({'evaluation':{}},.02,names,count)
    with pytest.raises(ValueError,match='forecast'):strict_screen({'evaluation':{'functionals':dict.fromkeys(names)}},.02,names,count)


def test_masked_transport_is_separate_and_observed_inputs_fail_closed():
    f=fixture(masked=True);f['data']['y'][1][0]=float('nan');f['data']['x'][1][0]=float('inf')
    transport,_,_=validate_fixture(f,'masked-flow')
    assert transport['y'][1][0]==transport['x'][1][0]==0
    assert np.isnan(f['data']['y'][1][0])
    f['data']['y'][0][0]=float('nan')
    with pytest.raises(ValueError,match='Observed'):validate_fixture(f,'masked-flow')


def test_masked_labels_do_not_reduce_frozen_forecast_family():
    f=fixture(masked=True)
    f['holdout']['y']=[[None]*4];f['holdout']['observation_mask']=[[False]*4]
    _,names,family=validate_fixture(f,'masked-flow')
    assert len(names)==14 and family==[(1,0),(1,1),(1,2),(1,3)]
    functionals={name:dict(interval_90=[-1,1],endpoint_mcse=[.01,.01]) for name in names}
    rows=[dict(horizon=1,group=g,forecast_available=True,width=2.,endpoint_mcse=[.01,.01]) for g in range(4)]
    report=dict(status='completed',healthy=True,evaluation=dict(functionals=functionals,forecast=dict(rows=rows)))
    assert strict_screen(report,.02,names,family)['pass']
    rows.pop()
    assert not strict_screen(report,.02,names,family)['pass']
    f['holdout']['x_available']=[[False,True,True,True]];f['holdout']['x'][0][0]=None
    assert validate_fixture(f,'masked-flow')[2]==[(1,1),(1,2),(1,3)]


@pytest.mark.parametrize('model',['flow','masked-flow'])
def test_public_compiled_normalized_parity(model):
    from flow_starts import canonical_starts,to_noncentered
    f=fixture(groups=1,masked=model=='masked-flow');transport,_,_=validate_fixture(f,model)
    target,metadata=compile_target(f['data'],model,32)
    position=to_noncentered(canonical_starts(transport,4),transport)[0]
    result=parity(target,f['data'],transport,model,[position,position+np.linspace(-.02,.02,len(position))])
    assert result['passed'] and len(result['cases'])==2 and metadata['dimension']==8


def test_masked_actual_worker_retains_failed_tiny_health_gate(tmp_path,monkeypatch):
    f=fixture(groups=1,masked=True);source=tmp_path/'fixture.json';source.write_text(json.dumps(f));out=tmp_path/'out'
    monkeypatch.setattr('sys.argv',['worker','--fixture',str(source),'--out',str(out),'--seed','828',
        '--model','masked-flow','--warmup','10','--tiers','4','8'])
    assert main()==1
    report=json.loads((out/'python-pymc-flow-report.json').read_text())
    assert report['status']=='completed',report.get('error')
    assert not report['precision_pass'] and report['parity']['passed']
    assert [v['added_draws'] for v in report['attempts']]==[4,4]
    first=json.loads((out/'draws-4/python-pymc-flow-raw.json').read_text())
    final=json.loads((out/'draws-8/python-pymc-flow-raw.json').read_text())
    np.testing.assert_array_equal(first['canonical_draws'],np.asarray(final['canonical_draws'])[:,:4])
    assert list(final)[-1]=='initial_positions'
