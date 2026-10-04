"""Independent one-step predictive mixture CDFs and deterministic quantiles.

Each canonical posterior draw contributes a Student-t CDF integrated over its
future Gaussian innovation. Gauss-Hermite quadrature removes the additional
one-noise-draw simulation used by the ordinary predictor; posterior Monte Carlo
error remains. Flow outputs are observations at supplied x_next/group. Local
outputs are observed LOG prices at dt=1, never exponentiated-price moments.

Memory is O(number_of_draws + chunk_size*quadrature_order); CDF evaluations are
O(number_of_draws*quadrature_order). No inference, SBC, MCSE, or reference-bank
accuracy claim follows from quadrature convergence.
"""
from __future__ import annotations

from dataclasses import dataclass
import math

import numpy as np
from scipy.optimize import brentq
from scipy.special import roots_hermitenorm, stdtr


ORDERS = (16, 32, 64, 128)


def equal_fit_weights(draw_counts):
    """Equal weight per independent fit, then equal draw weight within each fit.

    Concatenate draws in the same fit order. This weights a pooled mixture CDF,
    not an average of independently computed fit quantiles.
    """
    counts = list(draw_counts)
    if not counts or any(isinstance(n, bool) or not isinstance(n, (int, np.integer)) or n < 1 for n in counts):
        raise ValueError('Positive integer draw count per independent fit required')
    return np.concatenate([np.full(n, 1./(len(counts)*n)) for n in counts])


def _canonical(draws, dimension, chunk_size):
    if isinstance(chunk_size, bool) or not isinstance(chunk_size, int) or chunk_size < 1:
        raise ValueError('chunk_size must be a positive integer')
    q = np.asarray(draws, dtype=float)
    if q.ndim < 1 or q.shape[-1] != dimension or q.size == 0:
        raise ValueError('Canonical draw dimension does not match the model layout')
    q = q.reshape(-1, dimension)
    for start in range(0, len(q), chunk_size):
        if not np.isfinite(q[start:start+chunk_size]).all():
            raise ValueError('Canonical posterior draws must all be finite')
    return q


def _weights(weights, count):
    if weights is None:
        return np.full(count, 1./count)
    w = np.asarray(weights, float).reshape(-1)
    if len(w) != count or not np.isfinite(w).all() or (w < 0).any() or not (w > 0).any():
        raise ValueError('One finite nonnegative weight per draw with positive total required')
    # Scaling first avoids overflow from summing otherwise valid large weights.
    w = w/w.max()
    return w/w.sum()


def _positive_exp(log_values, label):
    with np.errstate(over='ignore', under='ignore'):
        values = np.exp(log_values)
    if not np.isfinite(values).all() or (values <= 0).any():
        raise ValueError(label+' is not representable as a positive finite scale')
    return values


