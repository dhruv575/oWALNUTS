"""Queued static-authored protocol contracts; no real fixture preparation."""
import copy
import json
from pathlib import Path
import pytest
import asof_rolling_protocol as p


def test_ablation_changes_only_covariates_and_description():
    f=dict(data=dict(x=[[.2]*4]*128,initial_positions=[[1.]*140]*4),holdout=dict(x=[[.5]*4],y=[[None]*4]),precision_family=[[1,g] for g in range(4)])
    result=p.no_flow(f)
    assert result['data']['initial_positions']==f['data']['initial_positions']
    assert result['holdout']['y']==f['holdout']['y'] and result['precision_family']==f['precision_family']
    assert all(v==0 for row in result['data']['x'] for v in row)
    assert f['data']['x'][0][0]==.2


def test_all32_cells_cyclic_balanced_matched_streams(tmp_path):
    rows=[dict(origin=o,init_seed=100+i,chain_seed=200+i,predictive_seed=130200+i) for i,o in enumerate(p.ORIGINS)]
    fixtures={}
    for row in rows:
        for kind in ['flow','no-flow']:
            path=tmp_path/f'{row["origin"]}-{kind}.json'
            path.write_text(json.dumps(dict(data=dict(initial_positions=[[1.]*140]*4),precision_family=[[1,g] for g in range(4)])))
            fixtures[(row['origin'],kind)]=path
    cells=p.build_cells(fixtures,rows,tmp_path,dict(python='python',timeout_seconds=600))
    assert len(cells)==32 and len({c['id'] for c in cells})==32
    for i in range(8):
        group=cells[4*i:4*i+4];shift=i%4
        assert [c['comparison_arm'] for c in group]==p.ARMS[shift:]+p.ARMS[:shift]
        assert len({c['seed'] for c in group})==len({c['predictive_seed'] for c in group})==1
        assert all(c['dimension']==140 and len(c['precision_names'])==14 and len(c['forecast_cells'])==4 for c in group)
        assert all('--timeout' in c['command'] and '600' in c['command'] for c in group)


def test_seed_audit_requires_historical_bound_inventory(tmp_path):
    rows=[dict(origin=o,init_seed=100+i,chain_seed=200+i,predictive_seed=130200+i) for i,o in enumerate(p.ORIGINS)]
    history=tmp_path/'old-plan.json';history.write_text('{"seed":1}')
    seeds=[r[k] for r in rows for k in ['init_seed','chain_seed','predictive_seed']]
    audit=tmp_path/'audit.json';audit.write_text(json.dumps(dict(status='passed',seeds=seeds,hits=[],scope='test',auditor='test',inventory_files={str(history):p.sha(history)})))
    assert p.validate_seeds(rows,audit)['status']=='passed'
    history.write_text('{"seed":100}')
    with pytest.raises(ValueError):p.validate_seeds(rows,audit)


def draft(tmp_path,monkeypatch,empty_origin=False):
    import asof_rolling_execute as e
    rows=[dict(origin=o,init_seed=100+i,chain_seed=200+i,predictive_seed=130200+i) for i,o in enumerate(p.ORIGINS)]
    historical=tmp_path/'historical.json';historical.write_text('{"seed":1}')
    audit=tmp_path/'audit.json';audit.write_text(json.dumps(dict(status='passed',seeds=[r[k] for r in rows for k in ['init_seed','chain_seed','predictive_seed']],hits=[],scope='mock historical',auditor='test',inventory_files={str(historical):p.sha(historical)})))
    panel=tmp_path/'panel.json';panel.write_text('{}');protocol=tmp_path/'protocol.json';protocol.write_text('{}')
    python=tmp_path/'python.exe';python.write_text('mock');package=tmp_path/'package';(package/'owalnuts').mkdir(parents=True)
    for n in ['__init__.py','_owalnuts.pyd']:(package/'owalnuts'/n).write_text('mock')
    attest=tmp_path/'attest.json';attest.write_text('{}')
    monkeypatch.setattr(p,'attested_dependencies',lambda *a:{})
    monkeypatch.setattr(p,'runtime_versions',lambda *a:{})
    monkeypatch.setattr(e,'runtime_versions',lambda *a:{})
    def fixture(*args,**kwargs):return dict(data=dict(x=[[.2]*4 for _ in range(128)],initial_positions=[[float(kwargs['init_seed'])]*140 for _ in range(4)]),holdout=dict(x=[[.2]*4],y=[[None]*4]),precision_family=[] if empty_origin and kwargs['origin_index']==144 else [[1,g] for g in range(4)])
    monkeypatch.setattr(p,'origin_fixture',fixture)
    out=tmp_path/'experiment';plan=p.prepare(out,panel,protocol,python,package,attest,audit,rows)
    return e,out,plan


