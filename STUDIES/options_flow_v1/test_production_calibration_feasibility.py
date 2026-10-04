"""Static-authored controller contracts; no real fixtures or samplers launched."""
import copy
import json
import math
from pathlib import Path
from types import SimpleNamespace
import pytest
import production_calibration_feasibility as controller


def generated(model,seed):
    if model=='flow':
        data=dict(y=[[.1]*4 for _ in range(32)],x=[[.3]*4 for _ in range(32)],rho=.95,nu=5.)
        truth=[0.,-1.,-1.,-1.5]+[0.]*8+[-1.]*32;future=dict(y=[[.2]*4],x=[[.3]*4])
    else:
        data=dict(y=[.1]*32,anchor=0.,anchor_mode='exogenous',dt=[1.]*31,nu=5.)
        truth=[0.]*32+[math.log(.08),math.log(.12)];future=dict(y=[.2])
    return dict(seed=seed,prior_predictive=True,data=data,truth=truth,holdout=future)


def prepared(tmp_path,monkeypatch,recipe='noncentered',relative_python=False):
    study=tmp_path/'study';study.mkdir();(study/'bound.py').write_text('immutable mock source')
    monkeypatch.setattr(controller,'HERE',study)
    python=tmp_path/'python.exe';python.write_text('mock executable');package=tmp_path/'package';(package/'owalnuts').mkdir(parents=True)
    for name in ['__init__.py','_owalnuts.pyd']:(package/'owalnuts'/name).write_text('mock runtime')
    attestation=tmp_path/'attestation.json';attestation.write_text('{}')
    historical=tmp_path/'historical-seeds.json';historical.write_text('[1,2,3]')
    audit=tmp_path/'audit.json';audit.write_text(json.dumps(dict(status='passed',seeds=controller.seed_inventory(controller.seed_rows()),hits=[],scope='mock bounded metadata audit',auditor='unit-test',inventory_files={str(historical):controller.sha(historical)})))
    monkeypatch.setattr(controller,'attested_dependencies',lambda *a:{})
    monkeypatch.setattr(controller,'runtime_versions',lambda *a:{'python':'mock'})
    out=tmp_path/'experiment';calls=[]
    def generator(model,seed):
        intent=json.loads((out/'recipe-intent.json').read_text())
        assert intent['flow_recipe']==recipe and intent['expected']==20
        calls.append((model,seed));return generated(model,seed)
    monkeypatch.setattr(controller,'generate',generator)
    if relative_python:
        monkeypatch.chdir(tmp_path)
        python=Path('python.exe')
    plan=controller.prepare(out,python,package,attestation,audit,flow_recipe=recipe)
    assert len(calls)==16
    return out,plan


@pytest.mark.parametrize('recipe',['noncentered','mixed_slopes'])
def test_recipe_precedes_generation_and_twenty_intents_are_preserved(tmp_path,monkeypatch,recipe):
    out,plan=prepared(tmp_path,monkeypatch,recipe)
    assert not plan['frozen'] and len(plan['ordered'])==20
    manifests=[json.loads((out/f'{key}-manifest-draft.json').read_text()) for key in plan['manifest_keys']]
    assert [len(m['cells']) for m in manifests]==[8,2,8,2]
    assert all(m['family_size']==100 and not m['qualified'] for m in manifests)
    for m in manifests:
        if m['procedure']['worker_kind']=='reference':assert [int(c['id'].split('-')[1]) for c in m['cells']]==[1,6]
    controller.freeze(out)
    frozen=json.loads((out/'plan.json').read_text());assert frozen['frozen'] and len(frozen['manifests'])==4


def test_invalid_recipe_cannot_generate_or_create_output(tmp_path,monkeypatch):
    monkeypatch.setattr(controller,'generate',lambda *a:pytest.fail('No generation before recipe choice'))
    with pytest.raises(ValueError):controller.prepare(tmp_path/'bad','unused','unused','unused','unused',flow_recipe=None)
    assert not (tmp_path/'bad').exists()


def test_distinct_seed_streams_and_truth_independent_initialization():
    rows=controller.seed_rows();assert len(controller.seed_inventory(rows))==64
    bad=copy.deepcopy(rows);bad[0]['predictive_seed']=bad[0]['chain_seed']
    with pytest.raises(ValueError):controller.seed_inventory(bad)
    for model in ['flow','local_level']:
        a=generated(model,1);b=copy.deepcopy(a);b['truth']=[999.]*len(b['truth']);b['holdout']['y']=[[999.]*4] if model=='flow' else [999.]
        assert controller.initialize(a,model,27)['data']['initial_positions']==controller.initialize(b,model,27)['data']['initial_positions']


def test_procedure_cannot_be_reselected_by_mutating_both_draft_and_digest(tmp_path,monkeypatch):
    out,_=prepared(tmp_path,monkeypatch);path=out/'flow-public-manifest-draft.json';manifest=json.loads(path.read_text())
    manifest['procedure']['coordinates']='mixed_slopes';manifest['procedure_sha256']=controller.object_digest(manifest['procedure']);path.write_text(json.dumps(manifest))
    with pytest.raises(ValueError,match='procedure'):controller.freeze(out)


