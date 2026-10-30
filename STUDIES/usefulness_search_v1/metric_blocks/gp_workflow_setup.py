"""Pure target-data construction for the verified fixed-dimensional GP workflow."""
import numpy as np
from bounded_transport import logdet

def target_data(original,map_parameters,affine=False):
    m=map_parameters;assert m['K']==4. and len(m['mu'])==13
    cfg=dict(original);linear=np.zeros((13,13));quadratic=np.zeros((13,13,13));shift=np.zeros(13);scale=np.ones(13)
    if not affine:
        for j,part in enumerate(m['parts']):
            shift[j]=part['intercept'];scale[j]=part['s'];w=part['w'];linear[j,:j]=w[:j];index=j
            for i in range(j):
                for k in range(i,j):quadratic[j,i,k]=w[index];index+=1
            assert index==len(w)
    cfg.update(mu=m['mu'],L_map=m['L'],shift=shift.tolist(),scale=scale.tolist(),linear=linear.tolist(),quadratic=quadratic.tolist(),map_log_det=logdet(m,affine))
    return cfg
