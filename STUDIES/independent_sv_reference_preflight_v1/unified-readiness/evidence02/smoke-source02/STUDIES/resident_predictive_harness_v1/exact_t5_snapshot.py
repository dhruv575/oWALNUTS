"""Exact t5 CDF/SF with stable positive tail series; no fastmath/clipping."""
import math
import numpy as np
from numba import njit, vectorize, float64
SQRT5=math.sqrt(5.0)
_coeff=[];_a=1.
for _k in range(64):
    _coeff.append(_a/(2*_k+5));_a*=(_k+.5)/(_k+1)
COEFF=np.array(_coeff)
@njit(cache=True)
def small_tail(a):
    if math.isnan(a): return math.nan
    if math.isinf(a): return 0.0
    if a <= SQRT5:
        v=a/SQRT5; z=v*v
        return .5-(math.atan(v)+v*(5+3*z)/(3*(1+z)*(1+z)))/math.pi
    v=SQRT5/math.hypot(a,SQRT5);z=v*v;p=0.0
    for n in range(63,-1,-1):p=COEFF[n]+z*p
    return ((8/(3*math.pi))*p*v)*v*v*v*v
@vectorize([float64(float64)],nopython=True,cache=True)
def cdf(x):
    q=small_tail(abs(x))
    return q if x<0 else 1-q
@vectorize([float64(float64)],nopython=True,cache=True)
def sf(x):
    q=small_tail(abs(x))
    return 1-q if x<0 else q

def stdtr5(nu,x):
    if nu!=5: raise ValueError('Exact implementation only supports nu=5')
    return cdf(x)
