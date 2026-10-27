"""Known Gaussian-chain diagnostic, not a sampler qualification. See PLAN.md."""
import hashlib
import itertools
import json
import platform
import time
from pathlib import Path

import arviz as az
import numpy as np
import scipy
from scipy.integrate import quad
from scipy.optimize import brentq
from scipy.special import ndtr, ndtri, owens_t

HERE = Path(__file__).resolve().parent
PS = (.5, .95)
REPS = 200
CHAINS = 4
FUTURE_SD = .2
M0 = 2 * np.log(.005)
GRID = list(itertools.product((.5, 1., 2.), (0., .8, .98), (50, 200, 800)))


def covariance(p, correlation):
    z = ndtri(p)
    return p - 2 * owens_t(z, np.sqrt((1 - correlation) / (1 + correlation))) - p*p


def finite_variances(ratio, ar, k, p):
    c = ratio*ratio / (1 + ratio*ratio)
    gammas = covariance(p, c * ar**np.arange(k))
    off = 2 * np.dot(k-np.arange(1, k), gammas[1:])
    analytic = (k * gammas[0] + off) / (CHAINS*k*k)
    noisy = (k * p*(1-p) + off) / (CHAINS*k*k)
    return float(analytic), float(noisy)


def check_formulas():
    checks = []
    for ratio, p in itertools.product((.5, 1., 2.), PS):
        z = ndtri(p)
        threshold = np.sqrt(1 + ratio*ratio)*z
        g = lambda x: ndtr(threshold-ratio*x)
        density = lambda x: np.exp(-x*x/2)/np.sqrt(2*np.pi)
        mean = quad(lambda x: g(x)*density(x), -12, 12, epsabs=1e-12)[0]
        variance = quad(lambda x: (g(x)-p)**2*density(x), -12, 12, epsabs=1e-12)[0]
        expected = float(covariance(p, ratio*ratio/(1+ratio*ratio)))
        assert abs(mean-p) < 1e-10 and abs(variance-expected) < 1e-10
        for k in (50, 800):
            a, n = finite_variances(ratio, 0, k, p)
            assert abs(a-expected/(CHAINS*k)) < 1e-12
            assert abs(n-p*(1-p)/(CHAINS*k)) < 1e-12
        if p == .5:
            assert abs(expected-np.arcsin(ratio*ratio/(1+ratio*ratio))/(2*np.pi)) < 1e-12
        checks.append(dict(ratio=ratio, p=p, mean_error=mean-p, variance_error=variance-expected))
    return checks


def summarize(rows, exact_var, p):
    if not rows:
        return dict(completed=0, planned=REPS)
    results = [row[str(p)] for row in rows if str(p) in row]
    if not results:
        return dict(completed=0, planned=REPS)
    values = lambda key: np.array([r[key] for r in results])
    passed = int(values('wald_covers').sum())
    n = len(results)
    center = (passed/n + 1.96**2/(2*n))/(1+1.96**2/n)
    half = 1.96*np.sqrt((passed/n)*(1-passed/n)/n + 1.96**2/(4*n*n))/(1+1.96**2/n)
    return dict(completed=n, planned=REPS, wald_covered=passed,
                wald_coverage=passed/n, coverage_wilson95=[center-half, center+half],
                cdf_mean_variance_empirical_over_exact=float(np.var(values('cdf_at_true'), ddof=1)/exact_var),
                true_threshold_mcse_over_exact_median=float(np.median(values('cdf_mcse_at_true'))/np.sqrt(exact_var)),
                true_threshold_mcse_variance_over_exact_mean=float(np.mean(values('cdf_mcse_at_true')**2)/exact_var),
                analytic_relative_rmse=float(np.sqrt(np.mean(values('relative_error_analytic')**2))),
                noisy_relative_rmse=float(np.sqrt(np.mean(values('relative_error_noisy')**2))),
                analytic_relative_bias=float(values('relative_error_analytic').mean()),
                noisy_relative_bias=float(values('relative_error_noisy').mean()))


