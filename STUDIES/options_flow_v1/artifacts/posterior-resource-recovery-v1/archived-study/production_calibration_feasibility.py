"""Prospective 8-per-model feasibility controller, never qualification.

Recipe selection and seed audit precede any generation. Preparation, freezing,
execution and normalization are explicit separate actions. Static draft.
"""
import argparse
import copy
import datetime
import json
import math
import os
from pathlib import Path
import random
import re
import subprocess
import time
from continuation_comparison import sha,load,save,attested_dependencies
from masked_market_comparison_plan import dispersed_starts
from production_calibration_adapter import object_digest,fixture_contract,select_truth,normalize,write_records
from production_calibration_report import summarize,validate_manifest

HERE=Path(__file__).resolve().parent
REFERENCE_INDICES=[1,6]
TIERS=[1000,2000,4000,8000]
REPORTING_SETTINGS=dict(alpha=.05,nominal=.9,tolerance=.05,family_size=100,min_replicates=8,minimum_usable_probability=.9)


def runtime_versions(python):
    return json.loads(subprocess.check_output([str(python),'-c',
        "import sys,json,importlib.metadata as m;print(json.dumps(dict(python=sys.version,packages={p:m.version(p) for p in ['numpy','scipy','pymc','pytensor','numba','jax','jaxlib','numpyro','arviz']})))"],text=True))


def seed_rows():
    rows=[]
    for model,offset in [('flow',0),('local_level',100)]:
        for i in range(8):
            rows.append(dict(model=model,index=i,dataset_seed=104010001+offset+i,init_seed=104110001+offset+i,
                chain_seed=104210001+offset+i,predictive_seed=104340001+offset+i))
    return rows


def seed_inventory(rows):
    values=[row[key] for row in rows for key in ['dataset_seed','init_seed','chain_seed','predictive_seed']]
    if len(values)!=64 or len(set(values))!=64 or any(type(v) is not int or not 0<=v<2**32 for v in values):raise ValueError('Distinct uint32 data/init/chain/prediction seed streams required')
    if any(row['predictive_seed']!=row['chain_seed']+130000 for row in rows):raise ValueError('Existing worker predictive offset contract violated')
    return values


def audited_seeds(path,inventory):
    audit=load(path);files=audit.get('inventory_files')
    if audit.get('status')!='passed' or sorted(audit.get('seeds',[]))!=sorted(inventory) or audit.get('hits')!=[] or not audit.get('scope') or not audit.get('auditor') or not isinstance(files,dict) or not files:raise ValueError('Exact bounded seed audit with immutable searched inventory and auditor required')
    pattern=re.compile(r'(?<![0-9])(?:'+'|'.join(map(str,inventory))+r')(?![0-9])')
    for filename,digest in files.items():
        source=Path(filename)
        if source.resolve()==Path(path).resolve() or 'raw' in source.name.lower() or source.stat().st_size>2000000:raise ValueError('Seed audit must name bounded historical metadata, excluding itself and raw arrays')
        if sha(source)!=digest:raise ValueError('Searched seed inventory changed')
        raw=source.read_bytes();text=raw.decode('utf-16' if raw[:2] in [b'\xff\xfe',b'\xfe\xff'] else 'utf-8-sig')
        if pattern.search(text):raise ValueError('Proposed seed occurs in searched historical inventory')
    return audit


def generate(model,seed):
    """Only called by explicit prepare, after immutable recipe intent exists."""
    if model=='flow':
        from model import simulate
        return simulate(seed,periods=32,groups=4,holdout=1,prior=True)
    from local_level import simulate
    return simulate(seed,periods=32,holdout=1,prior=True,anchor=0.)


def initialize(fixture,model,seed):
    fixture=copy.deepcopy(fixture);data=fixture['data']
    if model=='flow':starts=dispersed_starts(32,4,data['rho'],seed)
    else:
        rng=random.Random(seed);starts=[]
        for _ in range(4):
            path=[float(y)+.02*rng.gauss(0.,1.) for y in data['y']]
            starts.append(path+[math.log(.08)+.2*rng.gauss(0.,1.),math.log(.12)+.2*rng.gauss(0.,1.)])
    data['initial_positions']=starts
    fixture['initialization']=dict(seed=seed,policy='Flow0.25priorSD globals/groups/AR innovations using shape/rho only; local observed y plusN(0,.02), logscales atlog(.08/.12)+N(0,.2). No truth or holdout used.')
    return fixture


