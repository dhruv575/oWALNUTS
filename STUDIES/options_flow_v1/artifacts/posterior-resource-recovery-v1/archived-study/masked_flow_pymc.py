"""Public PyMC noncentered adapter for the separate masked-flow experiment."""
import numpy as np
from masked_flow import validate


def build_model(data,block_size=32):
    import pymc as pm
    import pytensor.tensor as pt
    from pymc_flow_workflow import ar_path
    from flow_starts import canonical_starts,to_noncentered
    y,x,mask=validate(data);t,g=y.shape;k=4+2*g
    # Strict flow helper only needs finite placeholders for canonical-start shape.
    clean=dict(data,y=np.where(mask,y,0.).tolist(),x=np.where(mask,x,0.).tolist())
    provided=data.get('initial_positions');chains=1 if provided is None else len(provided)
    initial=to_noncentered(canonical_starts(clean,chains),clean)[0]
    with pm.Model() as model:
        q=pm.Flat('q',shape=k+t,initval=initial)
        lp=pt.sum(pm.logp(pm.Normal.dist(mu=np.array([0.,-1.,-1.,-1.5]),sigma=np.array([.5,.5,1.,.5])),q[:4]))
        lp+=pt.sum(pm.logp(pm.Normal.dist(mu=np.float64(0),sigma=np.float64(1)),q[4:]))
        if mask.any():
            ti,gi=np.nonzero(mask)
            h=ar_path(q[k:],q[2],pt.exp(q[3]),np.float64(data['rho']),t,block_size)
            location=np.float64(.3)*q[4+gi]+(q[0]+pt.exp(q[1])*q[4+g+gi])*np.array(x[ti,gi],copy=True)
            lp+=pt.sum(pm.logp(pm.StudentT.dist(nu=np.float64(data['nu']),mu=location,sigma=pt.exp(h[ti]/np.float64(2))),np.array(y[ti,gi],copy=True)))
        pm.Potential('masked_noncentered_flow',lp)
    return model


def compile_target(data,block_size=32):
    import owalnuts
    return owalnuts.from_pymc(build_model(data,block_size),gil_free=True)
