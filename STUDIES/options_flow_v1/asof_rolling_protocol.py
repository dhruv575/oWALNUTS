"""Prospective eight-origin as-of replay preparation. No implicit execution.

Draft controller: preparation and later sampling require separate explicit calls.
"""
import copy
import re
from pathlib import Path
from continuation_comparison import sha,load,save,attested_dependencies
from production_calibration_feasibility import runtime_versions
from asof_market_fixture import prepare as origin_fixture,delayed_scores
from masked_market_comparison_plan import command,NAMES

HERE=Path(__file__).resolve().parent
ORIGINS=[144,168,192,216,240,264,288,312]
ARMS=['public-flow','reference-flow','public-no-flow','reference-no-flow']


def validate_seeds(rows,audit_path):
    if len(rows)!=8 or [r['origin'] for r in rows]!=ORIGINS:raise ValueError('Exact scheduled origin seed rows required')
    seeds=[r[k] for r in rows for k in ['init_seed','chain_seed','predictive_seed']]
    if len(set(seeds))!=24 or any(type(s) is not int or not 0<=s<2**32 for s in seeds):raise ValueError('24 disjoint uint32 streams required')
    if any(r['predictive_seed']!=r['chain_seed']+130000 for r in rows):raise ValueError('Prediction seed offset differs')
    audit=load(audit_path);files=audit.get('inventory_files',{})
    if audit.get('status')!='passed' or sorted(audit.get('seeds',[]))!=sorted(seeds) or audit.get('hits')!=[] or not files or not audit.get('auditor') or not audit.get('scope'):raise ValueError('Bounded historical seed audit required')
    pattern=re.compile(r'(?<![0-9])(?:'+'|'.join(map(str,seeds))+r')(?![0-9])')
    for filename,digest in files.items():
        p=Path(filename)
        if 'raw' in p.name.lower() or p.stat().st_size>2000000 or sha(p)!=digest:raise ValueError('Invalid seed inventory binding')
        raw=p.read_bytes();text=raw.decode('utf-16' if raw[:2] in [b'\xff\xfe',b'\xfe\xff'] else 'utf-8-sig')
        if pattern.search(text):raise ValueError('Historical seed collision')
    return audit


def no_flow(fixture):
    f=copy.deepcopy(fixture)
    for key in ['data','holdout']:f[key]['x']=[[0.]*4 for row in f[key]['x']]
    f['ablation']='Same-model zero-flow predictive diagnostic; unused slope priors retained. Not an optimized no-flow performance baseline.'
    return f


def build_cells(fixtures,seed_rows,out,plan):
    cells=[]
    for i,row in enumerate(seed_rows):
        order=ARMS[i%4:]+ARMS[:i%4]
        for label in order:
            public=label.startswith('public');kind='no-flow' if label.endswith('no-flow') else 'flow'
            path=fixtures[(row['origin'],kind)];fixture=load(path)
            cell=dict(id=f'origin-{row["origin"]}-{label}',origin=row['origin'],comparison_arm=label,
                arm='owalnuts_continuation' if public else 'numpyro_continuation',seed=row['chain_seed'],
                predictive_seed=row['predictive_seed'],init_seed=row['init_seed'],fixture=str(path),fixture_sha256=sha(path),
                starts=fixture['data']['initial_positions'],precision_names=NAMES,forecast_cells=fixture['precision_family'],dimension=140)
            cell['command']=command(plan,cell,Path(out)/cell['id']);cells.append(cell)
    return cells


