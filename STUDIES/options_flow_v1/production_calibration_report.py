"""Generic prospective interval coverage evidence, never automatic qualification.

Manifest: model, arm, procedure_sha256, protocol_sha256, alpha, nominal, tolerance, family_size, min_replicates,
minimum_usable_probability, selectors=[{name,kind:functional,key} or
{name,kind:forecast,horizon,group}], cells=[{id,model,arm,procedure_sha256,dataset_seed,source_sha256,fixture_sha256,
truth:{selector_name:finite_value}}]. Records are a LIST of immutable normalized
records with id, model, arm, procedure_sha256, dataset_seed, protocol_sha256,
source_sha256, fixture_sha256, truth, usable,
intervals:{name:[lower,upper]}, original_report_sha256. An upstream adapter must
independently recompute the production procedure's health/precision/first-pass
and provenance gates before setting usable=True. This module does not infer
usability from R-hat or rank sufficiency, nor launch workers or rewrite reports.
"""
import math


def finite(v):return isinstance(v,(int,float)) and not isinstance(v,bool) and math.isfinite(v)
def exact_interval(hits,total,alpha):
    if total==0:return None
    from scipy.stats import beta
    return [0. if hits==0 else float(beta.ppf(alpha/2,hits,total-hits+1)),1. if hits==total else float(beta.ppf(1-alpha/2,hits+1,total-hits))]
def reliability_lower(hits,total,alpha):
    if total==0 or hits==0:return 0.
    from scipy.stats import beta
    return float(beta.ppf(alpha,hits,total-hits+1))


def validate_manifest(m):
    if not m.get('protocol_sha256') or m.get('status')!='FROZEN':raise ValueError('Frozen prospective protocol required')
    for k in ['alpha','nominal','tolerance','minimum_usable_probability']:
        if not finite(m.get(k)):raise ValueError('Finite claim settings required')
    if not 0<m['alpha']<1 or not 0<m['nominal']-m['tolerance']<m['nominal']+m['tolerance']<1 or not 0<=m['minimum_usable_probability']<1:raise ValueError('Invalid claim bounds')
    for k in ['model','arm','procedure_sha256']:
        if not isinstance(m.get(k),str) or not m[k]:raise ValueError('One explicit model/arm/procedure required')
    selectors=m['selectors'];names=[s['name'] for s in selectors]
    if not names or len(set(names))!=len(names):raise ValueError('Unique nonempty selector names required')
    identities=[]
    for s in selectors:
        if s['kind']=='functional':identities.append(('functional',s['key']))
        elif s['kind']=='forecast':identities.append(('forecast',s['horizon'],s.get('group')))
        else:raise ValueError('Unknown selector')
    if len(set(identities))!=len(identities):raise ValueError('Duplicate physical selector')
    # Two reported interval claims per selector plus one reliability claim. Explicitly
    # allocate multiplicity across the WHOLE declared decision family.
    if isinstance(m.get('family_size'),bool) or not isinstance(m.get('family_size'),int) or m['family_size']<2*len(names)+1:raise ValueError('Family must include conditional, unconditional and reliability claims')
    if isinstance(m.get('min_replicates'),bool) or not isinstance(m.get('min_replicates'),int) or m['min_replicates']<1:raise ValueError('Positive prospective minimum required')
    cells=m['cells'];ids=[c['id'] for c in cells]
    if not ids or len(set(ids))!=len(ids):raise ValueError('Unique nonempty intended cells required')
    if len({c['fixture_sha256'] for c in cells})!=len(cells):raise ValueError('Independent distinct fixtures required')
    seeds=[c.get('dataset_seed') for c in cells]
    if any(isinstance(v,bool) or not isinstance(v,int) or v<0 for v in seeds) or len(set(seeds))!=len(seeds):raise ValueError('Unique independent dataset seeds required')
    for c in cells:
        if any(c.get(k)!=m[k] for k in ['model','arm','procedure_sha256']):raise ValueError('Mixed model/arm/procedure summary prohibited')
        if not c.get('source_sha256') or not c.get('fixture_sha256') or set(c['truth'])!=set(names) or not all(finite(v) for v in c['truth'].values()):raise ValueError('Frozen source, fixture and complete generated truth required')
    return names


