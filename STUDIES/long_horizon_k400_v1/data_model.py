"""Fresh paired stream construction; called only after frozen campaign admission."""
import hashlib,math
import numpy as np

def generate(seed,rng_factory=np.random.default_rng):
    parameters={};phase='parameters';rng=rng_factory(seed)
    try:
        parameters['mu']=float(rng.normal(2*np.log(.005),1.));parameters['log_sigma']=float(rng.normal(np.log(.2),.5));parameters['beta']=float(rng.normal(0,.002));phase='innovations'
        z=rng.normal(size=2251);noise=rng.standard_t(5,size=2251);sigma=np.exp(parameters['log_sigma'])
        if not np.isfinite(list(parameters.values())).all() or not np.isfinite(sigma) or sigma<=0:raise ValueError('unrepresentable prior draw')
        phase='latent_path';h=np.empty(2251);h[0]=parameters['mu']+sigma*z[0]/np.sqrt(1-.95**2)
        for i in range(1,2251):h[i]=parameters['mu']+.95*(h[i-1]-parameters['mu'])+sigma*z[i]
        shifted=h.copy();shifted[1250:]+=2*np.log(2)
        phase='paired_returns'
        with np.errstate(over='raise',invalid='raise',under='ignore'):
            scale=np.exp(h/2);shift_scale=np.exp(shifted/2)
            if np.any(scale<=0) or np.any(shift_scale<=0):raise ValueError('unrepresentable return scale')
            control=parameters['beta']+scale*noise;shift=parameters['beta']+shift_scale*noise
        if not all(np.isfinite(a).all() for a in (h,shifted,control,shift)):raise ValueError('nonfinite generated stream')
        if not np.array_equal(control[:1250],shift[:1250]):raise ValueError('paired prefix differs')
        return dict(seed=seed,parameters=parameters,control_y=control,shift_y=shift,control_h=h,shift_h=shifted,first_shifted_index=1250)
    except Exception as exc:
        error=RuntimeError(str(exc));error.payload=dict(seed=seed,parameters=parameters,phase=phase,error=repr(exc));raise error from exc

def canonical_targets(checkpoints):
    return [('control',tick) for tick in checkpoints]+[('shift',tick) for tick in checkpoints if tick>1000]

def canonical(variant,tick):return ('control' if tick<=1000 else variant,tick)