def generated_contract(fixture,model,seed):
    if fixture.get('seed')!=seed or len(fixture['data']['y'])!=32 or len(fixture['holdout']['y'])!=1:raise ValueError('Generated seed/period/horizon contract mismatch')
    if model=='flow' and len(fixture['data']['y'][0])!=4:raise ValueError('Four flow groups required')
    if model=='local_level' and fixture['data'].get('anchor')!=0.:raise ValueError('Exogenous local anchor must equal zero')
    return fixture_contract(fixture,model)


def selectors(model):
    names=['beta_bar','tau','mu_h','sigma_h','h_terminal','h_mean']+[p+str(g) for g in range(4) for p in ['alpha_','beta_']] if model=='flow' else ['h_initial','h_terminal','h_mean','sigma_obs','sigma_rw']
    selected=[dict(name=name,kind='functional',key=name) for name in names]
    selected += [dict(name=f'forecast_1_{g}',kind='forecast',horizon=1,group=g) for g in range(4)] if model=='flow' else [dict(name='forecast_1',kind='forecast',horizon=1,group=None)]
    return selected


def worker_command(python,model,kind,coordinates,fixture,out,seed):
    args=['--fixture',str(fixture),'--out',str(out),'--seed',str(seed),'--warmup','1000','--chains','4','--tiers',*map(str,TIERS)]
    if kind=='public':
        worker='pymc_flow_continuation_workflow.py' if model=='flow' else 'pymc_continuation_workflow.py'
        args+=['--coordinates',coordinates]
        if model=='flow':args+=['--model','flow','--block-size','32','--expected-cpus','0']
    else:
        worker='continuation_precision.py';args+=['--model',model,'--target-accept','0.9','--batch-size','1000']
        if model=='local_level':args+=['--coordinates','observation_residual']
    return [str(python),str(HERE/worker),*args]