def summarize(manifest,records):
    names=validate_manifest(manifest)
    if not isinstance(records,list):raise ValueError('List records preserve duplicate detection')
    expected={c['id']:c for c in manifest['cells']};seen={};extras=[]
    for r in records:
        if not isinstance(r,dict) or 'id' not in r:raise ValueError('Malformed record')
        if r['id'] not in expected:extras.append(r['id'])
        seen.setdefault(r['id'],[]).append(r)
    outcomes={};hits={n:0 for n in names};usable=0
    for cid,c in expected.items():
        candidates=seen.get(cid,[]);reasons=[];covered={n:False for n in names}
        if len(candidates)!=1:reasons.append('missing record' if not candidates else 'duplicate records')
        else:
            r=candidates[0]
            for k in ['model','arm','procedure_sha256','dataset_seed','source_sha256','fixture_sha256','truth']:
                if r.get(k)!=c[k]:reasons.append('mismatched '+k)
            if not isinstance(r.get('truth'),dict) or not all(finite(v) for v in r['truth'].values()):reasons.append('mismatched finite truth')
            if r.get('protocol_sha256')!=manifest['protocol_sha256']:reasons.append('protocol mismatch')
            if not r.get('original_report_sha256'):reasons.append('missing original report binding')
            if r.get('usable') is not True:reasons.append('production procedure unsuccessful')
            intervals=r.get('intervals')
            if not isinstance(intervals,dict):
                reasons.append('invalid interval mapping');intervals={}
            for name in names:
                interval=intervals.get(name)
                if not isinstance(interval,(list,tuple)) or len(interval)!=2 or not all(finite(x) for x in interval) or interval[1]<=interval[0]:reasons.append('invalid interval '+name)
                else:covered[name]=interval[0]<=c['truth'][name]<=interval[1]
        good=not reasons
        if good:
            usable+=1
            for name in names:hits[name]+=int(covered[name])
        outcomes[cid]=dict(usable=good,reasons=reasons,coverage_if_valid=covered)
    total=len(expected);alpha=manifest['alpha']/manifest['family_size'];stats={}
    for name in names:
        count=hits[name];unconditional=exact_interval(count,total,alpha);conditional=exact_interval(count,usable,alpha)
        stats[name]=dict(usable_and_covering=count,intended=total,usable=usable,
            unconditional_usable_and_covering_rate=count/total,
            conditional_coverage=count/usable if usable else None,
            unconditional_simultaneous_ci=unconditional,conditional_simultaneous_ci=conditional,
            unconditional_equivalence=unconditional[0]>=manifest['nominal']-manifest['tolerance'] and unconditional[1]<=manifest['nominal']+manifest['tolerance'])
    lower=reliability_lower(usable,total,alpha)
    duplicate_ids=[k for k,v in seen.items() if len(v)>1]
    integrity=not extras and not duplicate_ids and all(not any(s.startswith(('mismatched','protocol mismatch','missing original')) for s in o['reasons']) for o in outcomes.values())
    component=integrity and total>=manifest['min_replicates'] and lower>=manifest['minimum_usable_probability'] and all(v['unconditional_equivalence'] for v in stats.values())
    return dict(qualified=False,model=manifest['model'],arm=manifest['arm'],procedure_sha256=manifest['procedure_sha256'],protocol_sha256=manifest['protocol_sha256'],intended=total,usable=usable,
        missing=[k for k in expected if k not in seen],duplicate_ids=duplicate_ids,extra_ids=extras,
        record_integrity_pass=integrity,coverage_component_meets_prespecified_rule=component,
        family_size=manifest['family_size'],family_labels=[*[f'conditional:{n}' for n in names],*[f'unconditional:{n}' for n in names],'usable_probability'],per_claim_alpha=alpha,reliability_lower=lower,
        selectors=stats,cells=outcomes,
        limitations=['Independent identically generated datasets are required; distinct seeds/hashes detect reuse but do not prove the generator correct.',
        'Usability must come from a separately validated production-procedure adapter.',
        'Unconditional usable-and-covering is not mathematical posterior coverage on failed fits.',
        'Conditional coverage describes the selected usable subset, not all generated datasets.',
        'Ranks are not consumed; this is interval coverage evidence, not full SBC.',
        'No demanding-performance, market-utility or overall qualification claim.'])
