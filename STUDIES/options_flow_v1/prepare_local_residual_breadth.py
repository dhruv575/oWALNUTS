"""Explicit preparation only; never invokes a sampling worker.

Requires a root-produced seed audit bound to the exact draft spec and a
default attestation bound to the actual candidate source. Numerical imports
are deferred until --prepare, after all input evidence has been checked.
"""
import argparse
import datetime
import hashlib
import json
from pathlib import Path
import sys


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save(path, value):
    with path.open('x',encoding='utf-8') as handle:
        json.dump(value,handle,indent=2,allow_nan=False)


def check_evidence(spec_path, spec, audit, defaults):
    if audit.get('status') != 'passed' or audit.get('spec_sha256') != digest(spec_path):
        raise ValueError('Require passing seed audit bound to the exact spec')
    expected = sorted(c[k] for c in spec['cells'] for k in ('dataset_seed','chain_seed','prediction_seed'))
    if len(expected) != 72 or len(set(expected)) != 72 or audit.get('seeds') != expected:
        raise ValueError('Seed audit must cover exactly 72 distinct intended streams')
    if not audit.get('audited_files') or not audit.get('method'):
        raise ValueError('Seed audit requires bounded corpus identity and method')
    for path, sha in audit['audited_files'].items():
        if digest(path) != sha:raise ValueError('Audited input changed: '+path)
    if defaults.get('target_accept') != .8 or not defaults.get('evidence_files'):
        raise ValueError('Require candidate default .8 source attestation')
    for path, sha in defaults['evidence_files'].items():
        if digest(path) != sha:raise ValueError('Default evidence changed: '+path)
    if not defaults.get('explanation'):
        raise ValueError('Default attestation must explain which source establishes .8')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prepare',action='store_true',required=True)
    parser.add_argument('--spec',type=Path,required=True)
    parser.add_argument('--seed-audit',type=Path,required=True)
    parser.add_argument('--default-attestation',type=Path,required=True)
    parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args()
    spec=json.loads(args.spec.read_text());audit=json.loads(args.seed_audit.read_text())
    defaults=json.loads(args.default_attestation.read_text())
    check_evidence(args.spec,spec,audit,defaults)
    if args.out.exists():raise FileExistsError('Preparation never overwrites an existing directory')
    if len(spec['cells']) != 24 or spec['reference_indices'] != [0,5,8,13,16,21]:
        raise ValueError('Unexpected prospective cohort')
    for i,cell in enumerate(spec['cells']):
        expected_order=['candidate']
        if i in spec['reference_indices']:
            expected_order=['candidate','reference'] if spec['reference_indices'].index(i)%2==0 else ['reference','candidate']
        if cell['index']!=i or cell['execution_order']!=expected_order:
            raise ValueError('Prospective balanced order changed')
    settings=spec['settings']
    for key,value in dict(cpus=[0],chains=4,warmup=1000,retained_tiers=[1000,2000,4000,8000],batch_size=1000,timeout_seconds_per_worker=1800).items():
        if settings.get(key)!=value:raise ValueError('Unsupported setting: '+key)
    if spec['candidate'].get('target_accept')!=.8 or spec['reference'].get('target_accept')!=.9:
        raise ValueError('Prospective acceptance settings changed')
    # These imports and fixture generation occur only on explicit invocation.
    import numpy as np
    import owalnuts
    import owalnuts._owalnuts as extension
    from local_level import simulate
    from local_observation_residual import canonical_starts
    root=Path(__file__).resolve().parent
    source={p.name:digest(p) for p in root.glob('*.py')}
    bound={str(Path(p).resolve()):digest(p) for p in
           [owalnuts.__file__,extension.__file__,sys.executable,args.spec,args.seed_audit,args.default_attestation]}
    bound.update(defaults['evidence_files'])
    # Exclusive directory plus unfinished marker makes interrupted preparation
    # explicit. Never auto-resume/reuse partly generated fixtures.
    args.out.mkdir(parents=True,exist_ok=False)
    save(args.out/'preparation.started.json',dict(utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),spec_sha256=digest(args.spec)))
    cells=[]
    for intended in spec['cells']:
        i=intended['index']
        if intended['prediction_seed'] != intended['chain_seed']+130000:
            raise ValueError('Prediction stream mismatch')
        fixture=simulate(intended['dataset_seed'],periods=128,holdout=1,prior=True,anchor=0.)
        starts=canonical_starts(fixture['data'],4)
        fixture['data']['initial_positions']=starts.tolist()
        fixture_path=(args.out/f'fixture-{i:02}.json').resolve()
        save(fixture_path,fixture)
        starts_hash=hashlib.sha256(json.dumps(starts.tolist(),separators=(',',':'),allow_nan=False).encode()).hexdigest()
        for arm in intended['execution_order']:
            cells.append(dict(id=f'local-{i:02}-{arm}',index=i,arm=arm,fixture=str(fixture_path),
                fixture_sha256=digest(fixture_path),canonical_starts_sha256=starts_hash,
                dataset_seed=intended['dataset_seed'],chain_seed=intended['chain_seed'],prediction_seed=intended['prediction_seed']))
    if len(cells)!=30 or sum(c['arm']=='reference' for c in cells)!=6:
        raise ValueError('Plan must preserve 24 candidate plus six reference cells')
    if source!={p.name:digest(p) for p in root.glob('*.py')}:
        raise ValueError('Study sources changed during preparation')
    for path,sha in bound.items():
        if digest(path)!=sha:raise ValueError('Bound input changed during preparation')
    plan=dict(frozen=True,qualified=False,phase='exploratory',python=str(Path(sys.executable).resolve()),
        source_sha256=source,bound_files=bound,runner_sha256=digest(root/'local_residual_breadth.py'),
        original_spec_sha256=digest(args.spec),cells=cells,specification=spec,
        seed_audit=audit,candidate_default_attestation=defaults,
        cache_policy='Retain existing disk caches; new worker process each cell; no cache clearing; compilation and imports charged',
        runtime_parity_policy='Candidate runs independent JAX density/gradient parity every invocation; cost charged; reference normalized-density correctness covered by source-bound preflight tests',
        denominators=dict(candidate=24,reference=6,total=30),
        inference_scope='Standalone fresh-cohort reliability screen; not a paired causal geometry comparison against historical centered cohort',
        retry_policy='Never restart a started cell automatically; preserve timeout/exception/missing-report costs and failures',
        software=dict(python=sys.version,numpy=np.__version__,algorithm_revision=owalnuts.ALGORITHM_REVISION))
    save(args.out/'plan.json',plan)
    with (args.out/'plan.sha256').open('x',encoding='utf-8') as handle:handle.write(digest(args.out/'plan.json')+'\n')
    save(args.out/'preparation.completed.json',dict(plan_sha256=digest(args.out/'plan.json'),fixtures=24,cells=30))
    print(str(args.out/'plan.json'))


if __name__=='__main__':main()
