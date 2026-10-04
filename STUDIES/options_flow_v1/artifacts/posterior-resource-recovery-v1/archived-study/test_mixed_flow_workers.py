"""Opt-in mixed worker transport/parity tests, queued until timing is quiet."""
import json
import numpy as np
import pytest


def fixture():
    return dict(data=dict(y=[[.1],[-.2]],x=[[.3],[.4]],rho=.8,nu=5.),holdout=dict(y=[[.2]],x=[[.5]]))


def test_optin_compiled_target_requires_normalized_gradient_parity():
    from flow_starts import canonical_starts
    from flow_mixed_coordinates import to_mixed
    from pymc_flow_continuation_workflow import compile_target,parity
    data=fixture()['data'];target,metadata=compile_target(data,'flow',32,'mixed_slopes')
    position=to_mixed(canonical_starts(data,4),data)[0]
    result=parity(target,data,data,'flow',[position],'mixed_slopes')
    assert result['passed'] and result['jax_enable_x64']
    assert result['normalized_canonical_jacobian_value_and_gradient']
    assert 'native_gradient_max_error' in result['cases'][0]
    with pytest.raises(ValueError,match='dense'):compile_target(data,'masked-flow',32,'mixed_slopes')


@pytest.mark.parametrize('backend',['public','reference'])
def test_tiny_mixed_workers_preserve_physical_starts_and_failed_gate(tmp_path,monkeypatch,backend):
    from flow_starts import canonical_starts
    f=fixture();f['data']['initial_positions']=canonical_starts(f['data'],4).tolist()
    source=tmp_path/'fixture.json';source.write_text(json.dumps(f));out=tmp_path/backend
    if backend=='public':
        from pymc_flow_continuation_workflow import main
        monkeypatch.setattr('sys.argv',['worker','--fixture',str(source),'--out',str(out),'--seed','911',
            '--coordinates','mixed_slopes','--warmup','10','--tiers','4','8'])
        assert main()==1
        report=json.loads((out/'python-pymc-flow-report.json').read_text())
        raw=[json.loads((out/f'draws-{n}/python-pymc-flow-raw.json').read_text()) for n in [4,8]]
    else:
        from mixed_flow_reference import execute
        report=execute(source,out,911,warmup=10,tiers=[4,8],batch=4)
        raw=[json.loads((out/f'draws-{n}-raw.json').read_text()) for n in [4,8]]
    assert report['status']=='completed',report.get('error')
    assert report['parity']['normalized_canonical_jacobian_value_and_gradient']
    assert not report['precision_pass'] and report['coordinates']=='mixed_slopes'
    np.testing.assert_array_equal(raw[-1]['initial_positions'],f['data']['initial_positions'])
    np.testing.assert_array_equal(raw[0]['canonical_draws'],np.asarray(raw[1]['canonical_draws'])[:,:4])
    assert [a['draws'] for a in report['attempts']]==[4,8]
