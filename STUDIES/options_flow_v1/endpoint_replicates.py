"""Exploratory independent-replicate endpoint analysis; never qualification.

Input is an explicitly normalized saved-report contract, not generating truth.
Manifest: target_sha256, arm, policy, replicate_ids, endpoints={name:{scale,probability}}, optional streams={id:{sampler_seed,initialization_seed,prediction_seed}}.
Reports: id, matching identities, status, healthy, precision_pass, endpoints
={name:{estimate,mcse,scale}}, optional predictive_replays={name:[{seed,estimate}]}.
Reference: matching target_sha256, provenance, resolved, endpoints with
estimate, mcse, scale. Reference MCSE is shared across replicate comparisons.
"""
import argparse
import hashlib
import json
import math
import statistics
from pathlib import Path


def finite(value):
    return isinstance(value,(int,float)) and not isinstance(value,bool) and math.isfinite(value)


def predictive_inputs(fixture):
    """Only actual forecast inputs, never latent or observed held-out outcomes."""
    return {k:v for k,v in fixture.get('holdout',{}).items() if k in ('x','dt','horizons','elapsed_times')}


def extract_worker(manifest,replicate_id,worker,fixture_bytes):
    """Normalize real worker endpoints after verifying frozen input bindings.

    manifest.worker_bindings[id] contains fixture_sha256 and exact report_fields
    (arm, seed, source_sha256 and settings required). New replicate fixtures must
    contain replicate_streams; historic fixtures without seed provenance fail.
    target SHA hashes {data_without_initial_positions,predictive_contract}, where
    predictive_contract is frozen in the manifest, never generating truth.
    """
    if replicate_id not in manifest['replicate_ids']:raise ValueError('Unexpected replicate ID')
    binding=manifest['worker_bindings'][replicate_id]
    digest=hashlib.sha256(fixture_bytes).hexdigest()
    if digest!=binding['fixture_sha256'] or worker.get('fixture_sha256')!=digest:
        raise ValueError('Fixture hash mismatch')
    fields=binding['report_fields']
    if not {'arm','seed','source_sha256','settings'}<=set(fields):raise ValueError('Incomplete worker identity binding')
    if any(worker.get(k)!=v for k,v in fields.items()):raise ValueError('Worker identity/source/settings mismatch')
    streams=manifest['streams'][replicate_id]
    fixture=json.loads(fixture_bytes)
    if fixture.get('replicate_streams')!=streams or worker.get('seed')!=streams['sampler_seed']:
        raise ValueError('Fixture stream provenance or sampler seed mismatch')
    # Existing study evaluators derive prediction RNG from sampler seed by this offset.
    if binding.get('prediction_seed_rule')!='sampler_seed_plus_130000' or streams['prediction_seed']!=streams['sampler_seed']+130000:
        raise ValueError('Unsupported or mismatched predictive stream rule')
    data={k:v for k,v in fixture['data'].items() if k!='initial_positions'}
    target={'data':data,'predictive_contract':manifest['predictive_contract'],'predictive_inputs':predictive_inputs(fixture)}
    target_hash=hashlib.sha256(json.dumps(target,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
    if target_hash!=manifest['target_sha256']:raise ValueError('Fixed posterior target mismatch')
    normalized=dict(id=replicate_id,target_sha256=target_hash,arm=manifest['arm'],policy=manifest['policy'],
        streams=streams,status=worker.get('status'),healthy=worker.get('healthy'),precision_pass=worker.get('precision_pass'),
        elapsed_seconds=worker.get('end_to_end_seconds'),endpoints={},
        provenance=dict(fixture_sha256=digest,worker_source_sha256=worker['source_sha256']))
    if normalized['status']!='completed':return normalized
    for name,spec in manifest['endpoints'].items():
        if binding.get('endpoint_scales',{}).get(name)!=spec['scale']:
            raise ValueError('Endpoint scale must match frozen worker-semantic mapping')
        probability=spec['probability']
        if probability not in (.05,.95):raise ValueError('Worker adapter supports only stored 90% interval endpoints')
        index=0 if probability==.05 else 1;selector=spec['selector']
        if selector['kind']=='functional':
            row=worker['evaluation']['functionals'][selector['name']]
            estimate=row['interval_90'][index]
        elif selector['kind']=='forecast':
            matches=[r for r in worker['evaluation']['forecast']['rows'] if r.get('horizon')==selector['horizon'] and r.get('group')==selector.get('group')]
            if len(matches)!=1:raise ValueError('Forecast selector must identify exactly one row')
            row=matches[0];estimate=row['lower' if index==0 else 'upper']
        else:raise ValueError('Unknown endpoint selector')
        normalized['endpoints'][name]=dict(estimate=estimate,mcse=row['endpoint_mcse'][index],
            probability=probability,scale=spec['scale'])
    return normalized


def extract_cohort(manifest,artifacts):
    """Keep extraction failures as invalid outcomes; absent IDs remain missing.

    artifacts maps ID to (worker report, actual fixture bytes). The manifest
    endpoint_scales mapping is a prospective reviewed worker-semantic contract,
    not automatic proof of units or initialization RNG provenance.
    """
    rows=[]
    for key,item in artifacts.items():
        if key not in manifest['replicate_ids']:raise ValueError('Unexpected replicate ID')
        worker,fixture_bytes=item
        try:row=extract_worker(manifest,key,worker,fixture_bytes)
        except (ValueError,KeyError,TypeError,IndexError) as exc:
            row=dict(id=key,target_sha256=manifest['target_sha256'],arm=manifest['arm'],policy=manifest['policy'],
                streams=manifest.get('streams',{}).get(key),status='invalid',healthy=False,precision_pass=False,
                endpoints={},elapsed_seconds=worker.get('end_to_end_seconds'),extraction_error=str(exc))
        rows.append(row)
    return rows


def analyze(manifest,reports,reference=None):
    ids=manifest['replicate_ids'];names=manifest['endpoints']
    if not ids or len(set(ids))!=len(ids) or not names:raise ValueError('Unique expected IDs and endpoint family required')
    for name,spec in names.items():
        if not isinstance(spec,dict) or not isinstance(spec.get('scale'),str) or not finite(spec.get('probability')) or not 0<spec['probability']<1:
            raise ValueError('Each endpoint requires explicit scale and quantile probability')
    expected_streams=manifest.get('streams')
    independence_verified=False
    if expected_streams is not None:
        if set(expected_streams)!=set(ids):raise ValueError('Stream manifest must cover every expected ID')
        for key in ['sampler_seed','initialization_seed','prediction_seed']:
            values=[expected_streams[i].get(key) for i in ids]
            if any(not isinstance(v,int) or isinstance(v,bool) for v in values) or len(set(values))!=len(values):
                raise ValueError('Independent unique integer streams required: '+key)
        flat=[value for stream in expected_streams.values() for value in stream.values()]
        if any(v<0 or v>=2**32 for v in flat) or len(set(flat))!=len(flat):raise ValueError('Cross-stream collisions or out-of-range seeds')
        independence_verified=True
    indexed={}
    for report in reports:
        key=report['id']
        if key not in ids or key in indexed:raise ValueError('Unexpected or duplicate replicate ID')
        indexed[key]=report
    result=dict(phase='exploratory',qualified=False,expected=len(ids),outcomes={},endpoints={},
        uncertainty_intervals=None,limitation='Descriptive feasibility only; no simultaneous accuracy or reliability guarantee')
    result['independence_status']='declared_streams_matched' if independence_verified else 'independence_unverified'
    result['endpoint_contract']=names
    accepted=[];costs=[];missing_cost_ids=[]
    for key in ids:
        row=indexed.get(key)
        reason=None
        if row is not None and finite(row.get('elapsed_seconds')) and row['elapsed_seconds']>=0:costs.append(row['elapsed_seconds'])
        else:missing_cost_ids.append(key)
        if row is None:reason='missing'
        elif any(row.get(k)!=manifest[k] for k in ['target_sha256','arm','policy']):reason='identity_mismatch'
        elif independence_verified and row.get('streams')!=expected_streams[key]:reason='stream_mismatch'
        elif row.get('status')!='completed':reason='failed'
        elif row.get('healthy') is not True:reason='unhealthy'
        elif row.get('precision_pass') is not True:reason='precision_failed'
        else:
            for name,spec in names.items():
                scale=spec['scale']
                endpoint=row.get('endpoints',{}).get(name,{})
                if endpoint.get('scale')!=scale or endpoint.get('probability')!=spec['probability'] or not finite(endpoint.get('estimate')) or not finite(endpoint.get('mcse')) or endpoint['mcse']<=0:
                    reason='invalid_or_missing_endpoint';break
        result['outcomes'][key]=reason or 'usable'
        if reason is None:accepted.append(row)
    result['costs']=dict(scope='Worker-internal elapsed cost; excludes external wrapper overhead',recorded_elapsed_seconds=sum(costs),expected_count=len(ids),recorded_count=len(costs),missing_ids=missing_cost_ids,complete=not missing_cost_ids)
    result['usable']=len(accepted);result['usable_rate_full_denominator']=len(accepted)/len(ids)
    reference_ok=(isinstance(reference,dict) and reference.get('resolved') is True
        and reference.get('target_sha256')==manifest['target_sha256'] and bool(reference.get('provenance')))
    for name,spec in names.items():
        scale=spec['scale']
        values=[r['endpoints'][name]['estimate'] for r in accepted]
        errors=[r['endpoints'][name]['mcse'] for r in accepted]
        summary=dict(n=len(values),conditional_on_usable=True)
        if len(values)>=2:
            empirical=statistics.variance(values);reported=statistics.mean(e*e for e in errors)
            summary.update(empirical_variance=empirical,mean_reported_mcse_squared=reported,
                variance_ratio=empirical/reported,mcse_calibration_ratio=math.sqrt(empirical/reported),
                mean_endpoint=statistics.mean(values))
        ref=reference.get('endpoints',{}).get(name,{}) if reference_ok else {}
        resolved=(reference_ok and ref.get('scale')==scale and ref.get('probability')==spec['probability'] and finite(ref.get('estimate'))
                  and finite(ref.get('mcse')) and ref['mcse']>=0)
        summary['reference_status']='resolved_declared' if resolved else 'reference_unresolved'
        if resolved and values:
            delta=[v-ref['estimate'] for v in values]
            summary.update(signed_difference_from_reference=statistics.mean(delta),
                rms_difference_from_reference=math.sqrt(statistics.mean(v*v for v in delta)),
                reference_mcse_shared=ref['mcse'],reference_provenance=reference['provenance'],
                reference_uncertainty_note='Shared reference error does not shrink with replicate count; RMS difference is not proven RMS error to truth')
        replay=[]
        for row in accepted:
            draws=row.get('predictive_replays',{}).get(name)
            if draws is None:continue
            seeds=[d.get('seed') for d in draws]
            if len(draws)<2 or any(not isinstance(v,int) or isinstance(v,bool) for v in seeds) or len(set(seeds))!=len(seeds) or any(not finite(d.get('estimate')) for d in draws):
                raise ValueError('Predictive replay requires unique integer seeds and >=2 finite estimates')
            replay.append(dict(id=row['id'],seeds=seeds,conditional_replay_variance=statistics.variance(d['estimate'] for d in draws)))
        summary['predictive_replay']=dict(rows=replay,
            mean_conditional_variance=statistics.mean(r['conditional_replay_variance'] for r in replay) if replay else None,
            scope='Conditional simulation variance on fixed posterior draws; reported separately, never subtracted from replicate dispersion')
        result['endpoints'][name]=summary
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--manifest',type=Path,required=True);p.add_argument('--reports',type=Path,required=True)
    p.add_argument('--reference',type=Path);p.add_argument('--out',type=Path,required=True)
    a=p.parse_args()
    result=analyze(json.loads(a.manifest.read_text()),json.loads(a.reports.read_text()),json.loads(a.reference.read_text()) if a.reference else None)
    with a.out.open('x') as handle:json.dump(result,handle,indent=2,allow_nan=False)


if __name__=='__main__':main()
