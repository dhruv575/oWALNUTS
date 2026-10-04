"""Draft reference-bank analysis, not a qualification certificate.

Manifest freezes expected fit IDs/backends, two lengths, endpoint probabilities,
scales, source/target hashes, and whole-fit bootstrap seed/count. Fit records bind
both paired lengths and contain scalar functional draws per endpoint. Predictive
endpoints instead contain cached conditional mixture CDF values on a common grid.
"""
import bisect
import math
import random


def finite(x):return isinstance(x,(float,int)) and not isinstance(x,bool) and math.isfinite(x)


def weighted_quantile(values,weights,p):
    """Left inverse of weighted empirical CDF; equal weight per fit upstream."""
    if not 0<p<1 or len(values)!=len(weights) or not values:raise ValueError('Invalid quantile inputs')
    ordered=sorted(zip(values,weights));total=0.
    for value,weight in ordered:
        if not finite(value) or not finite(weight) or weight<0:raise ValueError('Invalid weighted draw')
        total+=weight
    if total<=0:raise ValueError('Empty positive mass')
    cumulative=0.
    for value,weight in ordered:
        cumulative+=weight
        if cumulative>=p*total-8*math.ulp(total):return value
    return ordered[-1][0]


def pooled_parameter(fits,name,length,p,multiplicity=None):
    values=[];weights=[]
    for fit in fits:
        count=1 if multiplicity is None else multiplicity.get(fit['id'],0)
        if not count:continue
        draws=fit['levels'][str(length)]['endpoints'][name]['draws']
        if not draws:raise ValueError('Empty fit functional draws')
        values.extend(draws);weights.extend([count/len(draws)]*len(draws))
    return weighted_quantile(values,weights,p)


def prepare_parameters(fits,spec):
    cache={}
    for length in spec['lengths']:
        for name,endpoint in spec['endpoints'].items():
            if endpoint['kind']!='parameter':continue
            key=(length,endpoint['distribution_id'])
            if key in cache:
                cache[(length,name)]=cache[key];continue
            ordered={fit['id']:sorted(fit['levels'][str(length)]['endpoints'][name]['draws']) for fit in fits}
            if any(not values or any(not finite(v) for v in values) for values in ordered.values()):raise ValueError('Invalid functional draws')
            key=(length,endpoint['distribution_id'])
            if key not in cache:cache[key]=(ordered,sorted({v for values in ordered.values() for v in values}))
            cache[(length,name)]=cache[key]
    return cache


def cached_parameter(fits,cache,length,name,p,multiplicity=None):
    ordered,candidates=cache[(length,name)]
    counts={fit['id']:1 if multiplicity is None else multiplicity.get(fit['id'],0) for fit in fits}
    total=sum(counts.values())
    if total<=0:raise ValueError('Empty bootstrap mass')
    lo,hi=0,len(candidates)-1
    while lo<hi:
        mid=(lo+hi)//2;value=candidates[mid]
        cumulative=math.fsum(count*bisect.bisect_right(ordered[key],value)/len(ordered[key]) for key,count in counts.items())
        if cumulative>=p*total-8*math.ulp(total):hi=mid
        else:lo=mid+1
    return candidates[lo]


def predictive_bracket(fits,name,length,p,multiplicity=None):
    """Invert CDF envelopes; grid width and supplied CDF error remain explicit.

    A supplied error can be a verified bound or a declared estimate supported by
    refinement and independent controls. The latter gives approximate numerical
    brackets, not interval-arithmetic guarantees; provenance must distinguish it.
    """
    total=0.;lower=None;upper=None;grid=None
    for fit in fits:
        count=1 if multiplicity is None else multiplicity.get(fit['id'],0)
        if not count:continue
        row=fit['levels'][str(length)]['endpoints'][name]
        x=row['grid'];cdf=row['cdf']
        verified=row.get('error_bound_verified') is True and bool(row.get('error_bound_provenance'))
        checked=row.get('numerical_checks_passed') is True and bool(row.get('numerical_checks_provenance'))
        if not (verified or checked):raise ValueError('Predictive numerical checks unresolved')
        error=row.get('cdf_error_bound') if verified else row.get('numerical_cdf_error_estimate')
        if len(x)<2 or len(x)!=len(cdf) or any(not finite(v) for v in x+cdf) or any(b<=a for a,b in zip(x,x[1:])) or any(b<a for a,b in zip(cdf,cdf[1:])) or any(v<0 or v>1 for v in cdf) or not finite(error) or error<0:raise ValueError('Invalid predictive grid')
        if grid is None:grid=x;lower=[0.]*len(x);upper=[0.]*len(x)
        if x!=grid:raise ValueError('Predictive fits require identical queried grid')
        for j,value in enumerate(cdf):lower[j]+=count*max(0.,value-error);upper[j]+=count*min(1.,value+error)
        total+=count
    lower=[v/total for v in lower];upper=[v/total for v in upper]
    lo=[i for i,v in enumerate(upper) if v<p];hi=[i for i,v in enumerate(lower) if v>=p]
    if not lo or not hi:raise ValueError('CDF envelopes do not bracket quantile')
    return grid[max(lo)],grid[min(hi)]


