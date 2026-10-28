"""Independent forward-simulation oracle for the fixed T=1 synthetic cell."""
import numpy as np


def reference(seed=398123781, proposals=1_000_000, batch=10_000):
    if proposals<=0 or batch<=0:raise ValueError('Positive counts required')
    rng=np.random.default_rng(seed);accepted=[];nonfinite=0
    for start in range(0,proposals,batch):
        size=min(batch,proposals-start)
        mu=rng.normal(2*np.log(.005),1,size)
        l=rng.normal(np.log(.2),.5,size)
        beta=rng.normal(0,.002,size);z=rng.normal(size=size)
        h=mu+np.exp(l)*z/np.sqrt(1-.95**2)
        with np.errstate(over='ignore',invalid='ignore'):
            x=beta+np.exp(h/2)*rng.standard_t(5,size)
        nonfinite+=int(np.count_nonzero(~np.isfinite(x)))
        keep=(x>-.0005)&(x<.0005)&np.isfinite(x)
        u=np.log(x[keep]+.0005)-np.log(.0005-x[keep])
        accepted.append(np.column_stack([mu[keep],l[keep],beta[keep],z[keep],u]))
    return np.concatenate(accepted),dict(proposals=proposals,nonfinite=nonfinite,seed=seed,batch=batch)