def main():
    output = HERE / 'results.json'
    if output.exists():
        raise SystemExit('Preserving existing results.json; use a separate study copy for a new run.')
    start = time.perf_counter()
    deadline = start+180
    checks = check_formulas()
    children = np.random.SeedSequence(99271001).spawn(len(GRID))
    cells = []
    timed_out = False
    for index, ((ratio, ar, k), seed) in enumerate(zip(GRID, children)):
        cell = dict(index=index, ratio=ratio, ar=ar, k=k, spawn_key=list(seed.spawn_key),
                    planned=REPS, rows=[], errors=[])
        cells.append(cell)
        if timed_out:
            cell['status'] = 'not_run_budget'
            continue
        rng = np.random.default_rng(seed)
        tau = FUTURE_SD * ratio
        total_sd = np.hypot(tau, FUTURE_SD)
        state = rng.normal(size=(REPS, CHAINS))
        draws = np.empty((REPS, CHAINS, k))
        draws[:, :, 0] = M0 + tau*state
        for t in range(1, k):
            state = ar*state + np.sqrt(1-ar*ar)*rng.normal(size=state.shape)
            draws[:, :, t] = M0 + tau*state
        for rep, m in enumerate(draws):
            if time.perf_counter() >= deadline:
                timed_out = True
                break
            row = dict(replicate=rep)
            cell['rows'].append(row)
            noisy = np.quantile(np.exp((m + FUTURE_SD*rng.normal(size=m.shape))/2), PS)
            lo, hi = float(m.min()-12*FUTURE_SD), float(m.max()+12*FUTURE_SD)
            for j, p in enumerate(PS):
                try:
                    true_h = M0 + total_sd*ndtri(p)
                    true_q = np.exp(true_h/2)
                    g_true = ndtr((true_h-m)/FUTURE_SD)
                    h = brentq(lambda x: ndtr((x-m)/FUTURE_SD).mean()-p, lo, hi, xtol=1e-12)
                    q = np.exp(h/2)
                    z = (h-m)/FUTURE_SD
                    g_plugin = ndtr(z)
                    density = np.mean(2*np.exp(-z*z/2)/(np.sqrt(2*np.pi)*q*FUTURE_SD))
                    mcse_true = float(az.mcse(g_true, method='mean'))
                    mcse_plugin = float(az.mcse(g_plugin, method='mean'))
                    se_q = mcse_plugin/density
                    if not np.isfinite([mcse_true, mcse_plugin, se_q]).all() or density <= 0:
                        raise ValueError('invalid MCSE or density')
                    row[str(p)] = dict(cdf_at_true=float(g_true.mean()), cdf_mcse_at_true=mcse_true,
                        cdf_mcse_plugin=mcse_plugin, quantile_mcse=float(se_q), true_quantile=float(true_q),
                        analytic_quantile=float(q), noisy_quantile=float(noisy[j]),
                        relative_error_analytic=float(q/true_q-1), relative_error_noisy=float(noisy[j]/true_q-1),
                        wald_covers=bool(q-1.96*se_q <= true_q <= q+1.96*se_q))
                except Exception as exc:
                    cell['errors'].append(dict(replicate=rep, p=p, error=str(exc)))
        cell['status'] = 'timeout' if timed_out else ('errors' if cell['errors'] else 'completed')
        cell['summary'] = {}
        for p in PS:
            av, nv = finite_variances(ratio, ar, k, p)
            cell['summary'][str(p)] = dict(exact_cdf_mean_variance=av,
                exact_noisy_indicator_mean_variance=nv, **summarize(cell['rows'], av, p))
        print(f'{index+1}/27 ratio={ratio} ar={ar} K={k}: {cell["status"]}, {len(cell["rows"])} replicates', flush=True)
    result = dict(status='budget_exhausted' if timed_out else 'completed', seed_entropy=99271001,
        planned_settings=len(GRID), planned_replicates_per_setting=REPS, chains=CHAINS,
        future_sd=FUTURE_SD, m0=float(M0), elapsed_seconds=time.perf_counter()-start,
        formulas=checks, cells=cells,
        environment=dict(python=platform.python_version(), platform=platform.platform(),
                         numpy=np.__version__, scipy=scipy.__version__, arviz=az.__version__),
        source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        plan_sha256=hashlib.sha256((HERE/'PLAN.md').read_bytes()).hexdigest(),
        caveat='Exactly stationary Gaussian-chain method diagnostic; no SV accuracy, adaptive stopping, or market qualification.')
    output.write_text(json.dumps(result, indent=1, allow_nan=False)+'\n', encoding='utf-8', newline='\n')
    print(json.dumps(dict(status=result['status'], elapsed_seconds=result['elapsed_seconds'])))


if __name__ == '__main__':
    main()
