import numpy as np
from scipy.stats import norm
import pytest
from posterior_resource.predictive_grid import build
class Normal:
 def __init__(self,mu):self.mu=mu
 def cdf(self,x,order):return norm.cdf(np.asarray(x)-self.mu)

def test_nondegenerate_mixtures_and_same_endpoint_cache():
 r=build({'a':Normal(-.4),'b':Normal(.8)},max_queries=1024,absolute_width=.01,scenarios=[{'a':1},{'b':1},{'a':1,'b':1},{'a':3,'b':1}])
 assert r['status']=='numerically_resolved_for_declared_scenarios'
 assert r['rows']['a']['grid']==r['rows']['b']['grid']
 for c in r['checks']:
  w=r['scenarios'][c['scenario']];lo,hi=c['bracket'];p=c['probability']
  cdf=lambda x:sum(v*norm.cdf(x-({'a':-.4,'b':.8}[k])) for k,v in w.items())/sum(w.values())
  assert cdf(lo)<p<=cdf(hi) and hi-lo<=.01

def test_cap_and_quadrature_disagreement_unresolved():
 r=build({'a':Normal(0)},max_queries=3,absolute_width=.001)
 assert r['status']=='unresolved' and r['reason']=='query_cap'
 class Unstable(Normal):
  def cdf(self,x,order):return norm.cdf(np.asarray(x)+1/order)
 assert build({'a':Unstable(0)})['reason']=='quadrature_unresolved'

def test_expanding_outer_range_and_scenario_validation():
 r=build({'a':Normal(10)},initial=(-1,1),absolute_width=.02)
 assert r['status']=='numerically_resolved_for_declared_scenarios'
 with pytest.raises(ValueError):build({'a':Normal(0)},scenarios=[{'unknown':1}])


def test_separated_uniforms_cover_unlisted_weight():
 class Uniform:
  def __init__(self,left):self.left=left
  def cdf(self,x,order):return np.clip(np.asarray(x)-self.left,0,1)
 r=build({'a':Uniform(-2),'b':Uniform(1)},initial=(-3,3),absolute_width=.02,max_queries=1024)
 assert r['all_weight_vectors_verified']
 grid=r['rows']['a']['grid'];cdf=[.1*a+.9*b for a,b in zip(r['rows']['a']['cdf'],r['rows']['b']['cdf'])]
 lo=max(x for x,v in zip(grid,cdf) if v<.05);hi=min(x for x,v in zip(grid,cdf) if v>=.05)
 assert lo<=-1.5<=hi and hi-lo<=.02

@pytest.mark.parametrize('kwargs',[{'probabilities':[]},{'absolute_width':float('nan')},{'cdf_tolerance':True},{'probabilities':[0.]}])
def test_no_vacuous_or_nan_success(kwargs):
 with pytest.raises(ValueError):build({'a':Normal(0)},**kwargs)


def test_fixed_weight_error_envelopes_match_scalar_oracle():
 from posterior_resource.predictive_grid import weighted_brackets
 rows={'a':dict(grid=[-3.,-1.,0.,1.,3.],cdf=[.001,.2,.5,.8,.999],numerical_cdf_error_estimate=.01),'b':dict(grid=[-3.,-1.,0.,1.,3.],cdf=[.001,.1,.3,.7,.999],numerical_cdf_error_estimate=.02)}
 weights=np.array([[1,0],[0,1],[1,1],[3,1]])
 result=weighted_brackets(rows,weights,probabilities=(.1,.9),absolute_width=.01,chunk=2)
 for i,w in enumerate(weights):
  c=sum(w[j]*np.array(rows[k]['cdf']) for j,k in enumerate(rows))/sum(w);e=sum(w[j]*rows[k]['numerical_cdf_error_estimate'] for j,k in enumerate(rows))/sum(w)
  for j,p in enumerate([.1,.9]):
   lo=max(x for x,v in zip(rows['a']['grid'],c) if v+e<p);hi=min(x for x,v in zip(rows['a']['grid'],c) if v-e>=p)
   np.testing.assert_array_equal(result['brackets'][i,j],[lo,hi])
 assert not result['resolved']


def test_retained_ladder_recomputes_error_and_weight_binding():
 import hashlib
 class SlightOrderChange(Normal):
  def cdf(self,x,order):return norm.cdf(np.asarray(x)+1e-10/order)
 weights=np.array([[1.,0.],[0.,1.],[1.,1.]])
 r=build({'first':SlightOrderChange(0),'second':SlightOrderChange(0)},frozen_weights=weights,absolute_width=.02)
 assert r['ordered_ids']==['first','second']
 assert r['frozen_weights_sha256']==hashlib.sha256(np.asarray(weights,dtype='<f8').tobytes(order='C')).hexdigest()
 for row in r['rows'].values():
  ladder=row['cdf_by_order'];assert list(ladder)==['16','32','64','128']
  estimate=max(np.max(np.abs(np.array(ladder['128'])-ladder['64'])),np.max(np.abs(np.array(ladder['64'])-ladder['32'])))
  assert estimate==row['numerical_cdf_error_estimate']
  assert row['cdf']==ladder['128']
 assert r['declared_weight_brackets_resolved'] and not r['all_weight_vectors_verified']
