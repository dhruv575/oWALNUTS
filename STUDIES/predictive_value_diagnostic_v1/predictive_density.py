"""Observed-return predictive density/PIT, deterministic GH64/128, no sampling.

Inputs retain original (chain, draw, [mu, log_sigma, beta, h_last]) axes.
Deadline is an absolute time.monotonic() timestamp. Failures never return a
partially accepted score. ArviZ/MCSE estimation belongs to the caller.
"""
import hashlib
import importlib.util
import math
import sys
import time
from pathlib import Path

import numpy as np
import scipy
from numpy.polynomial.hermite import hermgauss
from scipy.special import logsumexp

HERE=Path(__file__).resolve().parent
EXACT_PATH=HERE.parent/'resident_predictive_harness_v1/exact_t5_snapshot.py'
EXACT_SHA='94c767c783623e99f1f60d7bf5b0766f72b96975ac6ec088218da994ef7b33f3'
LOG_C5=math.log(8/(3*math.pi*math.sqrt(5)))
LOG5=math.log(5)
ORDERS=(64,128)
_GRIDS={}
_EXACT=None

class NumericalFailure(ValueError):
    """Invalid input or a failed fixed numerical check; no usable score."""

class IntegrationDisagreement(NumericalFailure):
    def __init__(self,diagnostics):
        self.diagnostics=diagnostics
        super().__init__('GH64/128 predictive discrepancy exceeds fixed tolerance')

def _check_deadline(deadline):
    if deadline is not None and time.monotonic()>=deadline:
        raise TimeoutError('predictive observation deadline exceeded')

def _exact_cdf():
    global _EXACT
    if _EXACT is None:
        if hashlib.sha256(EXACT_PATH.read_bytes()).hexdigest()!=EXACT_SHA:
            raise NumericalFailure('Exact-t5 implementation hash mismatch')
        name='exact_t5_snapshot'
        if name in sys.modules:
            module=sys.modules[name]
            if hashlib.sha256(Path(module.__file__).read_bytes()).hexdigest()!=EXACT_SHA:
                raise NumericalFailure('Conflicting loaded exact-t5 implementation')
            _EXACT=module.cdf
            return _EXACT
        spec=importlib.util.spec_from_file_location(name,EXACT_PATH)
        module=importlib.util.module_from_spec(spec)
        sys.modules[name]=module
        spec.loader.exec_module(module)
        _EXACT=module.cdf
    return _EXACT

def implementation_identity():
    return dict(source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        exact_t5_sha256=hashlib.sha256(EXACT_PATH.read_bytes()).hexdigest(),
        numpy=np.__version__,scipy=scipy.__version__,orders=list(ORDERS),
        mixture='uniform over all supplied joint posterior draws')

def _grid(order):
    if order not in _GRIDS:
        z,w=hermgauss(order);z=np.sqrt(2)*z;w=w/np.sqrt(np.pi)
        if not np.isfinite(z).all() or not np.isfinite(w).all() or np.any(w<=0) or abs(w.sum()-1)>1e-12:
            raise NumericalFailure('Invalid Gaussian quadrature grid')
        w=w/w.sum()  # Explicit normalized probabilities, same for PDF and CDF.
        _GRIDS[order]=(z,w,np.log(w))
    return _GRIDS[order]

def _signed_log_residual(y,beta):
    # An overflow in finite y-beta has a finite logarithm; opposite signs add magnitudes.
    with np.errstate(over='ignore',divide='ignore',invalid='raise'):
        residual=y-beta;logs=np.log(np.abs(residual));sign=np.sign(residual)
        large=np.isinf(residual)
        if np.any(large):logs[large]=np.logaddexp(np.log(abs(y)),np.log(np.abs(beta[large])))
    return sign,logs

def density_mcse_inputs(logpdf_by_chain_draw):
    """Positive-density scaling for MCSE(mean density)/mean density.

Return scaled_density in the original chain/draw shape. A chain-aware mean-MCSE
of this array divided by mean_scaled_density is the delta-method log-score MCSE.
It is NOT MCSE of the logpdf array; no independence/precision guarantee is made.
"""
    logs=np.asarray(logpdf_by_chain_draw,dtype=np.float64)
    if logs.ndim!=2 or not logs.size or not np.isfinite(logs).all():
        raise NumericalFailure('Expected finite nonempty chain/draw log densities')
    shift=float(np.max(logs))
    with np.errstate(over='ignore',under='ignore'):
        scaled=np.exp(logs-shift)
    mean=float(np.mean(scaled))
    if not np.isfinite(mean) or mean<=0:raise NumericalFailure('Invalid density scaling')
    return dict(scaled_density=scaled,log_scale=shift,mean_scaled_density=mean,
        log_mean_density=shift+math.log(mean),scaled_underflow_count=int(np.sum(scaled==0)))

