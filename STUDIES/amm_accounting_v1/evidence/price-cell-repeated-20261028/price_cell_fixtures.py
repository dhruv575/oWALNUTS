"""Deterministic stress fixtures; no claim of prior draws or calibration."""
import numpy as np


def fixture(n,width):
    if n not in (12,250) or width not in (.001,.00001):
        raise ValueError('Outside fixed stress design')
    # Repeated exact latent levels intentionally exercise repeated cells.
    i=np.arange(n,dtype=float)
    latent=.003*np.sin(i*.17)+.001*np.sin(i*.61)
    latent[1::5]=latent[::5][:len(latent[1::5])]
    bins=np.floor(latent/width+.5)
    center=bins*width
    lower=center-width/2;upper=center+width/2
    if not np.all((latent>=lower)&(latent<upper)):raise ValueError('Cell membership')
    return dict(n=n,lower_cell=lower,upper_cell=upper,initial=0.,rho=.95),latent
