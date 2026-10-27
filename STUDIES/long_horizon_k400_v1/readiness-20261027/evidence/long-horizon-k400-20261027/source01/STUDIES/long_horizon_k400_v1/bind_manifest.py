"""Bind exact new source bundle to already verified E61 runtime; no study generation."""
import argparse,json
from pathlib import Path
from runtime import sha
from linear_runner import exclusive

def bind(bundle,prior,output):
    bundle=Path(bundle).absolute();prior=Path(prior);old=json.loads(prior.read_text());inventory=json.loads((bundle/'BUNDLE-MANIFEST.json').read_text());sources={str(bundle/k):v for k,v in inventory.items()}
    for path,want in sources.items():
        if sha(path)!=want:raise ValueError('Bundle hash mismatch '+path)
    compared=0
    for path,want in old['sources'].items():
        suffix=path.replace('\\','/').partition('/STUDIES/')[2]
        if suffix:
            target=bundle/'STUDIES'/suffix
            if target.exists():
                if sha(target)!=want:raise ValueError('Executed dependency differs '+suffix)
                compared+=1
        elif '/.bridgestan/' in path:sources[path]=want
    if not compared:raise ValueError('Missing prior runtime source comparisons')
    base=bundle/'STUDIES';deps=dict(resident_adapter=str(base/'prior_predictive_validation_v1/resident_adapter.py'),sv_target=str(base/'resident_predictive_harness_v1/sv_target.py'),evaluator_adapter=str(base/'prior_predictive_validation_v1/evaluator_adapter.py'),predictive_density=str(base/'predictive_value_diagnostic_v1/predictive_density.py'),compiler_capture=str(base/'independent_sv_reference_preflight_v1/compiler_capture.py'),sentinel_adapter=str(base/'prior_predictive_validation_v1/sentinel_adapter.py'),stan=str(base/'independent_sv_reference_preflight_v1/model.stan'))
    for path in deps.values():
        if path not in sources:raise ValueError('Unbound dependency '+path)
    if sources[deps['stan']]!=old['reference']['stan_sha256']:raise ValueError('Stan identity differs')
    runtime=old['runtimes']['candidate']
    if any(old['runtimes'][k]!=runtime for k in ('reference','sides','report')):raise ValueError('Unified runtime mismatch')
    spec=dict(status='frozen_pending_authorization',study='long_horizon_k400_v1',runtime=runtime,python=old['python_by_kind']['candidate'],sources=sources,dependencies=deps,reference=dict(sdk=old['reference']['bridgestan_sdk'],engine_options=old['reference']['engine_options']),protocol=json.loads((base/'long_horizon_k400_v1/protocol.json').read_text(encoding='utf-8-sig')),provenance=dict(prior_manifest_sha256=sha(prior),bundle_manifest_sha256=sha(bundle/'BUNDLE-MANIFEST.json'),unchanged_dependency_count=compared))
    exclusive(output,spec);return spec
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('bundle');p.add_argument('prior');p.add_argument('output');a=p.parse_args();bind(a.bundle,a.prior,a.output)