def test_draft_cell_cannot_change_audited_seed_streams(tmp_path,monkeypatch):
    out,_=prepared(tmp_path,monkeypatch);path=out/'flow-public-manifest-draft.json';manifest=json.loads(path.read_text())
    manifest['cells'][0]['chain_seed']+=999;path.write_text(json.dumps(manifest))
    with pytest.raises(ValueError,match='seed stream'):controller.freeze(out)


@pytest.mark.parametrize('mutation',['fixture','source','path','threshold'])
def test_freeze_rejects_cell_binding_alias_and_reporting_drift(tmp_path,monkeypatch,mutation):
    out,_=prepared(tmp_path,monkeypatch);path=out/'local_level-public-manifest-draft.json';manifest=json.loads(path.read_text())
    if mutation=='fixture':manifest['cells'][0]['fixture_sha256']='wrong'
    elif mutation=='source':manifest['cells'][0]['source_sha256']={}
    elif mutation=='path':manifest['cells'][0]['hardware_path']=manifest['cells'][1]['hardware_path']
    else:manifest['nominal']=.8
    path.write_text(json.dumps(manifest))
    with pytest.raises(ValueError):controller.freeze(out)
    assert not list(out.glob('*-manifest.json'))


def test_seed_inventory_is_verified_not_just_asserted(tmp_path):
    seeds=controller.seed_inventory(controller.seed_rows());history=tmp_path/'history.json';history.write_text(json.dumps(dict(seed=seeds[0])))
    audit=tmp_path/'audit.json';evidence=dict(status='passed',seeds=seeds,hits=[],scope='bounded metadata',auditor='test',inventory_files={str(history):controller.sha(history)})
    audit.write_text(json.dumps(evidence))
    with pytest.raises(ValueError,match='occurs'):controller.audited_seeds(audit,seeds)
    history.write_text('{}')
    with pytest.raises(ValueError,match='changed'):controller.audited_seeds(audit,seeds)
    evidence['inventory_files']={};audit.write_text(json.dumps(evidence))
    with pytest.raises(ValueError,match='inventory'):controller.audited_seeds(audit,seeds)


def test_missing_workers_normalize_all_twenty_failures_with_bound_prelaunch_markers(tmp_path,monkeypatch):
    out,_=prepared(tmp_path,monkeypatch);controller.freeze(out);plan=json.loads((out/'plan.json').read_text());calls=[]
    manifests=[json.loads(Path(p).read_text()) for p in plan['manifests']];cells={c['id']:c for m in manifests for c in m['cells']}
    def run(args,**kwargs):
        hardware=Path(args[args.index('--record')+1]);cid=hardware.name.removesuffix('-hardware.json');cell=cells[cid]
        marker=json.loads(Path(cell['started_path']).read_text());assert marker['dataset_seed']==cell['dataset_seed'] and marker['fixture_sha256']==cell['fixture_sha256']
        calls.append(cid)
        hardware.write_text(json.dumps(dict(status='worker-failed',returncode=3,elapsed_seconds=.000001,
            command=args[args.index('--')+1:],realized_cpus=[0],job_active_processes_after_cleanup=0,
            containment=dict(assigned_before_worker_execution=True))))
        return SimpleNamespace(returncode=3)
    monkeypatch.setattr(controller.subprocess,'run',run);controller.execute(out/'plan.json')
    assert len(calls)==20
    records=[r for m in manifests for r in controller.normalize(m)]
    assert len(records)==20 and all(r['provenance_valid'] and not r['usable'] for r in records)
    assert all(r['failure_evidence']['classification']=='missing_report' and r['cost']['controller_seconds']>0 for r in records)
    with pytest.raises(ValueError,match='Already attempted'):controller.execute(out/'plan.json')


def test_provenance_abort_still_normalizes_complete_intended_denominator(tmp_path,monkeypatch):
    out,_=prepared(tmp_path,monkeypatch);controller.freeze(out)
    (tmp_path/'study/bound.py').write_text('changed after freeze')
    monkeypatch.setattr(controller.subprocess,'run',lambda *a,**k:pytest.fail('No workers after source drift'))
    controller.execute(out/'plan.json')
    # Keep this controller contract test free of statistical/numerical imports.
    monkeypatch.setattr(controller,'summarize',lambda manifest,records:dict(intended=len(manifest['cells']),usable=sum(r['usable'] for r in records),qualified=False))
    controller.report(out)
    records=[r for p in out.glob('*-normalized.json') for r in json.loads(p.read_text())]
    assert len(records)==20 and all(not r['usable'] for r in records)


def test_relative_python_is_canonicalized_before_all_commands(tmp_path,monkeypatch):
    out,plan=prepared(tmp_path,monkeypatch,relative_python=True)
    assert plan['python']==str((tmp_path/'python.exe').resolve())
    for key in plan['manifest_keys']:
        manifest=json.loads((out/f'{key}-manifest-draft.json').read_text())
        assert all(cell['worker_command'][0]==plan['python'] for cell in manifest['cells'])
    controller.freeze(out)
    assert json.loads((out/'plan.json').read_text())['frozen']
