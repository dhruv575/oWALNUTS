"""Exact-binomial planning; dependence-robust union lower bounds, not qualification."""
import json,math
from pathlib import Path
import numpy as np
from scipy.stats import beta,binom
ALPHA=.05;FAMILY=37

def intervals(n):
 k=np.arange(n+1);a=ALPHA/FAMILY/2
 lo=np.zeros(n+1);hi=np.ones(n+1)
 lo[1:]=beta.ppf(a,k[1:],n-k[1:]+1);hi[:-1]=beta.ppf(1-a,k[:-1]+1,n-k[:-1])
 return lo,hi

def equivalence_power(n,p=.9):
 lo,hi=intervals(n);accepted=(lo>=.85)&(hi<=.95)
 return float(binom.pmf(np.arange(n+1)[accepted],n,p).sum())

def plan(n,success=.99,coverage=.9):
 # Worst-case failed intervals: lower bound for H/N and upper for(H+F)/N.
 # H~Binomial(n,s*c), U=H+F~Binomial(n,1-s+s*c).
 # Their dependence does not invalidate the union bound used below.
 lo,hi=intervals(n);k=np.arange(n+1)
 lower=float(binom.pmf(k[lo>=.85],n,success*coverage).sum())
 upper=float(binom.pmf(k[hi<=.95],n,1-success+success*coverage).sum())
 reliability=float(binom.pmf(k[lo>=.95],n,success).sum())
 per=max(0.,lower+upper-1)
 joint=max(0.,1-18*(2-lower-upper)-(1-reliability))
 # This diagnostic's probability is conditional on usability, NOT overall coverage.
 conditional_at_expected=equivalence_power(max(1,int(n*success)),coverage)
 return dict(n=n,success_probability=success,conditional_coverage=coverage,usable_and_covering=success*coverage,worst_case_population_coverage=[success*coverage,1-success+success*coverage],per_selector_worst_case_power_lower=per,joint18_plus_reliability_power_lower=joint,reliability_power=reliability,conditional_power_at_floor_expected_usable_count_only=conditional_at_expected,public_hours=n*75.26865346390211/3600,reference10percent_hours=math.ceil(n*.1)*89.43014267221831/3600)

def minimum(success,target=.8,limit=20000):
 # Scan every integer: no unproved monotonicity assumption for discrete bounds.
 for n in range(1,limit+1):
  r=plan(n,success)
  if r['joint18_plus_reliability_power_lower']>=target:return r
 return dict(success_probability=success,not_found_through=limit)

def main():
 results=dict(alpha=ALPHA,family_size=FAMILY,interpretation='37 CP intervals:18Hlower/18Uupper/1successlower; two-sided CP conservatively retained. Union lower power bound across18 selectors and reliability, no endpoint independence assumption. Conditional-success coverage is descriptive and cannot substitute.',grid=[plan(n,s) for s in (1.,.995,.99,.98,.95) for n in (800,1200,1600)],minimum80percent_joint=[minimum(s,limit=6000) for s in (1.,.995,.99,.98)],boundary_note='At true success=.95, probability of certifying lower bound>=.95 cannot approach80%; at success<=.85/.90≈.94444 worst-case missing-fit lower coverage cannot exceed.85 even at infinite N.')
 out=Path(__file__).with_name('planning-results.json')
 with out.open('x') as f:json.dump(results,f,indent=2,allow_nan=False)
 print(json.dumps(results['minimum80percent_joint'],indent=2))
if __name__=='__main__':main()
