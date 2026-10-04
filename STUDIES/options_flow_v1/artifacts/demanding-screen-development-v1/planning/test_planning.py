import sys
from pathlib import Path
import numpy as np
from scipy.stats import binom
import planning as p
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'STUDIES/options_flow_v1'))
from calibration_design import coverage_interval,operating_characteristics

def test_intervals_match_existing_scalar_exact_cases():
 for n in (1,4,20):
  lo,hi=p.intervals(n)
  for k in range(n+1):np.testing.assert_allclose([lo[k],hi[k]],coverage_interval(k,n,37),rtol=1e-13,atol=1e-15)
def test_coverage_power_matches_existing_semantics():
 for n in (20,100,800):assert abs(p.equivalence_power(n)-operating_characteristics(n,family_size=37)['per_functional_probability_of_equivalence'])<1e-12

def test_failed_fit_bounds_and_dependence_union():
 r=p.plan(800,.98);assert abs(r['usable_and_covering']-.882)<1e-12
 assert np.allclose(r['worst_case_population_coverage'],[.882,.902])
 assert 0<=r['joint18_plus_reliability_power_lower']<=r['per_selector_worst_case_power_lower']<=1
 assert r['joint18_plus_reliability_power_lower']<=r['reliability_power']
def test_no_failure_reduces_worst_case_to_ordinary_equivalence():
 r=p.plan(800,1)
 assert abs(r['per_selector_worst_case_power_lower']-p.equivalence_power(800))<1e-12
