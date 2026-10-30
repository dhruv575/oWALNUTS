import numpy as np

def criterion(covariance,hessians,held_covariance):
    """Bales et al. (2019), Eq13; maximum over supplied held-out Hessians."""
    c=np.asarray(covariance);h=np.asarray(hessians);s=np.asarray(held_covariance)
    l=np.linalg.cholesky((c+c.T)/2)
    z=np.linalg.solve(l,s);z=np.linalg.solve(l,z.T).T;z=(z+z.T)/2
    width=float(np.linalg.eigvalsh(z).max())
    stiffness=[float(np.abs(np.linalg.eigvalsh(l.T@((a+a.T)/2)@l)).max()) for a in h]
    values=np.sqrt(np.array(stiffness)*width)
    if not np.isfinite(values).all() or min(values)<=0:raise ValueError('invalid criterion')
    return dict(maximum=float(max(values)),values=values.tolist(),width=width)