def evaluate(fits,spec,length,multiplicity=None,cache=None):
    result={};numerical={}
    for name,endpoint in spec['endpoints'].items():
        if endpoint['kind']=='parameter':
            result[name]=cached_parameter(fits,cache,length,name,endpoint['probability'],multiplicity) if cache is not None else pooled_parameter(fits,name,length,endpoint['probability'],multiplicity);numerical[name]=0.
        else:
            lo,hi=predictive_bracket(fits,name,length,endpoint['probability'],multiplicity)
            result[name]=(lo+hi)/2;numerical[name]=(hi-lo)/2
    return result,numerical


def resample_fits(fits,rng):
    """One stratified resample reused jointly for every endpoint and later fit."""
    groups={}
    for fit in fits:groups.setdefault(fit['backend'],[]).append(fit['id'])
    counts={}
    for ids in groups.values():
        for _ in ids:
            key=rng.choice(ids);counts[key]=counts.get(key,0)+1
    return counts


def percentile(values,p):
    ordered=sorted(values);position=p*(len(values)-1);lo=int(position)
    return ordered[lo]+(ordered[min(lo+1,len(ordered)-1)]-ordered[lo])*(position-lo)


def shared_reference_errors(candidate_endpoints,bank_vector):
    return [{name:value-bank_vector[name] for name,value in candidate.items()} for candidate in candidate_endpoints]