def prepare(out,python,package,attestation,seed_audit,*,flow_recipe,local_recipe='observation_residual'):
    if flow_recipe not in ['noncentered','mixed_slopes'] or local_recipe!='observation_residual':raise ValueError('Explicit pre-generation tested recipes required')
    out=Path(out).resolve();python=Path(python).resolve();package=Path(package).resolve();rows=seed_rows();inventory=seed_inventory(rows);audit=audited_seeds(seed_audit,inventory)
    study={str(p.resolve()):sha(p) for p in HERE.glob('*.py')}
    runtime_files={str(Path(p).resolve()):sha(p) for p in [python,package/'owalnuts/__init__.py',package/'owalnuts/_owalnuts.pyd']}
    bound=dict(study,**runtime_files);bound.update(attested_dependencies(attestation,python,package))
    bound.update({str(Path(p).resolve()):v for p,v in audit['inventory_files'].items()})
    for path in [attestation,seed_audit]:bound[str(Path(path).resolve())]=sha(path)
    intent=dict(flow_recipe=flow_recipe,local_recipe=local_recipe,seed_rows=rows,seed_audit=audit,
        reference_indices=REFERENCE_INDICES,reference_recipes=dict(flow='noncentered',local_level='observation_residual'),
        periods=32,groups=4,local_anchor=0.,holdout=1,expected=20,timeout_seconds=600,aggregate_worker_allowance_seconds=12000,
        allowance_scope='Sum of20per-worker caps, not a cohort wall-clock deadline. Wrapper/reaping/preflight/reporting overhead can exceed it. Contained hardware wrapper owns timeout and descendant cleanup; controller does not kill wrapper before reaping.',
        tiers=TIERS,chains=4,warmup=1000,cpus=[0],bound_files=bound,study_bindings=study,
        prediction_seed_policy='Distinct audited PRNG seeds derived as chain+130000 by existing worker/adapter contract; not independently randomized seed selection',
        interpretation='Eight fresh prior datasets/model, two prespecified reference subsets/model: feasibility only, no calibration qualification',
        costs='Complete precision procedure, including runtime parity, imports/compile, warmup/draws/evaluation/output and wrapper; all failures retained',
        cache_policy='Fresh contained CPU0 workers; existing disk caches retained; no overlapping timed work',runtime_versions=runtime_versions(python),
        reporting_settings=REPORTING_SETTINGS,reporting_scope='Feasibility descriptive bounds only; these thresholds are not qualification requirements')
    out.mkdir(parents=True,exist_ok=False);save(out/'recipe-intent.json',intent)
    (out/'fixtures').mkdir();(out/'runs').mkdir();(out/'status').mkdir()
    fixture_rows={}
    for row in rows:
        fixture=initialize(generate(row['model'],row['dataset_seed']),row['model'],row['init_seed'])
        path=out/'fixtures'/f'{row["model"]}-{row["index"]:02d}.json';save(path,fixture)
        fixture_rows[(row['model'],row['index'])]=(path,fixture,generated_contract(fixture,row['model'],row['dataset_seed']))
    manifests={};procedures={}
    for model in ['flow','local_level']:
        for kind in ['public','reference']:
            key=model+'-'+kind;coords=flow_recipe if model=='flow' and kind=='public' else 'noncentered' if model=='flow' else local_recipe
            worker_arm=('python-pymc-flow-'+coords+'-continuation' if model=='flow' else 'python-pymc-cfunc-continuation') if kind=='public' else ('numpyro-continuation' if model=='flow' else 'numpyro-continuation-observation-residual')
            procedure=dict(worker_kind=kind,worker_arm=worker_arm,coordinates=coords,warmup=1000,chains=4,tiers=TIERS,relative_mcse=.02,timeout_seconds=600,cpus=[0],
                bound_files=bound,runtime_bindings=runtime_files if kind=='public' else {str(Path(python).resolve()):sha(python)},study_directory=str(HERE))
            if kind=='public' and model=='flow':procedure['block_size']=32
            if kind=='reference':procedure.update(target_accept=.9,batch_size=1000)
            procedures[key]=procedure;proc_digest=object_digest(procedure)
            manifests[key]=dict(status='DRAFT',qualified=False,model=model,arm=key+'-'+coords,procedure=procedure,procedure_sha256=proc_digest,
                **REPORTING_SETTINGS,reporting_scope=intent['reporting_scope'],selectors=selectors(model),cells=[])
    ordered=[]
    for row in rows:
        model=row['model'];index=row['index'];kinds=['public']
        if index in REFERENCE_INDICES:kinds=['reference','public'] if index==REFERENCE_INDICES[0] else ['public','reference']
        for kind in kinds:
            key=model+'-'+kind;manifest=manifests[key];procedure=procedures[key];cid=f'{model}-{index:02d}-{kind}'
            fixture_path,fixture,physical=fixture_rows[(model,index)];output=out/'runs'/cid
            cell=dict(id=cid,model=model,arm=manifest['arm'],procedure_sha256=manifest['procedure_sha256'],dataset_seed=row['dataset_seed'],init_seed=row['init_seed'],chain_seed=row['chain_seed'],predictive_seed=row['predictive_seed'],
                source_sha256=study if kind=='public' else {Path(k).name:v for k,v in study.items()},fixture_sha256=sha(fixture_path),fixture_path=str(fixture_path),
                truth=select_truth(physical,manifest['selectors']),output_directory=str(output),status_path=str(out/'status'/f'{cid}-status.json'),
                hardware_path=str(out/'status'/f'{cid}-hardware.json'),started_path=str(out/'status'/f'{cid}-started.json'),
                worker_command=worker_command(python,model,kind,procedure['coordinates'],fixture_path,output,row['chain_seed']))
            manifest['cells'].append(cell);ordered.append(dict(manifest=key,id=cid))
    protocol=dict(intent_sha256=sha(out/'recipe-intent.json'),procedures={k:object_digest(v) for k,v in procedures.items()},
        fixtures={str(v[0]):sha(v[0]) for v in fixture_rows.values()},ordered=ordered)
    protocol_sha=object_digest(protocol);save(out/'protocol.json',protocol)
    for key,manifest in manifests.items():manifest['protocol_sha256']=protocol_sha;save(out/f'{key}-manifest-draft.json',manifest)
    plan=dict(frozen=False,qualified=False,python=str(Path(python).resolve()),pythonpath=str(package),expected=20,
        protocol_sha256=protocol_sha,protocol_path=str(out/'protocol.json'),bound_files=bound,study_bindings=study,
        manifest_keys=list(manifests),ordered=ordered,timeout_seconds=600,runtime_versions=intent['runtime_versions'])
    save(out/'plan-draft.json',plan);return plan


