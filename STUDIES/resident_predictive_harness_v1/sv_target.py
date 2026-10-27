"""WP96 density, compiled once; immutable per-window arrays retained by owner."""
import math
import numba
import numpy as np
import owalnuts
RHO=.95
NU=5.0
def compile_target():
    """``q = [mu, log sigma, beta, z_1..z_n]``; the Rust ``Sv`` target."""
    cst = math.lgamma((NU + 1) / 2) - math.lgamma(NU / 2) - 0.5 * math.log(NU * math.pi)
    ln2pi = math.log(2 * math.pi)
    mu_mean, mu_sd, ls_mean, ls_sd, beta_sd = 2*math.log(.005), 1.0, math.log(.2), .5, .002

    @numba.cfunc(owalnuts.numba_raw_signature(), nopython=True, error_model="numpy")
    def logp_grad(dim, q_ptr, g_ptr, user):
        n = dim - 3
        y = numba.carray(user, (n,), dtype=numba.float64)
        q = numba.carray(q_ptr, (dim,))
        g = numba.carray(g_ptr, (dim,))
        mu, ls, beta = q[0], q[1], q[2]
        sigma = math.exp(ls)
        u = (mu - mu_mean) / mu_sd
        g[0] = -u / mu_sd
        lp = -0.5 * u * u - math.log(mu_sd) - 0.5 * ln2pi
        u = (ls - ls_mean) / ls_sd
        g[1] = -u / ls_sd
        lp += -0.5 * u * u - math.log(ls_sd) - 0.5 * ln2pi
        u = beta / beta_sd
        g[2] = -u / beta_sd
        lp += -0.5 * u * u - math.log(beta_sd) - 0.5 * ln2pi
        for i in range(n):
            z = q[3 + i]
            lp += -0.5 * z * z - 0.5 * ln2pi
            g[3 + i] = -z
        s0 = sigma / math.sqrt(1.0 - RHO * RHO)
        h = np.empty(n)
        h[0] = mu + s0 * q[3]
        for i in range(1, n):
            h[i] = mu + RHO * (h[i - 1] - mu) + sigma * q[3 + i]
        dh = np.zeros(n)
        for i in range(n):
            r = y[i] - beta
            e = math.exp(-h[i])
            a = r * r * e / NU
            lp += cst - 0.5 * h[i] - 0.5 * (NU + 1.0) * math.log1p(a)
            dh[i] = -0.5 + 0.5 * (NU + 1.0) * a / (1.0 + a)
            g[2] += (NU + 1.0) * r * e / NU / (1.0 + a)
        for i in range(n - 1, -1, -1):
            m = s0 if i == 0 else sigma
            g[3 + i] += dh[i] * m
            g[1] += dh[i] * m * q[3 + i]
            g[0] += dh[i] * (1.0 if i == 0 else 1.0 - RHO)
            if i > 0:
                dh[i - 1] += RHO * dh[i]
        if not math.isfinite(lp):
            return -math.inf
        for i in range(dim):
            if not math.isfinite(g[i]):
                return -math.inf
        return lp

    return logp_grad


class TargetOwner:
    def __init__(self, compiled, y):
        self.y = np.ascontiguousarray(y, dtype=np.float64).copy()
        if self.y.ndim != 1 or len(self.y)<2 or not np.isfinite(self.y).all():
            raise ValueError('invalid data window')
        self.compiled = compiled
        self.target = owalnuts.CFuncTarget(compiled.address, len(self.y)+3,
            user_data=self.y.ctypes.data, keep_alive=self)

def components(q):
    q=np.asarray(q); mu=q[...,0]; sigma=np.exp(q[...,1])
    h=mu+sigma/np.sqrt(1-RHO*RHO)*q[...,3]
    for j in range(4,q.shape[-1]):
        h=mu+RHO*(h-mu)+sigma*q[...,j]
    return np.stack([mu,q[...,1],q[...,2],h],axis=-1)

def compile_functional():
    @numba.cfunc(owalnuts.numba_functional_signature(),nopython=True,error_model='numpy')
    def compact(dim,q_ptr,out,n_out,user):
        q=numba.carray(q_ptr,(dim,)); mu=q[0]; sigma=np.exp(q[1])
        h=mu+sigma/np.sqrt(1-RHO*RHO)*q[3]
        for j in range(4,dim):
            h=mu+RHO*(h-mu)+sigma*q[j]
        out[0]=mu; out[1]=q[1]; out[2]=q[2]; out[3]=h
    return owalnuts.from_cfunc_functional(compact,4)

def remap(old):
    dim=old.positions.shape[1]
    shifted=old.remap(dim,lambda j:j if j<3 else (j+1 if j<dim-1 else None),fill=(0.,1.))
    positions=shifted.positions.copy(); mass=shifted.mass_diagonal.copy()
    positions[:,3]=RHO*old.positions[:,3]+np.sqrt(1-RHO*RHO)*old.positions[:,4]
    mass[:,3]=old.mass_diagonal[:,3]
    return owalnuts.WarmState(positions,old.step_sizes,mass)
