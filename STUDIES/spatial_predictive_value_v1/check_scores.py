from scoring_worker import empirical,analytic,mixture
from common import *
from scipy.stats import poisson,nbinom
x=np.array([0,1,3]);w=np.array([.2,.3,.5]);y=2
score,_=empirical(y,x,w);brute=w@abs(x-y)-.5*np.sum(w[:,None]*w[None,:]*abs(x[:,None]-x[None,:]));assert abs(score-brute)<1e-12
rows=[]
for dist in [poisson(5),nbinom(2,.3)]:
    k=np.arange(500);p=dist.pmf(k);assert abs(p.sum()-1)<1e-12
    direct=p@abs(k-y)-.5*np.sum(p[:,None]*p[None,:]*abs(k[:,None]-k[None,:]))
    result=analytic(np.array([y]),[dist])[0];assert abs(result['crps']-direct)<1e-10
    rows.append(dict(crps=result['crps'],direct=direct))
result=mixture(np.array([y]),lambda i:np.full(8192,6.25),np.ones(8192),955000099)[0]
assert abs(result['log_score']-poisson.logpmf(y,5))<1e-12 and abs(result['mean']-5)<1e-12 and abs(result['variance']-5)<1e-12
assert abs(result['crps']-rows[0]['crps'])<.05
write(BASE/'SCORE-CHECKS.json',dict(passed=True,analytic=rows,constant_mixture=result))