def _evaluate_order(m,sigma,beta,y,shape,order,chunk,deadline):
    z,w,logw=_grid(order);cdf=_exact_cdf();count=len(m)
    logs=np.empty(count);pits=np.empty(count);roundoff_clips=0
    for lo in range(0,count,chunk):
        _check_deadline(deadline);hi=min(lo+chunk,count)
        sign,logabs=_signed_log_residual(y,beta[lo:hi])
        with np.errstate(over='raise',invalid='raise',under='ignore'):
            h=m[lo:hi,None]+sigma[lo:hi,None]*z
            loga=2*logabs[:,None]-h-LOG5
            logdensity=LOG_C5-h/2-3*np.logaddexp(0,loga)
            integrated=logsumexp(logdensity+logw,axis=1)
        if not np.isfinite(integrated).all():raise NumericalFailure('Nonfinite integrated density')
        # Infinite standardized arguments are valid t5 CDF limits; density stays log-space.
        with np.errstate(over='ignore',under='ignore',invalid='raise'):
            standardized=sign[:,None]*np.exp(logabs[:,None]-h/2)
        conditional=cdf(standardized)
        if not np.isfinite(conditional).all():raise NumericalFailure('Nonfinite conditional CDF')
        u=conditional@w
        eps=32*np.finfo(float).eps
        if not np.isfinite(u).all() or np.any(u < -eps) or np.any(u > 1+eps):
            raise NumericalFailure('Predictive CDF outside probability range')
        roundoff_clips+=int(np.sum((u<0)|(u>1)))
        logs[lo:hi]=integrated;pits[lo:hi]=np.clip(u,0,1)
        _check_deadline(deadline)
    logpdf=float(logsumexp(logs)-math.log(count));pit=float(np.mean(pits))
    if not np.isfinite(logpdf) or not np.isfinite(pit):raise NumericalFailure('Nonfinite predictive aggregate')
    return dict(order=order,logpdf=logpdf,pit=pit,logpdf_by_chain_draw=logs.reshape(shape),
        pit_by_chain_draw=pits.reshape(shape),cdf_roundoff_clip_count=roundoff_clips)

def evaluate_observation(draws,y,*,rho=.95,nu=5,orders=ORDERS,chunk=512,deadline=None):
    """Full mixture observed logpdf/PIT, GH128 primary; tolerances fixed at1e-6.

Chunk bounds node matrices; there is no full component-by-node cache. Inputs,
per-draw outputs and their density-MCSE scaling still require O(chains*draws) memory.
"""
    started=time.monotonic();_check_deadline(deadline)
    if deadline is not None and not math.isfinite(deadline):raise NumericalFailure('Invalid deadline')
    if tuple(orders)!=ORDERS:raise NumericalFailure('Only frozen GH64/128 comparison is supported')
    if isinstance(chunk,bool) or not isinstance(chunk,(int,np.integer)) or not 1<=chunk<=4096:
        raise NumericalFailure('Chunk must be an integer in1..4096')
    if np.ndim(y)!=0 or not np.isfinite(y):raise NumericalFailure('Observed return must be finite scalar')
    if not np.isfinite(rho) or abs(rho)>=1 or nu!=5:raise NumericalFailure('Requires |rho|<1 and nu=5')
    a=np.asarray(draws,dtype=np.float64)
    if a.ndim!=3 or a.shape[-1]!=4 or not a.shape[0] or not a.shape[1] or not np.isfinite(a).all():
        raise NumericalFailure('Expected finite nonempty (chain,draw,4) joint samples')
    shape=a.shape[:2];flat=a.reshape(-1,4)
    with np.errstate(over='raise',invalid='raise',under='ignore'):
        sigma=np.exp(flat[:,1]);m=flat[:,0]+rho*(flat[:,3]-flat[:,0])
    if not np.isfinite(sigma).all() or np.any(sigma<=0) or not np.isfinite(m).all():
        raise NumericalFailure('Invalid innovation scale/predictive location')
    results=[_evaluate_order(m,sigma,flat[:,2],float(y),shape,n,chunk,deadline) for n in ORDERS]
    low,primary=results
    numerical=dict(orders=list(ORDERS),logpdf_absolute_difference=abs(low['logpdf']-primary['logpdf']),
        pit_absolute_difference=abs(low['pit']-primary['pit']),logpdf_tolerance=1e-6,pit_tolerance=1e-6,
        max_per_draw_logpdf_difference=float(np.max(abs(low['logpdf_by_chain_draw']-primary['logpdf_by_chain_draw']))),
        max_per_draw_pit_difference=float(np.max(abs(low['pit_by_chain_draw']-primary['pit_by_chain_draw']))),
        aggregate_by_order=[dict(order=r['order'],logpdf=r['logpdf'],pit=r['pit'],cdf_roundoff_clip_count=r['cdf_roundoff_clip_count']) for r in results],
        chunk=int(chunk),max_node_matrix_elements=min(chunk,len(flat))*128,uses_full_node_cache=False)
    if numerical['logpdf_absolute_difference']>1e-6 or numerical['pit_absolute_difference']>1e-6:
        raise IntegrationDisagreement(numerical)
    scaled=density_mcse_inputs(primary['logpdf_by_chain_draw'])
    residual=abs(scaled['log_mean_density']-primary['logpdf'])
    tolerance=64*np.finfo(float).eps*max(1,abs(primary['logpdf']))
    numerical['density_scaling_identity_residual']=residual
    numerical['density_scaling_identity_tolerance']=tolerance
    if residual>tolerance:raise NumericalFailure('Density scaling identity failed')
    primary.update(numerical=numerical,density_mcse=scaled,elapsed_seconds=time.monotonic()-started)
    _check_deadline(deadline)
    return primary