def verify(plan):
    protocol=load(plan['protocol_path'])
    if object_digest(protocol)!=plan['protocol_sha256']:raise ValueError('Protocol drift')
    if sha(Path(plan['protocol_path']).parent/'recipe-intent.json')!=protocol['intent_sha256']:raise ValueError('Pre-generation recipe intent drift')
    if {str(p.resolve()):sha(p) for p in HERE.glob('*.py')}!=plan['study_bindings'] or any(sha(p)!=v for p,v in plan['bound_files'].items()):raise ValueError('Bound source/build drift')
    for path,value in load(plan['protocol_path'])['fixtures'].items():
        if sha(path)!=value:raise ValueError('Fixture drift')
    if runtime_versions(plan['python'])!=plan['runtime_versions']:raise ValueError('Runtime package/interpreter drift')


def freeze(directory):
    directory=Path(directory);plan=load(directory/'plan-draft.json');verify(plan);frozen={};drafts=[]
    intent=load(directory/'recipe-intent.json');seed_map={(r['model'],r['index']):r for r in intent['seed_rows']};claimed_paths=set()
    for key in plan['manifest_keys']:
        manifest=load(directory/f'{key}-manifest-draft.json');manifest['status']='FROZEN'
        if object_digest(manifest['procedure'])!=manifest['procedure_sha256'] or manifest['procedure_sha256']!=load(plan['protocol_path'])['procedures'][key] or manifest['protocol_sha256']!=plan['protocol_sha256']:raise ValueError('Manifest protocol/procedure drift')
        expected_count=8 if manifest['procedure']['worker_kind']=='public' else 2
        if len(manifest['cells'])!=expected_count or {c['id'] for c in manifest['cells']}!={r['id'] for r in plan['ordered'] if r['manifest']==key}:raise ValueError('Intended denominator drift')
        if manifest['selectors']!=selectors(manifest['model']):raise ValueError('Coverage selector family drift')
        if any(manifest.get(k)!=v for k,v in intent['reporting_settings'].items()):raise ValueError('Predeclared feasibility reporting thresholds drift')
        for cell in manifest['cells']:
            seeds=seed_map[(manifest['model'],int(cell['id'].split('-')[1]))]
            if any(cell.get(k)!=seeds[k] for k in ['dataset_seed','init_seed','chain_seed','predictive_seed']):raise ValueError('Preselected seed stream drift')
            fixture=load(cell['fixture_path']);physical=generated_contract(fixture,manifest['model'],seeds['dataset_seed'])
            expected_fixture=(directory/'fixtures'/f'{manifest["model"]}-{seeds["index"]:02d}.json').resolve()
            if Path(cell['fixture_path']).resolve()!=expected_fixture or cell['fixture_sha256']!=sha(expected_fixture) or load(plan['protocol_path'])['fixtures'].get(str(expected_fixture))!=cell['fixture_sha256']:raise ValueError('Cell fixture binding drift')
            expected_source=plan['study_bindings'] if manifest['procedure']['worker_kind']=='public' else {Path(k).name:v for k,v in plan['study_bindings'].items()}
            if cell['source_sha256']!=expected_source:raise ValueError('Cell worker source schema drift')
            expected_paths=dict(output_directory=directory/'runs'/cell['id'],status_path=directory/'status'/f'{cell["id"]}-status.json',hardware_path=directory/'status'/f'{cell["id"]}-hardware.json',started_path=directory/'status'/f'{cell["id"]}-started.json')
            for name,expected in expected_paths.items():
                actual=Path(cell[name]).resolve();key_path=str(actual).casefold()
                if actual!=expected.resolve() or not actual.is_relative_to(directory.resolve()) or key_path in claimed_paths:raise ValueError('Cell paths must be unique and contained in the prospective output')
                claimed_paths.add(key_path)
            if fixture['seed']!=seeds['dataset_seed'] or physical['starts']!=initialize(fixture,manifest['model'],seeds['init_seed'])['data']['initial_positions']:raise ValueError('Fixture seed/start strategy drift')
            if cell['truth']!=select_truth(physical,manifest['selectors']):raise ValueError('Generated truth drift')
            expected_command=worker_command(plan['python'],manifest['model'],manifest['procedure']['worker_kind'],manifest['procedure']['coordinates'],cell['fixture_path'],cell['output_directory'],cell['chain_seed'])
            if cell['worker_command']!=expected_command:raise ValueError('Procedure command drift')
        validate_manifest(manifest);drafts.append((directory/f'{key}-manifest.json',manifest))
    for path,manifest in drafts:
        save(path,manifest);frozen[str(path.resolve())]=sha(path)
    plan.update(frozen=True,manifests=frozen);path=directory/'plan.json';save(path,plan)
    with path.with_suffix('.sha256').open('x') as handle:handle.write(sha(path))


