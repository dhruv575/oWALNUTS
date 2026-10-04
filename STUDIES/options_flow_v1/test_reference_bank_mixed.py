import sys,copy,math,statistics
from pathlib import Path
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'STUDIES/options_flow_v1'))
from reference_bank import analyze as scalar
from reference_bank_vectorized import batch_cached_parameter
from reference_bank import analyze as mixed


def bank():
    names=[f'theta{i}' for i in range(5)]+['observed'];endpoints={};pairs=[]
    for name in names:
        pair=[]
        for suffix,p in [('lo',.05),('hi',.95)]:
            key=name+'_'+suffix;pair.append(key);endpoints[key]=dict(kind='predictive' if name=='observed' else 'parameter',probability=p,scale='unit',distribution_id=name)
        pairs.append(pair)
    fits=[]
    for i in range(6):
        fit=dict(id=str(i),backend='a' if i<3 else 'b',seed=100+i,initialization_seed=200+i,fixture_sha256='fixture',source_sha256='source',target_sha256='target',levels={})
        for n in [8,16]:
            rows={}
            for name in names:
                shift=(i-2.5)*.4
                if name=='observed':
                    grid=[-6+j*.15 for j in range(81)]
                    row=dict(grid=grid,cdf=[1/(1+math.exp(-(x-shift-(.1 if n==8 else 0)))) for x in grid],numerical_cdf_error_estimate=.0001*(i+1),numerical_checks_passed=True,numerical_checks_provenance='Declared synthetic logistic-CDF control')
                else:row=dict(draws=[math.sin(j*1.1)+shift+int(name[-1])*.1 for j in range(n)])
                row.update(scale='unit',distribution_id=name)
                rows[name+'_lo']=row;rows[name+'_hi']=copy.deepcopy(row)
            fit['levels'][str(n)]=dict(status='completed',healthy=True,draws_per_chain=n,endpoints=rows)
        fits.append(fit)
    spec=dict(fits=[{k:v for k,v in f.items() if k!='levels'} for f in fits],source_sha256='source',target_sha256='target',lengths=[8,16],chains=1,endpoints=endpoints,interval_pairs=pairs,numerical_policy='validated_estimate',candidate_streams=[],bootstrap_replicates=300,minimum_tail_count=1,bootstrap_seed=321,alpha=.3,relative_half_width=.1,backend_equivalence_relative_width=.1,length_equivalence_relative_width=.1)
    return spec,fits


def test_exact_full_mixed_report_and_shared_covariance():
    spec,fits=bank();a=scalar(spec,fits);seen=[]
    def batch(*args):
        seen.append(args[-1]);return batch_cached_parameter(*args,chunk_size=17)
    b=mixed(spec,fits,parameter_batch=batch)
    assert a==b
    assert len(a['joint_bootstrap_endpoints'])==300
    assert len(seen)==40 and all(v is seen[0] for v in seen)
    vectors=a['joint_bootstrap_endpoints'];x=[v['theta0_lo'] for v in vectors];y=[v['observed_lo'] for v in vectors]
    assert statistics.variance(x)>0 and statistics.variance(y)>0
    assert sum((a-statistics.mean(x))*(b-statistics.mean(y)) for a,b in zip(x,y))>0
    assert a['endpoints']['observed_lo']['numerical_half_width']>0


@pytest.mark.parametrize('invalid',['grid','provenance','drawcount','missingfit'])
def test_invalid_mixed_matches_scalar_fail_closed(invalid):
    spec,fits=bank()
    if invalid=='missingfit':fits.pop()
    elif invalid=='drawcount':fits[0]['levels']['16']['endpoints']['theta0_lo']['draws'].pop()
    else:
        for name in ['observed_lo','observed_hi']:
            row=fits[0]['levels']['16']['endpoints'][name]
            if invalid=='grid':row['grid'][2]=row['grid'][1]
            else:row['numerical_checks_passed']=False
    assert scalar(spec,fits)==mixed(spec,fits,parameter_batch=batch_cached_parameter)
    assert mixed(spec,fits,parameter_batch=batch_cached_parameter)['status']=='reference_unresolved'


def test_optional_none_preserves_scalar_and_batch_error_is_visible():
    spec,fits=bank();assert mixed(spec,fits)==scalar(spec,fits)
    def reject(*args):raise ValueError('batch invalid')
    result=mixed(spec,fits,parameter_batch=reject)
    assert result['status']=='reference_unresolved' and 'batch invalid' in result['reasons']