def _multiplier(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
        raise ValueError('Future innovation multiplier must be finite and nonnegative')
    return float(value)


@dataclass
class PredictiveMixture:
    """Construct with from_flow/from_local_level; arrays contain one row per draw."""
    kind: str
    location: np.ndarray
    future_mean: np.ndarray
    future_sd: np.ndarray
    observation_log_scale: np.ndarray
    weights: np.ndarray
    nu: float
    chunk_size: int
    metadata: dict

    @classmethod
    def from_flow(cls, draws, data, group=0, x_next=0., weights=None,
                  chunk_size=2048, future_innovation_multiplier=1.):
        """Layout: 4 globals, G z_alpha, G z_beta, T centered latent h values.

        h_next ~ Normal(mu+rho*(h_terminal-mu), exp(log_sigma_h)).
        y_next|h_next ~ StudentT(nu, alpha_g+beta_g*x_next, exp(h_next/2)).
        Multiplier zero is an explicitly labelled analytic-control modification.
        """
        y = np.asarray(data['y'])
        if y.ndim != 2 or min(y.shape) < 1:
            raise ValueError('Flow data requires a nonempty T by G shape')
        t, g = y.shape
        if isinstance(group, bool) or not isinstance(group, (int, np.integer)) or not 0 <= group < g:
            raise ValueError('group is outside the canonical model group range')
        rho, nu = float(data['rho']), float(data['nu'])
        if not np.isfinite([rho, nu, x_next]).all() or abs(rho) >= 1 or nu <= 2:
            raise ValueError('Finite x_next, abs(rho)<1 and nu>2 required')
        multiplier = _multiplier(future_innovation_multiplier)
        q = _canonical(draws, 4+2*g+t, chunk_size)
        tau = _positive_exp(q[:, 1], 'hierarchical scale')
        location = .3*q[:, 4+group]+(q[:, 0]+tau*q[:, 4+g+group])*float(x_next)
        future_mean = q[:, 2]+rho*(q[:, -1]-q[:, 2])
        future_sd = np.zeros(len(q)) if multiplier == 0 else _positive_exp(q[:, 3], 'future innovation scale')*multiplier
        if not np.isfinite(location).all() or not np.isfinite(future_mean).all() or not np.isfinite(future_sd).all():
            raise ValueError('Derived predictive parameters are not representable')
        return cls('flow', location.copy(), future_mean.copy(), future_sd.copy(),
                   np.zeros(len(q)), _weights(weights, len(q)), nu, chunk_size,
                   {'model':'flow','scale':'observed outcome','horizon':1,'group':int(group),
                    'x_next':float(x_next),'canonical_dimension':q.shape[1],
                    'future_innovation_multiplier':multiplier,'analytic_control':multiplier != 1.})

    @classmethod
    def from_local_level(cls, draws, data, weights=None, chunk_size=2048,
                         future_innovation_multiplier=1.):
        """Layout: T centered h values, log_sigma_obs, log_sigma_rw; dt=1.

        h_next ~ Normal(h_terminal, exp(log_sigma_rw)); observed log price has
        Student-t(5) location h_next and scale exp(log_sigma_obs).
        """
        y = np.asarray(data['y'])
        if y.ndim != 1 or len(y) < 1 or float(data.get('nu', 5.)) != 5.:
            raise ValueError('Local-level data requires a nonempty vector and nu=5')
        multiplier = _multiplier(future_innovation_multiplier)
        q = _canonical(draws, len(y)+2, chunk_size)
        _positive_exp(q[:, -2], 'observation scale')
        future_sd = np.zeros(len(q)) if multiplier == 0 else _positive_exp(q[:, -1], 'future innovation scale')*multiplier
        if not np.isfinite(future_sd).all():
            raise ValueError('Future innovation scale is not representable')
        return cls('local_level', np.zeros(len(q)), q[:, -3].copy(), future_sd.copy(),
                   q[:, -2].copy(), _weights(weights, len(q)), 5., chunk_size,
                   {'model':'local_level','scale':'observed log price','horizon':1,'dt':1.,
                    'canonical_dimension':q.shape[1],
                    'future_innovation_multiplier':multiplier,'analytic_control':multiplier != 1.})

    def _cdf_scalar(self, value, nodes, gaussian_weights):
        if math.isnan(value):
            raise ValueError('CDF evaluation point cannot be NaN')
        if value == -math.inf:return 0.
        if value == math.inf:return 1.
        chunks = []
        for start in range(0, len(self.weights), self.chunk_size):
            stop = min(start+self.chunk_size, len(self.weights))
            future = self.future_mean[start:stop, None]+self.future_sd[start:stop, None]*nodes
            if not np.isfinite(future).all():
                raise FloatingPointError('Gaussian quadrature nodes exceed representable latent states')
            if self.kind == 'flow':
                residual = value-self.location[start:stop, None]
                log_scale = future/2
            elif self.kind == 'local_level':
                residual = value-future
                log_scale = self.observation_log_scale[start:stop, None]
            else:
                raise ValueError('Unknown predictive model')
            if not np.isfinite(residual).all():
                raise FloatingPointError('Observation residual exceeds representable range')
            # Log-standardization tolerates extreme conditional scales. Infinite
            # standardized arguments are legitimate CDF tails; 0*infinity is
            # avoided so the symmetric center is exactly standardized zero.
            with np.errstate(over='ignore', under='ignore', divide='ignore', invalid='ignore'):
                standardized = np.sign(residual)*np.exp(np.log(np.abs(residual))-log_scale)
                standardized = np.where(residual == 0, 0., standardized)
            if np.isnan(standardized).any():
                raise FloatingPointError('Nonrepresentable standardized observation')
            conditional = stdtr(self.nu, standardized)
            integrals = conditional@gaussian_weights
            chunks.append(float(np.dot(self.weights[start:stop], integrals)))
        value = math.fsum(chunks)
        if not math.isfinite(value) or not -1e-12 <= value <= 1+1e-12:
            raise FloatingPointError('Quadrature did not produce a finite probability')
        return min(1., max(0., value))

    def cdf(self, values, order=64):
        """Weighted posterior mixture CDF, integrated separately per draw."""
        if isinstance(order, bool) or not isinstance(order, int) or order < 2:
            raise ValueError('Quadrature order must be an integer >=2')
        nodes, gaussian_weights = roots_hermitenorm(order)
        gaussian_weights = gaussian_weights/gaussian_weights.sum()
        values = np.asarray(values, float)
        out = np.asarray([self._cdf_scalar(float(v), nodes, gaussian_weights)
                          for v in values.reshape(-1)]).reshape(values.shape)
        return float(out) if out.ndim == 0 else out

    def _initial_bracket(self):
        centers = self.location if self.kind == 'flow' else self.future_mean
        center = float(np.median(centers))
        logs = self.future_mean/2 if self.kind == 'flow' else self.observation_log_scale
        # This is only a starting scale for a checked expanding bracket, never a
        # predictive variance approximation or a change to the distribution.
        typical_scale = math.exp(min(300., max(-300., float(np.median(logs)))))
        step = max(typical_scale, float(np.median(np.abs(centers-center))), 1e-8)
        if self.kind == 'local_level':step = max(step, float(np.median(self.future_sd)))
        return center, step

    def _quantiles_at_order(self, probabilities, order, root_xtol, cdf_tolerance, max_expansions):
        nodes, gaussian_weights = roots_hermitenorm(order)
        gaussian_weights = gaussian_weights/gaussian_weights.sum()
        cdf = lambda v:self._cdf_scalar(float(v), nodes, gaussian_weights)
        center, step = self._initial_bracket()
        low, high = center-step, center+step
        expansions = 0
        while not (cdf(low) <= probabilities[0] and cdf(high) >= probabilities[-1]):
            if expansions >= max_expansions:
                raise RuntimeError('Quantile bracket did not contain requested probability range')
            step *= 2
            low, high = center-step, center+step
            if not math.isfinite(low) or not math.isfinite(high):
                raise FloatingPointError('Quantile bracket overflow')
            expansions += 1
        values=[]; roots=[]
        for probability in probabilities:
            value, info = brentq(lambda v:cdf(v)-probability, low, high,
                                xtol=root_xtol, rtol=8*np.finfo(float).eps,
                                maxiter=200, full_output=True, disp=False)
            residual = abs(cdf(value)-probability)
            if not info.converged or residual > cdf_tolerance:
                raise RuntimeError('Quantile root solver failed its CDF residual tolerance')
            values.append(float(value))
            roots.append({'probability':float(probability),'cdf_residual':float(residual),
                          'iterations':int(info.iterations),'converged':bool(info.converged)})
        return {'order':order,'quantiles':values,'roots':roots,'bracket':[float(low),float(high)],
                'bracket_expansions':expansions}

    def quantiles(self, probabilities=(.05,.95), relative_tolerance=.0002,
                  root_xtol=1e-10, cdf_tolerance=1e-8, max_expansions=80):
        """Run the complete 16/32/64/128 ladder; never silently accept its cap.

        Require BOTH final successive changes (32->64 and 64->128) to be no
        larger than .0002 of the final interval width, by default. Earlier
        changes are also retained. This numerical convergence diagnostic is not
        a rigorous quadrature-error bound or a posterior MCSE estimate.
        """
        probabilities=np.asarray(probabilities,float)
        if probabilities.ndim != 1 or len(probabilities)<2 or not np.isfinite(probabilities).all() or probabilities[0]<=0 or probabilities[-1]>=1 or (np.diff(probabilities)<=0).any():
            raise ValueError('At least two strictly increasing probabilities inside (0,1) required')
        if not all(math.isfinite(v) and v>0 for v in [relative_tolerance,root_xtol,cdf_tolerance]):
            raise ValueError('Positive finite numerical tolerances required')
        if isinstance(max_expansions,bool) or not isinstance(max_expansions,int) or max_expansions<0:
            raise ValueError('Nonnegative integer bracket expansion cap required')
        report={'metadata':dict(self.metadata),'posterior_draw_count':len(self.weights),
                'probabilities':probabilities.tolist(),'orders':list(ORDERS),
                'relative_tolerance':relative_tolerance,'root_xtol':root_xtol,
                'cdf_tolerance':cdf_tolerance,'required_final_successive_changes':2,
                'ladder':[],'quantiles':None,'provisional_quantiles':None,
                'status':'quadrature_unresolved','numerical_reference_ready':False,
                'posterior_reference_qualified':False,
                'limitation':'Only Gaussian-innovation integration and mixture inversion are checked. Posterior bank uncertainty, bias, and endpoint MCSE validation remain separate.'}
        for order in ORDERS:
            try:
                row=self._quantiles_at_order(probabilities,order,root_xtol,cdf_tolerance,max_expansions)
                report['ladder'].append(row)
            except (ValueError,RuntimeError,FloatingPointError,OverflowError) as exc:
                report['ladder'].append({'order':order,'error':f'{type(exc).__name__}: {exc}'})
                report['failure_reason']='quadrature_or_root_failure'
                return report
        final=np.asarray(report['ladder'][-1]['quantiles'])
        report['provisional_quantiles']=final.tolist()
        width=float(final[-1]-final[0]);report['reference_width']=width
        if not math.isfinite(width) or width<=0:
            report['failure_reason']='nonpositive_or_nonfinite_reference_width'
            return report
        comparisons=[]
        for previous,current in zip(report['ladder'],report['ladder'][1:]):
            delta=np.abs(np.asarray(current['quantiles'])-previous['quantiles'])
            comparisons.append({'from_order':previous['order'],'to_order':current['order'],
                'absolute_endpoint_changes':delta.tolist(),
                'changes_over_reference_width':(delta/width).tolist(),
                'pass':bool(np.all(delta<=relative_tolerance*width))})
        report['successive_comparisons']=comparisons
        report['numerical_reference_ready']=all(row['pass'] for row in comparisons[-2:])
        if report['numerical_reference_ready']:
            report['status']='quadrature_converged';report['quantiles']=final.tolist()
        else:report['failure_reason']='quadrature_ladder_not_converged_at_cap'
        return report
