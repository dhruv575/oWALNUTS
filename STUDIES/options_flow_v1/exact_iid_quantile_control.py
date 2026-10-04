"""Exact iid continuous quantile control, independent of cluster bootstrap.

For K=#(X_i <= q_p) ~ Binomial(n,p), [X_(r),X_(s)] covers q_p iff
r <= K < s. X_(0)=-infinity, X_(n+1)=+infinity. Choose the largest r
with P(K<r)<=alpha/(2m), and smallest s with P(K>=s)<=alpha/(2m).
Bonferroni gives simultaneous coverage >=1-alpha for m prespecified quantiles,
without assuming independence between endpoints. Discreteness is conservative.
Valid for fixed-size iid samples from one continuous distribution; NOT AR/MCMC,
backend mixtures, optional stopping or subsets selected for successful fits.
Normal truth is used only for control scoring, never to construct bounds.
Reference: NIST TN2119, section on distribution-free quantile intervals:
https://nvlpubs.nist.gov/nistpubs/TechnicalNotes/NIST.TN.2119.pdf
"""
import math
from scipy.stats import binom, norm

def ranks(n,p,*,alpha=.05,family_size=2):
    if type(n)!=int or n<1 or type(family_size)!=int or family_size<1:raise ValueError('Positive integer n/family_size required')
    if isinstance(p,bool) or isinstance(alpha,bool) or not 0<p<1 or not 0<alpha<1:raise ValueError('Interior probability and alpha required')
    tail=alpha/(2*family_size)
    if tail==0:raise ValueError('Tail allocation underflow')
    lo,hi=0,n+1
    while lo+1<hi:
        mid=(lo+hi)//2
        if binom.cdf(mid-1,n,p)<=tail:lo=mid
        else:hi=mid
    lower=lo;lo,hi=0,n+1
    while lo+1<hi:
        mid=(lo+hi)//2
        if binom.sf(mid-1,n,p)<=tail:hi=mid
        else:lo=mid
    upper=hi
    lower_error=float(binom.cdf(lower-1,n,p));upper_error=float(binom.sf(upper-1,n,p))
    return dict(lower_rank=lower,upper_rank=upper,tail_budget=tail,lower_noncoverage=lower_error,upper_noncoverage=upper_error,coverage_probability=1-lower_error-upper_error)

def control(draws,*,probabilities=(.05,.95),alpha=.05,mean=0.,sd=1.,iid_confirmed=False):
    """Score every supplied fixed-size iid normal control, including misses.

    iid_confirmed is an explicit assumption acknowledgement, not an iid test.
    Infinite bounds are floats; callers must explicitly encode them if using
    strict JSON. There is no resolved-fit filter or qualification decision.
    """
    if iid_confirmed is not True:raise ValueError('Explicit iid assumption acknowledgement required')
    values=list(draws);ps=tuple(probabilities)
    if not values or any(isinstance(v,bool) or not isinstance(v,(float,int)) or not math.isfinite(v) for v in values):raise ValueError('Finite nonempty scalar sample required')
    if not ps or len(set(ps))!=len(ps):raise ValueError('Nonempty distinct prespecified quantiles required')
    if not math.isfinite(mean) or not math.isfinite(sd) or sd<=0:raise ValueError('Finite normal location and positive scale required')
    ordered=sorted(values);rows=[]
    for p in ps:
        r=ranks(len(values),p,alpha=alpha,family_size=len(ps));a=r['lower_rank'];b=r['upper_rank'];lower=-math.inf if a==0 else ordered[a-1];upper=math.inf if b==len(values)+1 else ordered[b-1];truth=float(norm.ppf(p,loc=mean,scale=sd))
        rows.append(dict(probability=p,**r,lower=lower,upper=upper,truth=truth,covered=lower<=truth<=upper))
    return dict(n=len(values),alpha=alpha,family_size=len(ps),simultaneous_coverage_lower_bound=1-alpha,rows=rows,both_or_all_covered=all(r['covered'] for r in rows),qualified=False,scope='Fixed-size iid continuous normal control only; unconditional over all attempted control samples, no success selection.')