def test_explicit_freeze_and_no_overwrite(tmp_path,monkeypatch):
    e,out,plan=draft(tmp_path,monkeypatch)
    assert not (out/'plan.json').exists() and not plan['frozen']
    frozen=e.freeze(out);assert frozen['frozen']
    assert (out/'plan.sha256').read_text()==e.sha(out/'plan.json')
    with pytest.raises(ValueError):e.freeze(out)


@pytest.mark.parametrize('mutation',[
    lambda p:p['cells'].reverse(),
    lambda p:p['cells'][0].update(id='../escape'),
    lambda p:p['cells'][0].update(fixture='../fixture.json'),
    lambda p:p['cells'][0].update(starts=[[0.]]),
    lambda p:p['cells'][0]['command'].append('--unexpected'),
    lambda p:p.update(expected=31),
    lambda p:p.update(window=127),
    lambda p:p['schema'].update(dimension=139),
    lambda p:p['seed_rows'][0].update(chain_seed=999),
])
def test_freeze_rejects_changed_schedule_schema_and_paths(tmp_path,monkeypatch,mutation):
    e,out,plan=draft(tmp_path,monkeypatch);mutation(plan)
    (out/'plan-draft.json').write_text(json.dumps(plan))
    with pytest.raises(ValueError):e.freeze(out)
    assert not (out/'plan.json').exists()


def test_fixture_mutation_rejected_at_freeze(tmp_path,monkeypatch):
    e,out,plan=draft(tmp_path,monkeypatch);path=Path(plan['cells'][0]['fixture'])
    changed=json.loads(path.read_text());changed['data']['initial_positions'][0][0]+=1;path.write_text(json.dumps(changed))
    with pytest.raises(ValueError):e.freeze(out)


@pytest.mark.parametrize('arm',['owalnuts_continuation','numpyro_continuation'])
def test_scoring_join_binds_exact_origin_fixture_seed_and_output(tmp_path,monkeypatch,arm):
    fixture=dict(provenance=dict(origin_index=144));fp=tmp_path/'fixture.json';fp.write_text(json.dumps(fixture))
    cell=dict(arm=arm,origin=144,fixture=str(fp),fixture_sha256=p.sha(fp),seed=42,predictive_seed=130042,forecast_cells=[[1,g] for g in range(4)])
    report=dict(status='completed',seed=42,predictive_seed=130042,arm='python-pymc-masked-flow-noncentered-continuation',model='masked-flow',bindings={str(fp.resolve()):p.sha(fp)},
        plan=dict(arm='numpyro-masked-noncentered-continuation',model='masked_flow',fixture_sha256=p.sha(fp),predictive_seed=130042),evaluation=dict(forecast=dict(rows=[dict(horizon=1,group=g,forecast_available=True) for g in range(4)])))
    out=tmp_path/'report.json';out.write_text(json.dumps(report));monkeypatch.setattr(p,'delayed_scores',lambda *a,**k:[])
    assert p.delayed_join(fixture,{},out,p.sha(out),cell=cell,as_of_ms=999)['origin']==144
    for mutate in [lambda r:r.update(seed=43),lambda r:r.update(arm='wrong') if arm=='owalnuts_continuation' else r['plan'].update(arm='wrong'),lambda r:r.update(bindings={}) if arm=='owalnuts_continuation' else r['plan'].update(fixture_sha256='wrong')]:
        changed=copy.deepcopy(report);mutate(changed);out.write_text(json.dumps(changed))
        with pytest.raises(ValueError):p.delayed_join(fixture,{},out,p.sha(out),cell=cell,as_of_ms=999)
    out.write_text(json.dumps(report));old=p.sha(out);out.write_text(json.dumps(dict(report,changed=True)))
    with pytest.raises(ValueError):p.delayed_join(fixture,{},out,old,cell=cell,as_of_ms=999)


def test_preparation_and_freeze_keep_no_anchor_origin_four_cells(tmp_path,monkeypatch):
    e,out,plan=draft(tmp_path,monkeypatch,empty_origin=True)
    assert len(plan['cells'])==32 and len([c for c in plan['cells'] if c['origin']==144])==4
    assert all(c['forecast_cells']==[] for c in plan['cells'] if c['origin']==144)
    assert [r['origin'] for r in plan['seed_rows']]==p.ORIGINS
    e.freeze(out)