def execute(path):
    path=Path(path).resolve();plan=load(path);original=sha(path)
    if plan.get('frozen') is not True or plan['expected']!=20 or len(plan['ordered'])!=20:raise ValueError('Frozen twenty-cell protocol required')
    def check():
        if sha(path)!=original or path.with_suffix('.sha256').read_text().strip()!=original:raise ValueError('Plan drift')
        verify(plan)
        if any(sha(p)!=v for p,v in plan['manifests'].items()):raise ValueError('Manifest drift')
    manifests={Path(p).name.removesuffix('-manifest.json'):load(p) for p in plan['manifests']};abort=None;cohort_start=time.perf_counter()
    for order in plan['ordered']:
        manifest=manifests[order['manifest']];cell=next(c for c in manifest['cells'] if c['id']==order['id'])
        status=Path(cell['status_path']);marker=Path(cell['started_path']);output=Path(cell['output_directory'])
        if status.exists() or marker.exists() or output.exists():raise ValueError('Already attempted cell; no automatic retry')
        if abort:
            save(status,dict(status='unattempted_provenance_abort',error=abort,elapsed_seconds=0,returncode=None));continue
        save(marker,dict(protocol_sha256=manifest['protocol_sha256'],procedure_sha256=manifest['procedure_sha256'],fixture_sha256=cell['fixture_sha256'],dataset_seed=cell['dataset_seed'],utc=datetime.datetime.now(datetime.timezone.utc).isoformat()))
        tick=time.perf_counter();record=dict(id=cell['id'],status='started',returncode=None)
        try:
            try:check()
            except Exception as exc:abort=str(exc);raise
            args=[plan['python'],str(HERE/'hardware_control.py'),'--cpus','0','--record',cell['hardware_path'],'--timeout','600','--',*cell['worker_command']]
            record['command']=args
            with (status.parent/(cell['id']+'.log')).open('x') as log:r=subprocess.run(args,cwd=HERE,env=dict(os.environ,PYTHONPATH=plan['pythonpath']),stdout=log,stderr=subprocess.STDOUT)
            record['returncode']=r.returncode;save(status.parent/(cell['id']+'-exit.json'),dict(record))
            if Path(cell['hardware_path']).exists():record['hardware_sha256']=sha(cell['hardware_path'])
            name=('python-pymc-flow-report.json' if manifest['model']=='flow' else 'python-pymc-report.json') if manifest['procedure']['worker_kind']=='public' else 'numpyro-continuation-report.json'
            if (output/name).exists():record['report_sha256']=sha(output/name)
            try:check()
            except Exception as exc:abort=str(exc);raise
            record['status']='worker_terminal'
        except Exception as exc:record.update(status='controller_failed',error=str(exc))
        record['elapsed_seconds']=time.perf_counter()-tick;save(status,record)
    save(path.parent/'execution-timing.json',dict(seconds=time.perf_counter()-cohort_start,intended=20,qualified=False))


def report(directory):
    directory=Path(directory);plan=load(directory/'plan.json')
    if plan.get('frozen') is not True or (directory/'plan.sha256').read_text().strip()!=sha(directory/'plan.json'):raise ValueError('Frozen plan digest mismatch')
    # Reporting must preserve failed provenance in the intended denominator.
    # The adapter checks current source/fixture bindings per cell; do not abort
    # the whole normalization just because those checks will fail.
    if object_digest(load(plan['protocol_path']))!=plan['protocol_sha256']:raise ValueError('Protocol identity drift')
    for name,value in plan['manifests'].items():
        if sha(name)!=value:raise ValueError('Manifest drift')
        manifest=load(name);records=normalize(manifest);key=Path(name).name.removesuffix('-manifest.json')
        write_records(directory/f'{key}-normalized.json',records)
        save(directory/f'{key}-coverage.json',summarize(manifest,records))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('action',choices=['prepare','freeze','run','report']);p.add_argument('--out',type=Path,required=True)
    for name in ['python','package','attestation','seed-audit']:p.add_argument('--'+name,type=Path)
    p.add_argument('--flow-recipe',choices=['noncentered','mixed_slopes']);p.add_argument('--local-recipe',choices=['observation_residual'],default='observation_residual');a=p.parse_args()
    if a.action=='prepare':prepare(a.out,a.python,a.package,a.attestation,a.seed_audit,flow_recipe=a.flow_recipe,local_recipe=a.local_recipe)
    elif a.action=='freeze':freeze(a.out)
    elif a.action=='run':execute(a.out/'plan.json')
    else:report(a.out)