def analyze(spec,fits,parameter_batch=None):
    out=dict(status='reference_unresolved',qualified=False,expected_fits=len(spec['fits']),recorded_fits=len(fits),reasons=[],
        uncertainty_method='Stratified whole-fit percentile bootstrap with Bonferroni endpoint tails; finite-bank approximation, not exact coverage',
        source_sha256=spec['source_sha256'],target_sha256=spec['target_sha256'])
    try:
        expected={r['id']:r for r in spec['fits']}
        if len(expected)!=len(spec['fits']) or len({f['id'] for f in fits})!=len(fits) or set(expected)!={f['id'] for f in fits}:raise ValueError('Missing, duplicate or unexpected bank fits')
        if spec.get('numerical_policy') not in ('verified_bound','validated_estimate'):raise ValueError('Declare numerical error policy prospectively')
        endpoints=spec.get('endpoints',{})
        if not endpoints:raise ValueError('Empty endpoint family')
        for name,endpoint in endpoints.items():
            if endpoint.get('kind') not in ('parameter','predictive') or endpoint.get('probability') not in (.05,.95) or not isinstance(endpoint.get('scale'),str) or not isinstance(endpoint.get('distribution_id'),str) or not endpoint['distribution_id']:raise ValueError('Invalid endpoint definition')
        paired=[]
        for pair in spec.get('interval_pairs',[]):
            if len(pair)!=2 or any(name not in endpoints for name in pair):raise ValueError('Invalid interval pair')
            a,b=(endpoints[name] for name in pair)
            if a['probability']!=.05 or b['probability']!=.95 or a['scale']!=b['scale'] or a['kind']!=b['kind'] or a['distribution_id']!=b['distribution_id']:raise ValueError('Mismatched interval pair')
            paired.extend(pair)
        if len(paired)!=len(set(paired)) or set(paired)!=set(endpoints):raise ValueError('Every endpoint must appear in exactly one interval pair')
        if len(spec['lengths'])!=2 or spec['lengths'][1]!=2*spec['lengths'][0]:raise ValueError('Two paired doubling lengths required')
        if len({r['backend'] for r in expected.values()})!=2:raise ValueError('Two backends required')
        backend_counts=[sum(r['backend']==b for r in expected.values()) for b in {r['backend'] for r in expected.values()}]
        if len(set(backend_counts))!=1 or min(backend_counts)<2:raise ValueError('Equal independent fit count per backend required')
        for fit in fits:
            binding=expected[fit['id']]
            for key in ['backend','seed','initialization_seed','fixture_sha256','source_sha256','target_sha256']:
                if fit.get(key)!=binding.get(key) or key not in binding:raise ValueError('Fit provenance mismatch: '+key)
            if fit['source_sha256']!=spec['source_sha256'] or fit['target_sha256']!=spec['target_sha256']:raise ValueError('Bank target/source mismatch')
            for length in spec['lengths']:
                level=fit['levels'][str(length)]
                if level.get('status')!='completed' or level.get('healthy') is not True or level.get('draws_per_chain')!=length:raise ValueError('Missing, failed or unhealthy bank level')
                for name,endpoint in spec['endpoints'].items():
                    row=level['endpoints'][name]
                    if row.get('scale')!=endpoint['scale'] or row.get('distribution_id')!=endpoint['distribution_id']:raise ValueError('Endpoint scale/distribution mismatch')
                    if endpoint['kind']!='parameter' and spec['numerical_policy']=='verified_bound' and row.get('error_bound_verified') is not True:raise ValueError('Verified numerical bound required by this manifest')
                    if endpoint['kind']=='parameter' and len(row['draws'])!=spec['chains']*length:raise ValueError('Functional draw count mismatch')
        for fit in fits:
            for length in spec['lengths']:
                level=fit['levels'][str(length)]['endpoints']
                for lower,upper in spec['interval_pairs']:
                    a,b=level[lower],level[upper]
                    fields=['draws'] if spec['endpoints'][lower]['kind']=='parameter' else ['grid','cdf','cdf_error_bound','error_bound_verified','error_bound_provenance','numerical_cdf_error_estimate','numerical_checks_passed','numerical_checks_provenance']
                    if any(a.get(key)!=b.get(key) for key in fields):raise ValueError('Paired endpoints must use identical distribution data/cache')
        streams=[r[key] for r in expected.values() for key in ('seed','initialization_seed')]
        if any(isinstance(v,bool) or not isinstance(v,int) or v<0 for v in streams) or len(set(streams))!=len(streams) or set(streams)&set(spec['candidate_streams']):raise ValueError('Bank streams collide or are invalid')
        for field in ['alpha','relative_half_width','backend_equivalence_relative_width','length_equivalence_relative_width']:
            if not finite(spec.get(field)) or not 0<spec[field]<1:raise ValueError('Invalid uncertainty budget: '+field)
        for field in ['bootstrap_replicates','minimum_tail_count','bootstrap_seed']:
            if isinstance(spec.get(field),bool) or not isinstance(spec.get(field),int) or spec[field]<1:raise ValueError('Invalid bootstrap setting')
        tail=spec['alpha']/(6*len(endpoints))
        if spec['bootstrap_replicates']*tail<spec['minimum_tail_count']:raise ValueError('Bootstrap tail resolution insufficient for declared endpoint family')
        low,high=spec['lengths'];cache=prepare_parameters(fits,spec)
        point,numerical=evaluate(fits,spec,high,cache=cache);earlier,earlier_error=evaluate(fits,spec,low,cache=cache)
        difference_errors={name:numerical[name]+earlier_error[name] for name in point}
        backends=sorted({f['backend'] for f in fits});by_backend={b:[f for f in fits if f['backend']==b] for b in backends}
        backend_results={b:evaluate(rows,spec,high,cache=cache) for b,rows in by_backend.items()}
        backend_point={b:r[0] for b,r in backend_results.items()}
        backend_errors={name:sum(r[1][name] for r in backend_results.values()) for name in point}
        rng=random.Random(spec['bootstrap_seed']);draws=[];differences=[];backend_differences=[]
        vectorized=None
        if parameter_batch is not None:
            if any(e['kind']!='parameter' for e in spec['endpoints'].values()):raise ValueError('Optional batch path supports parameters only')
            all_counts=[resample_fits(fits,rng) for _ in range(spec['bootstrap_replicates'])]
            groups=[(fits,high),(fits,low)]+[(by_backend[b],high) for b in backends]
            vectorized=[{name:parameter_batch(group,cache,length,name,e['probability'],all_counts) for name,e in spec['endpoints'].items()} for group,length in groups]
        for index in range(spec['bootstrap_replicates']):
            if vectorized is None:
                counts=resample_fits(fits,rng);q,error=evaluate(fits,spec,high,counts,cache);q0,error0=evaluate(fits,spec,low,counts,cache)
                backend_resamples=[evaluate(by_backend[b],spec,high,counts,cache) for b in backends]
            else:
                results=[({name:values[index] for name,values in group.items()},{name:0. for name in point}) for group in vectorized]
                (q,error),(q0,error0)=results[:2];backend_resamples=results[2:]
            qb=[r[0] for r in backend_resamples]
            for name in point:
                difference_errors[name]=max(difference_errors[name],error[name]+error0[name])
                backend_errors[name]=max(backend_errors[name],sum(r[1][name] for r in backend_resamples))
            draws.append(q);differences.append({k:q[k]-q0[k] for k in q});backend_differences.append({k:qb[0][k]-qb[1][k] for k in q})
            for name in numerical:numerical[name]=max(numerical[name],error[name])
        tail=spec['alpha']/(2*3*len(point));bounds={}
        for name in point:
            values=[r[name] for r in draws];lo=percentile(values,tail)-numerical[name];hi=percentile(values,1-tail)+numerical[name]
            bounds[name]=dict(estimate=point[name],lower=lo,upper=hi,half_width=max(point[name]-lo,hi-point[name]),numerical_half_width=numerical[name])

        for lower,upper in spec['interval_pairs']:
            width=point[upper]-point[lower];wlow=bounds[upper]['lower']-bounds[lower]['upper']
            if width<=0 or wlow<=0:out['reasons'].append('Nonpositive conservative width: '+lower);continue
            for name in [lower,upper]:
                if bounds[name]['half_width']>spec['relative_half_width']*width:out['reasons'].append('Reference precision unresolved: '+name)
                agreement=[r[name] for r in backend_differences]
                backend_interval=[percentile(agreement,tail)-backend_errors[name],percentile(agreement,1-tail)+backend_errors[name]]
                change=[r[name] for r in differences]
                length_interval=[percentile(change,tail)-difference_errors[name],percentile(change,1-tail)+difference_errors[name]]
                bounds[name]['backend_difference_interval']=backend_interval;bounds[name]['paired_length_difference_interval']=length_interval
                if max(map(abs,backend_interval))>spec['backend_equivalence_relative_width']*width:out['reasons'].append('Backend equivalence unresolved: '+name)
                if max(map(abs,length_interval))>spec['length_equivalence_relative_width']*width:out['reasons'].append('Length stability unresolved: '+name)
                bounds[name]['W_low']=wlow
        out.update(endpoints=bounds,joint_bootstrap_endpoints=draws,paired_length_point_difference={k:point[k]-earlier[k] for k in point},backend_point=backend_point,
            bootstrap_usage='For each outer candidate resample choose ONE bank endpoint-vector resample and reuse it across every candidate replicate; do not redraw bank error per replicate')
        out['numerical_policy']=spec['numerical_policy']
        out['numerical_limitation']='Validated numerical error estimates and finite-fit bootstrap are approximate; no formal integration-error or simultaneous-coverage guarantee is implied'
        if not out['reasons']:out['status']='numerically_resolved_under_declared_checks'
    except (ValueError,KeyError,TypeError,ZeroDivisionError) as exc:out['reasons'].append(str(exc))
    return out


def cache_observed_predictive(draws,data,model,grid,order=128):
    """Observed-only cache; validation evidence must be attached separately."""
    from predictive_cdf import PredictiveMixture
    mixture=PredictiveMixture.from_flow(draws,data,group=0,x_next=0.) if model=='flow' else PredictiveMixture.from_local_level(draws,data)
    return dict(grid=list(grid),cdf=mixture.cdf(grid,order).tolist(),order=order,
        error_bound_verified=False,cdf_error_bound=None,error_bound_provenance=None,
        numerical_checks_passed=False,numerical_cdf_error_estimate=None,numerical_checks_provenance=None,
        limitation='Attach frozen refinement and independent-quadrature-control evidence before using a declared numerical error estimate; formal bounds are a separate optional policy')


