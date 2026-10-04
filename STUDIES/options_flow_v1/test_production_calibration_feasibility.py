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


def prepared(tmp_path,monkeypatch,recipe='noncentered',relative_python=False,screen=None):
    study=tmp_path/'study';study.mkdir();(study/'bound.py').write_text('immutable mock source')
    monkeypatch.setattr(controller,'HERE',study)
    python=tmp_path/'python.exe';python.write_text('mock executable');package=tmp_path/'package';(package/'owalnuts').mkdir(parents=True)
    for name in ['__init__.py','_owalnuts.pyd']:(package/'owalnuts'/name).write_text('mock runtime')
    attestation=tmp_path/'attestation.json';attestation.write_text('{}')
    historical=tmp_path/'historical-seeds.json';historical.write_text('[1,2,3]')
    audit=tmp_path/'audit.json';audit.write_text(json.dumps(dict(status='passed',seeds=controller.seed_inventory(screen['seed_rows'],True) if screen else controller.seed_inventory(controller.seed_rows()),hits=[],scope='mock bounded metadata audit',auditor='unit-test',inventory_files={str(historical):controller.sha(historical)})))
    monkeypatch.setattr(controller,'attested_dependencies',lambda *a:{})
    monkeypatch.setattr(controller,'runtime_versions',lambda *a:{'python':'mock'})
    out=tmp_path/'experiment';calls=[]
    def generator(model,seed,periods=32):
        intent=json.loads((out/'recipe-intent.json').read_text())
        assert intent['flow_recipe']==recipe and intent['expected']==(20 if screen is None else screen['count']+len(screen['reference_indices']))
        calls.append((model,seed));f=generated(model,seed)
        if periods!=32:
            f['data']['y']=[f['data']['y'][0]]*periods;f['data']['x']=[f['data']['x'][0]]*periods;f['truth']=f['truth'][:12]+[-1.]*periods
        return f
    monkeypatch.setattr(controller,'generate',generator)
    if relative_python:
        monkeypatch.chdir(tmp_path)
        python=Path('python.exe')
    plan=controller.prepare(out,python,package,attestation,audit,flow_recipe=recipe,screen_spec=screen)
    assert len(calls)==(16 if screen is None else screen['count'])
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


def demanding_spec(count=4,refs=(0,3)):
    # Unit-test streams only; no actual campaign reservations.
    rows=[]
    for i in range(count):
        r=dict(model='flow',index=i,dataset_seed=100+i,init_seed=200+i,chain_seed=300+i,predictive_seed=130300+i)
        if i in refs:r.update(reference_chain_seed=400+i,reference_predictive_seed=130400+i)
        rows.append(r)
    return dict(models=['flow'],periods=1000,groups=4,count=count,reference_indices=list(refs),seed_rows=rows,timeout_seconds=1800,total_seconds=21600)


def test_demanding_explicit_scope_before_generation_and_shared_starts(tmp_path,monkeypatch):
    spec=demanding_spec();out,plan=prepared(tmp_path,monkeypatch,'mixed_slopes',screen=spec)
    assert plan['expected']==6 and len(plan['manifest_keys'])==2
    public=controller.load(out/'flow-public-manifest-draft.json');ref=controller.load(out/'flow-reference-manifest-draft.json')
    assert len(public['cells'])==4 and len(ref['cells'])==2
    assert ref['procedure']['worker_arm']=='numpyro-mixed-slopes-continuation' and ref['procedure']['implementation']=='associative'
    for r in ref['cells']:
        p=next(c for c in public['cells'] if c['dataset_seed']==r['dataset_seed'])
        assert r['fixture_path']==p['fixture_path'] and r['init_seed']==p['init_seed'] and r['chain_seed']!=p['chain_seed'] and r['predictive_seed']!=p['predictive_seed']
        assert '--implementation' in r['worker_command'] and 'associative' in r['worker_command']
        f=controller.load(r['fixture_path']);assert len(f['data']['y'])==1000 and len(f['data']['initial_positions'][0])==1012
    controller.freeze(out)
    assert controller.load(out/'plan.json')['expected']==6


@pytest.mark.parametrize('field',['periods','indices','reference_seed','models'])
def test_demanding_scope_rejects_before_generation(field):
    spec=demanding_spec()
    if field=='periods':spec['periods']=32
    elif field=='indices':spec['reference_indices']=[0,0]
    elif field=='models':spec['models']=['local_level']
    else:spec['seed_rows'][0]['reference_chain_seed']=spec['seed_rows'][0]['chain_seed']
    with pytest.raises(ValueError):controller.screen_contract(spec)

def test_proposed32_plus8_policy_is_explicit_and_validates_without_generation():
    spec=demanding_spec(32,(0,4,8,12,16,20,24,28))
    result=controller.screen_contract(spec)
    assert result['count']+len(result['reference_indices'])==40
    assert len(controller.seed_inventory(result['seed_rows'],True))==144


def test_resource_budget_preserves_all_unstarted_without_workers(tmp_path,monkeypatch):
    out,_=prepared(tmp_path,monkeypatch,'mixed_slopes',screen=demanding_spec());controller.freeze(out)
    clock=[0.]
    def now():clock[0]+=30000;return clock[0]
    monkeypatch.setattr(controller.time,'perf_counter',now)
    monkeypatch.setattr(controller.subprocess,'run',lambda *a,**kw:pytest.fail('No budget for worker'))
    controller.execute(out/'plan.json')
    statuses=[controller.load(p) for p in (out/'status').glob('*-status.json')]
    assert len(statuses)==6 and all(r['status']=='unattempted_budget' for r in statuses)
    assert not list((out/'status').glob('*-started.json'))
    assert controller.load(out/'execution-timing.json')['total_budget_unresolved'] is True

