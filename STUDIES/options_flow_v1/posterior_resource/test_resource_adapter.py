import json,sys
from pathlib import Path
import numpy as np
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
from .resource_worker import validate_report
from .stream_extract import extract


def test_compact_cdf_inputs_match_independent_existing_constructor(tmp_path):
    from predictive_cdf import PredictiveMixture
    rng=np.random.default_rng(818);q=rng.normal(0,.1,(4,8,15));q[...,1]=-.7;q[...,3]=-1.4
    data=dict(y=[[0.]*4]*3,x=[[.2]*4]*3,rho=.8,nu=5.)
    raw=tmp_path/'raw.json';raw.write_text(json.dumps({'canonical_draws':q.tolist()}))
    extract(raw,tmp_path/'out',chains=4,draws=8,dimension=15,rho=.8,x_next=.63)
    z=np.load(tmp_path/'out/compact.npz');direct=PredictiveMixture.from_flow(q,data,group=0,x_next=.63)
    np.testing.assert_array_equal(z['cdf_location'].reshape(-1),direct.location)
    np.testing.assert_array_equal(z['cdf_future_mean'].reshape(-1),direct.future_mean)
    np.testing.assert_array_equal(z['cdf_future_sd'].reshape(-1),direct.future_sd)
    rebuilt=PredictiveMixture('flow',z['cdf_location'].reshape(-1),z['cdf_future_mean'].reshape(-1),z['cdf_future_sd'].reshape(-1),np.zeros(32),np.full(32,1/32),5.,2048,{})
    np.testing.assert_array_equal(rebuilt.cdf([-.7,0.,1.],32),direct.cdf([-.7,0.,1.],32))


def metadata(tmp_path,public):
    from flow_mixed_coordinates import to_mixed
    names=['beta_bar','tau','mu_h','sigma_h','h_terminal','h_mean']+[p+str(g) for g in range(4) for p in ['alpha_','beta_']]
    data=dict(y=[[0.]*4]*1000,x=[[0.]*4]*1000,rho=.95,nu=5.,initial_positions=[[0.,-1.,-1.,-1.5]+[0.]*8+[-1.]*1000 for _ in range(4)])
    path=tmp_path/'fixture.json';path.write_text(json.dumps(dict(data=data)))
    cell=dict(backend='public' if public else 'reference',seed=100,fixture=str(path),fixture_sha256='fixture')
    package=tmp_path/'package'
    package_bindings={str(package/'owalnuts'/n):'packagehash' for n in ['__init__.py','_owalnuts.pyd']}
    plan=dict(pythonpath=str(package),worker_bindings={},bindings={**package_bindings,str(tmp_path/'unrelated/__init__.py'):'unrelated'},full_gate=dict(functional_names=names))
    raw=tmp_path/'raw.json';raw.write_text(json.dumps(dict(adapted_metadata={'fixed':True},initial_positions=data['initial_positions'],sampling_initial_positions=to_mixed(np.asarray(data['initial_positions']),data).tolist())))
    report=dict(status='completed',model='flow',coordinates='mixed_slopes',draws=8000,parity=dict(passed=True),seed=100,predictive_seed=130100,
        settings=dict(warmup=1000,chains=4,tiers=[8000],block_size=32,threads=1,target_accept=.9,batch=1000),attempts=[dict(draws=8000,added_target_calls=900)],
        arm='python-pymc-flow-mixed_slopes-continuation' if public else 'numpyro-mixed-slopes-continuation',implementation='associative',
        warmup_target_calls=100,adapted_metadata={'fixed':True},session_progress_before_close=dict(completed_transitions=[9000]*4,target_calls=1000),total_target_calls=1000,
        initial_positions=data['initial_positions'],hardware_control=dict(realized_cpus=[0]),precision_plan=dict(names=names,forecast_rows=4,threshold=.02,tiers=[8000]),
        bindings={str(path.resolve()):'fixture',**package_bindings},evaluation=dict(canonical_parameter_diagnostics={f'q_{i}':{} for i in range(1012)},functionals={n:{} for n in names},forecast=dict(rows=[{}]*4)),
        checkpoints=[dict(draws_per_chain=1000*(i+1),start_iterations=[1000*(i+1)]*4,end_iterations=[1000*(i+2)]*4,adaptation_sha256='frozen') for i in range(8)])
    return report,cell,dict(data=data),plan,raw


@pytest.mark.parametrize('public',[True,False])
def test_actual_mixed_schema_admission_and_wrong_earlystop(tmp_path,public):
    args=metadata(tmp_path,public);validate_report(*args)
    args[0]['draws']=4000
    with pytest.raises(ValueError,match='full8k'):validate_report(*args)


@pytest.mark.parametrize('field',['parity','seed','precision','state'])
def test_rejects_bad_mixed_admission(tmp_path,field):
    args=metadata(tmp_path,False);r=args[0]
    if field=='parity':r['parity']['passed']=False
    elif field=='seed':r['seed']+=1
    elif field=='precision':r['precision_plan']['forecast_rows']=1
    else:r['checkpoints'][3]['adaptation_sha256']='changed'
    with pytest.raises(ValueError):validate_report(*args)


@pytest.mark.parametrize('tamper',['counter','adaptation'])
def test_public_raw_state_and_cost_reconcile(tmp_path,tamper):
    args=metadata(tmp_path,True)
    if tamper=='counter':args[0]['warmup_target_calls']+=1
    else:args[0]['adapted_metadata']={'changed':True}
    with pytest.raises(ValueError):validate_report(*args)


def test_package_hash_still_required_while_unrelated_init_is_not(tmp_path):
    args=metadata(tmp_path,True)
    validate_report(*args)
    key=str(Path(args[3]['pythonpath'])/'owalnuts/__init__.py')
    args[0]['bindings'][key]='wrong'
    with pytest.raises(ValueError,match='binding mismatch'):validate_report(*args)
