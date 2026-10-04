"""Explicit actual-worker smoke; short draws must FAIL production health gates.

Run only in a coordinated quiet window with the attested extension on PYTHONPATH.
No controller campaign, frozen plan, or successful-fit claim is created.
"""
import copy
import json
from pathlib import Path
import pytest


@pytest.mark.parametrize('arm',['owalnuts_continuation','numpyro_continuation'])
def test_actual_worker_metadata_and_identity_bound_scoring(tmp_path,monkeypatch,arm):
    from test_asof_market_fixture import inputs
    from asof_market_fixture import prepare
    from asof_rolling_protocol import delayed_join,sha
    from asof_rolling_execute import gate,validate_result
    panel,protocol=inputs()
    # Extend the same clock contract deterministically; no real-data selection.
    template=copy.deepcopy(panel['records'][0]);panel['records']=[]
    for i in range(130):
        row=copy.deepcopy(template);decision=i*1800000+60000
        row.update(grid_index=i,decision_ms=decision,cutoff_ms=decision-60000,target_end_ms=decision+1800000)
        for g in row['groups']:g.update(feature_available_ms=decision,target_available_ms=decision+1860000)
        panel['records'].append(row)
    fixture=prepare(panel,protocol,origin_index=128,window=128,init_seed=612)
    source=tmp_path/'fixture.json';source.write_text(json.dumps(fixture));out=tmp_path/'out';seed=613
    if arm=='owalnuts_continuation':
        from pymc_flow_continuation_workflow import main
        monkeypatch.setattr('sys.argv',['worker','--fixture',str(source),'--out',str(out),'--seed',str(seed),'--model','masked-flow','--warmup','12','--tiers','8'])
        assert main()==1
        output=out/'python-pymc-flow-report.json'
    else:
        from masked_flow_reference import execute
        report=execute(source,out,seed,warmup=12,chains=4,batch=8,tiers=(8,))
        output=out/'report.json'
    report=json.loads(output.read_text())
    assert report['status']=='completed',report.get('traceback',report.get('error'))
    assert report['precision_pass'] is False
    cell=dict(origin=128,arm=arm,seed=seed,predictive_seed=seed+130000,fixture=str(source),fixture_sha256=sha(source),
        starts=fixture['data']['initial_positions'],forecast_cells=[[1,g] for g in range(4)],precision_names=list(report['evaluation']['functionals']))
    assert len(cell['precision_names'])==14 and len(report['evaluation']['canonical_parameter_diagnostics'])==140
    assert gate(report,cell) is False  # No relaxed or fabricated health pass.
    with pytest.raises(ValueError,match='Sampling contract'):
        validate_result({},cell,report,out) # Production rejects12warmup,8draws.
    joined=delayed_join(fixture,panel,output,sha(output),cell=cell,as_of_ms=panel['records'][128]['groups'][0]['target_available_ms'])
    assert joined['origin']==128 and len(joined['labels'])==4
    assert all(r['observed'] is None for r in report['evaluation']['forecast']['rows'])
    wrong=dict(cell,seed=seed+1)
    with pytest.raises(ValueError,match='seed'):
        delayed_join(fixture,panel,output,sha(output),cell=wrong,as_of_ms=999999999)
    if arm=='owalnuts_continuation':
        assert report['arm']=='python-pymc-masked-flow-noncentered-continuation'
        assert report['session_progress_before_close']['completed_transitions']==[20]*4
        assert report['total_target_calls']==report['session_progress_before_close']['target_calls']
        assert report['attempts'][0]['added_draws']==8
    else:
        assert report['plan']['arm']=='numpyro-masked-noncentered-continuation'
        cp=report['checkpoints'][0]
        assert cp['draws_per_chain']==8 and all(b-a==8 for a,b in zip(cp['start_iterations'],cp['end_iterations']))