def test_budget_skips_make_unresolved_even_within_total(tmp_path,monkeypatch):
    out,_=prepared(tmp_path,monkeypatch,'mixed_slopes',screen=demanding_spec());controller.freeze(out)
    values=iter([0.]);monkeypatch.setattr(controller.time,'perf_counter',lambda:next(values,21000.))
    monkeypatch.setattr(controller.subprocess,'run',lambda *a,**kw:pytest.fail('Insufficient full cell budget'))
    controller.execute(out/'plan.json');timing=controller.load(out/'execution-timing.json')
    assert timing['seconds']==21000 and timing['seconds']<21600
    assert timing['budget_skipped']==6 and timing['has_budget_skipped'] and timing['total_budget_unresolved']


@pytest.mark.parametrize('field,value',[('resource_screen',False),('total_seconds',999999),('timeout_seconds',1),('expected',40)])
def test_screen_draft_plan_cannot_override_pregeneration_scope(tmp_path,monkeypatch,field,value):
    out,_=prepared(tmp_path,monkeypatch,'mixed_slopes',screen=demanding_spec());path=out/'plan-draft.json';plan=controller.load(path);plan[field]=value;path.write_text(json.dumps(plan))
    with pytest.raises(ValueError,match='execution scope'):controller.freeze(out)

def test_demanding_truth_and_future_labels_do_not_select_policy_or_starts():
    spec=demanding_spec();before=copy.deepcopy(spec);a=generated('flow',100);b=copy.deepcopy(a)
    b['truth']=[999.]*len(b['truth']);b['holdout']['y']=[[999.]*4]
    assert controller.initialize(a,'flow',200)['data']['initial_positions']==controller.initialize(b,'flow',200)['data']['initial_positions']
    def commands(f):
        # The only fixture argument used by command routing is its predeclared path.
        return [controller.worker_command('python','flow',kind,'mixed_slopes','fixed-fixture.json','fixed-out',300 if kind=='public' else 400,'associative' if kind=='reference' else None) for kind in ('public','reference')]
    assert commands(a)==commands(b)
    assert controller.screen_contract(spec)==controller.screen_contract(before)
    assert controller.TIERS==[1000,2000,4000,8000] and spec['reference_indices']==[0,3]


def test_report_costs_retained_on_normalization_failure(tmp_path,monkeypatch):
    out,_=prepared(tmp_path,monkeypatch,'mixed_slopes',screen=demanding_spec());controller.freeze(out)
    controller.save(out/'execution-timing.json',dict(seconds=21000,budget_skipped=1,total_budget_unresolved=True))
    monkeypatch.setattr(controller,'normalize',lambda *a:(_ for _ in ()).throw(ValueError('normalization failure')))
    with pytest.raises(ValueError,match='normalization'):controller.report(out)
    timing=controller.load(out/'report-timing.json')
    assert not timing['report_completed'] and timing['report_seconds']>=0 and timing['combined_execution_and_report_seconds']>=21000 and timing['resource_inference_unresolved']

def test_cleanup_failure_aborts_remaining_fits(tmp_path,monkeypatch):
    out,_=prepared(tmp_path,monkeypatch,'mixed_slopes',screen=demanding_spec());controller.freeze(out);calls=[]
    def run(args,**kw):
        calls.append(args);hardware=Path(args[args.index('--record')+1]);hardware.write_text(json.dumps(dict(job_active_processes_after_cleanup=1,realized_cpus=[0],containment=dict(assigned_before_worker_execution=True))))
        return SimpleNamespace(returncode=0)
    monkeypatch.setattr(controller.subprocess,'run',run);controller.execute(out/'plan.json')
    statuses=[controller.load(p) for p in (out/'status').glob('*-status.json')]
    assert len(calls)==1 and len(statuses)==6
    assert sum(r['status']=='unattempted_provenance_abort' for r in statuses)==5


@pytest.mark.parametrize('valid,unstarted,expected',[(False,False,True),(True,True,True),(True,False,False)])
def test_report_integrity_flags_without_relabeling_legitimate_gate_failures(tmp_path,monkeypatch,valid,unstarted,expected):
    out,_=prepared(tmp_path,monkeypatch,'mixed_slopes',screen=demanding_spec());controller.freeze(out)
    controller.save(out/'execution-timing.json',dict(seconds=1,budget_skipped=0,total_budget_unresolved=False))
    plan=controller.load(out/'plan.json')
    for path in plan['manifests']:
        for cell in controller.load(path)['cells']:controller.save(cell['status_path'],dict(status='unattempted_budget' if unstarted else 'worker_terminal'))
    monkeypatch.setattr(controller,'normalize',lambda m:[dict(provenance_valid=valid,usable=False) for cell in m['cells']])
    monkeypatch.setattr(controller,'write_records',lambda *a:None);monkeypatch.setattr(controller,'summarize',lambda *a:dict(qualified=False))
    controller.report(out);timing=controller.load(out/'report-timing.json')
    assert timing['resource_inference_unresolved'] is expected
    assert timing['integrity_issue_count']==(0 if valid else 6)
    assert timing['observed_unstarted_count']==(6 if unstarted else 0)
