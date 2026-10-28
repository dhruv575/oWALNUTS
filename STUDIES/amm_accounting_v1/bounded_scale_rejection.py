"""Independent T1 posterior draws via a bounded Gaussian beta prior envelope."""
import numpy as np
from scipy.stats import truncnorm


def draw(cap,y,proposals,seed,batch=10000):
    if not np.isfinite(cap) or cap<=0 or not np.isfinite(y) or type(proposals)is not int or proposals<1 or type(batch)is not int or batch<1:raise ValueError('Finite parameters and positive proposal budget')
    rng=np.random.default_rng(seed);accepted=[];m=np.log(.2);sd=.5
    for start in range(0,proposals,batch):
        size=min(batch,proposals-start)
        mu=rng.normal(2*np.log(.005),1,size);l=truncnorm.rvs(-np.inf,(np.log(cap)-m)/sd,loc=m,scale=sd,size=size,random_state=rng)
        z=rng.normal(size=size);h=mu+np.exp(l)*z/np.sqrt(1-.95**2)
        beta=y+np.exp(h/2)*rng.standard_t(5,size=size)
        gap=np.log(cap)-l
        if not np.isfinite(beta).all() or not np.all(gap>0):raise ValueError('Nonfinite proposal or cap rounding')
        eta=gap+np.log(-np.expm1(-gap))
        with np.errstate(divide='ignore'):keep=np.log(rng.random(size))<-.5*(beta/.002)**2
        accepted.append(np.column_stack((mu[keep],eta[keep],beta[keep],z[keep])))
    result=np.concatenate(accepted)
    if not np.isfinite(result).all():raise ValueError('Nonfinite accepted draws')
    return result