def prepare(out,panel_path,protocol_path,python,package,attestation,seed_audit,seed_rows):
    """Explicit preparation only; freezes no plan and launches no worker."""
    audit=validate_seeds(seed_rows,seed_audit);python=Path(python).resolve();package=Path(package).resolve()
    panel=load(panel_path);protocol=load(protocol_path);out=Path(out).resolve()
    bound={str(Path(p).resolve()):sha(p) for p in [panel_path,protocol_path,python,attestation,seed_audit,package/'owalnuts/__init__.py',package/'owalnuts/_owalnuts.pyd']}
    bound.update(attested_dependencies(attestation,python,package));bound.update(audit['inventory_files'])
    plan=dict(frozen=False,qualified=False,expected=32,origins=ORIGINS,window=128,seed_rows=seed_rows,
        python=str(python),pythonpath=str(package),runtime=runtime_versions(python),bound_files=bound,
        study_bindings={str(p.resolve()):sha(p) for p in HERE.glob('*.py')},timeout_seconds=600,
        aggregate_worker_allowance_seconds=19200,chains=4,warmup=1000,tiers=[1000,2000,4000,8000],relative_mcse=.02,
        reference_target_accept=.9,candidate_target_accept='attested unchanged default0.8',
        panel_path=str(Path(panel_path).resolve()),protocol_path=str(Path(protocol_path).resolve()),seed_audit_path=str(Path(seed_audit).resolve()),
        schema=dict(dimension=140,precision_names=NAMES,forecast_cells=[[1,g] for g in range(4)]),
        interpretation='Historical event-time plus assumed60sec availability lag replay, conditional on eligible trade arrival; eight fixed origins, no qualification.',
        costs='All imports/parity/compile/warmup/draw/evaluation/output/wrapper and failed attempts retained',
        runtime_policy='CPU0 contained workers sequential; retained disk caches; fresh processes; no competing timed jobs',
        scoring_policy='Separate join only after immutable inference outputs; mature protocol-eligible labels only; missing/purged labels explicit',
        ablation='Same-model x=0 train/current, unused prior parameters retained; predictive diagnostic, not fastest no-flow baseline')
    out.mkdir(parents=True,exist_ok=False);save(out/'intent.json',plan);(out/'fixtures').mkdir()
    fixtures={}
    for row in seed_rows:
        f=origin_fixture(panel,protocol,origin_index=row['origin'],window=128,init_seed=row['init_seed'])
        if f['precision_family']!=[[1,g] for g in range(4)]:raise ValueError('Prespecified four-current-feature family unavailable; do not replace origin')
        for kind,value in [('flow',f),('no-flow',no_flow(f))]:
            path=out/'fixtures'/f'{row["origin"]}-{kind}.json';save(path,value);fixtures[(row['origin'],kind)]=path
    plan['intent_sha256']=sha(out/'intent.json');plan['cells']=build_cells(fixtures,seed_rows,out,plan);save(out/'plan-draft.json',plan);return plan


def delayed_join(fixture,panel,output_path,expected_output_sha256,*,cell,as_of_ms):
    """Join only an identity-bound immutable completed forecast output."""
    from continuation_comparison import norm
    if sha(output_path)!=expected_output_sha256:raise ValueError('Frozen inference output changed')
    report=load(output_path)
    if report.get('status')!='completed':raise ValueError('Incomplete forecast output')
    if sha(cell['fixture'])!=cell['fixture_sha256'] or load(cell['fixture'])!=fixture or fixture['provenance']['origin_index']!=cell['origin']:raise ValueError('Scoring fixture/origin differs')
    if report.get('seed')!=cell['seed']:raise ValueError('Scoring seed differs')
    if cell['arm']=='owalnuts_continuation':
        if report.get('arm')!='python-pymc-masked-flow-noncentered-continuation' or report.get('model')!='masked-flow' or report.get('predictive_seed')!=cell['predictive_seed']:raise ValueError('Scoring public identity differs')
        if norm(report['bindings']).get(str(Path(cell['fixture']).resolve()).casefold())!=cell['fixture_sha256']:raise ValueError('Output belongs to another fixture')
    else:
        p=report['plan']
        if p.get('arm')!='numpyro-masked-noncentered-continuation' or p.get('model')!='masked_flow' or p.get('fixture_sha256')!=cell['fixture_sha256'] or p.get('predictive_seed')!=cell['predictive_seed']:raise ValueError('Scoring reference identity differs')
    forecast=report['evaluation']['forecast']
    if {(r['horizon'],r['group']) for r in forecast['rows']}!={tuple(v) for v in cell['forecast_cells']}:raise ValueError('Scoring forecast family differs')
    return dict(inference_output_sha256=expected_output_sha256,origin=cell['origin'],seed=cell['seed'],
        labels=delayed_scores(fixture,panel,as_of_ms=as_of_ms),qualified=False)
