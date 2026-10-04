"""Finite-N stationary Gaussian-AR indicator covariance; quantile delta is approximate.

Plackett identity: d Phi2(a,b;r)/dr = bivariate normal density(a,b;r).
Thus Cov(1{X<=a},1{Y<=b})=integral_0^r density(a,b;s)ds.
For F independent N-long paths, Cov(Fhat_p,Fhat_q) equals
[N*(min(p,q)-p*q)+2*sum((N-k)*gamma_k)]/(F*N*N).
No cluster bootstrap is used. Quadrature errors below are numerical estimates,
not certified bounds. Dividing by normal densities is an asymptotic quantile
linearization, not an exact finite-sample quantile confidence interval.
"""
import math
from functools import lru_cache
from scipy.integrate import quad
from scipy.stats import norm

@lru_cache(maxsize=100000)
def indicator_covariance(p,q,correlation,epsabs=1e-12):
    if any(isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) for v in [p,q,correlation,epsabs]) or epsabs<=0 or not 0<p<1 or not 0<q<1 or not -1<correlation<1:raise ValueError('Interior probabilities/correlation required')
    a,b=norm.ppf(p),norm.ppf(q)
    def derivative(r):return math.exp(-(a*a-2*r*a*b+b*b)/(2*(1-r*r)))/(2*math.pi*math.sqrt(1-r*r))
    if correlation==0:return 0.,0.
    value,error=quad(derivative,0.,correlation,epsabs=epsabs,epsrel=1e-10,limit=200)
    return float(value),float(error)

def finite_n_covariance(n,fits,rho,probabilities=(.05,.95),epsabs=1e-12):
    if type(n)!=int or n<1 or type(fits)!=int or fits<1 or isinstance(rho,bool) or not isinstance(rho,(int,float)) or not math.isfinite(rho) or not -1<rho<1 or isinstance(epsabs,bool) or not isinstance(epsabs,(int,float)) or not math.isfinite(epsabs) or epsabs<=0:raise ValueError('Positive integer sizes and stationaryrho required')
    ps=tuple(probabilities)
    if len(ps)!=2 or not all(not isinstance(p,bool) and isinstance(p,(int,float)) and math.isfinite(p) and 0<p<1 for p in ps):raise ValueError('Two interior endpoint probabilities required')
    covariance=[[0.,0.],[0.,0.]];error=[[0.,0.],[0.,0.]]
    for i in range(2):
        for j in range(i,2):
            terms=[n*(min(ps[i],ps[j])-ps[i]*ps[j])];errors=[]
            for k in range(1,n):
                corr=rho**k
                if corr==0:break
                value,err=indicator_covariance(ps[i],ps[j],corr,epsabs);terms.append(2*(n-k)*value);errors.append(2*(n-k)*err)
            value=math.fsum(terms)/(fits*n*n);err=math.fsum(errors)/(fits*n*n)
            covariance[i][j]=covariance[j][i]=value;error[i][j]=error[j][i]=err
    densities=[float(norm.pdf(norm.ppf(p))) for p in ps]
    delta=[[covariance[i][j]/(densities[i]*densities[j]) for j in range(2)] for i in range(2)]
    return dict(n=n,fits=fits,rho=rho,probabilities=ps,cdf_covariance=covariance,quadrature_error_estimate=error,quantile_delta_covariance=delta,quantile_interval_status='Approximate delta variance only; no exact quantile CI',formula_scope='Exact finiteN stationaryGaussianAR indicator covariance, numerically integrated')
