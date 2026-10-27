"""Exact t5 CDF/SF, stable smaller-tail evaluation; no fastmath or clipping."""
import math
import numpy as np
from numba import njit, vectorize, float64
SQRT5=math.sqrt(5.0)
@njit(cache=True)
def small_tail(a):
    if math.isnan(a): return math.nan
    if math.isinf(a): return 0.0
    if a <= SQRT5:
        v=a/SQRT5; z=v*v
        return .5-(math.atan(v)+v*(5+3*z)/(3*(1+z)*(1+z)))/math.pi
    t=SQRT5/a; z=t*t
    if t > .25:
        return (math.atan(t)-t*(3+5*z)/(3*(1+z)*(1+z)))/math.pi
    # Horner, 24 fixed terms. Multiplication ordering preserves representable tails.
    p=0.0
    for n in range(23,-1,-1):
        coefficient=((n+1)*(n+2)/2)/(5+2*n)
        if n%2: coefficient=-coefficient
        p=coefficient+z*p
    return ((8/(3*math.pi))*p*t)*t*t*t*t
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
