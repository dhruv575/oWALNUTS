"""Read-only, bounded post-hoc scale-CDF diagnostic; see committed PLAN.md."""
import argparse
import hashlib
import json
import platform
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import arviz as az
import numpy as np
import scipy
from scipy.optimize import brentq
from scipy.special import ndtr, ndtri

HERE = Path(__file__).resolve().parent
TICKS = (2, 50, 100)
KS = (50, 100, 200)
SEEDS = (880101, 880102, 880103)
PS = (.5, .95)
TOL = np.array([.02, .05])
CAVEAT = ("Shared same-sampler finite-draw reference; independent sampler not validated. "
          "Deterministic CDF removes innovation simulation, not posterior Monte Carlo error. "
          "Reported reference MCSE is an asymptotic diagnostic, not a qualification guarantee.")


def identity(path):
    b = path.read_bytes()
    return dict(path=str(path.resolve()), bytes=len(b), sha256=hashlib.sha256(b).hexdigest())


def check_deadline(deadline):
    if time.perf_counter() >= deadline:
        raise TimeoutError("five-minute diagnostic ceiling")


def quantiles(m, sigma, deadline):
    """Invert full equal-weight mixture CDF in h=2 log(scale) coordinates."""
    m, sigma = np.asarray(m).ravel(), np.asarray(sigma).ravel()
    if m.size == 0 or m.shape != sigma.shape or not np.isfinite(m).all():
        raise ValueError("invalid mixture shape or location")
    if not np.isfinite(sigma).all() or np.any(sigma <= 0):
        raise ValueError("invalid mixture scale")
    lo, hi = float(np.min(m - 12*sigma)), float(np.max(m + 12*sigma))

    def cdf(h):
        check_deadline(deadline)
        return float(ndtr((h-m)/sigma).mean())

    grid = np.linspace(lo, hi, 17)
    vals = np.array([cdf(h) for h in grid])
    if not np.all(np.diff(vals) >= 0) or vals[0] >= .5 or vals[-1] <= .95:
        raise ValueError("mixture CDF failed monotonicity or bracket check")
    start = time.perf_counter()
    roots = [brentq(lambda h: cdf(h)-p, lo, hi, xtol=1e-12, rtol=1e-12) for p in PS]
    elapsed = time.perf_counter()-start
    residuals = [abs(cdf(h)-p) for h, p in zip(roots, PS)]
    if max(residuals) > 1e-10:
        raise ValueError("CDF inversion residual above 1e-10")
    q = np.exp(np.asarray(roots)/2)
    if not np.isfinite(q).all() or np.any(q <= 0):
        raise ValueError("nonfinite output quantile")
    return dict(p50=float(q[0]), p95=float(q[1]), logvol_roots=roots,
                residuals=residuals, logvol_bracket=[lo, hi], solver_seconds=elapsed)


def fixtures(deadline):
    checks = []
    for sigma in (.2, .4, 1.4):
        m = 2*np.log(.005)
        for components in (1, 7):
            r = quantiles(np.repeat(m, components), np.repeat(sigma, components), deadline)
            expected = np.exp((m + sigma*ndtri(PS))/2)
            error = float(np.max(np.abs(np.array([r['p50'], r['p95']])/expected-1)))
            if error > 1e-10:
                raise ValueError("analytic fixture failed")
            checks.append(dict(sigma=sigma, identical_components=components,
                               max_relative_error=error, max_residual=max(r['residuals'])))
    return checks


def records(cell, sources):
    path = cell/'ticks.jsonl'
    sources.setdefault(str(path.resolve()), identity(path))
    out = {}
    for line in path.read_text().splitlines():
        r = json.loads(line)
        t = r.get('tick', -1)
        if t < 0:
            continue
        if t in out:
            raise ValueError(f"duplicate tick {t}: {path}")
        out[t] = r
    return out


def load(cell, rec, tick, reference, sources):
    path = cell/rec['file'] if reference else cell/f'tick-{tick:03}.f32'
    sources.setdefault(str(path.resolve()), identity(path))
    raw = np.frombuffer(path.read_bytes(), dtype='<f4')
    if raw.size != rec['chains']*rec['draws']*3:
        raise ValueError(f"bad compact-draw shape: {path}")
    a = raw.reshape(rec['chains'], rec['draws'], 3).astype(float)
    idx = rec['kept'] if reference else list(range(rec['chains']))
    a = a[idx]
    if len(a) == 0 or not np.isfinite(a).all():
        raise ValueError(f"empty or nonfinite draws: {path}")
    return a, idx


def compute(a, idx, tick, proto, deadline, reference=False):
    m = a[..., 0] + proto['model']['rho']*(a[..., 2]-a[..., 0])
    sigma = np.exp(a[..., 1])
    deterministic_start = time.perf_counter()
    deterministic = quantiles(m, sigma, deadline)
    deterministic['processing_seconds'] = time.perf_counter()-deterministic_start
    noise_start = time.perf_counter()
    eps = np.random.default_rng(proto['quantities']['eps_seed_base']+tick).normal(size=(4,20000))[idx, :a.shape[1]]
    noisy = np.quantile(np.exp((m+sigma*eps)/2), PS)
    noise_seconds = time.perf_counter()-noise_start
    result = dict(deterministic=deterministic, original_noise=dict(p50=float(noisy[0]), p95=float(noisy[1]),
                  processing_seconds=noise_seconds), chains=len(a), draws_per_chain=a.shape[1],
                  original_noise_chain_rows=idx)
    if reference:
        mcse = []
        for p, h, q in zip(PS, deterministic['logvol_roots'], (deterministic['p50'], deterministic['p95'])):
            z = (h-m)/sigma
            g = ndtr(z)
            density = float(np.mean(2*np.exp(-z*z/2)/(np.sqrt(2*np.pi)*q*sigma)))
            cdf_mcse = float(az.mcse(g, method='mean'))
            value = cdf_mcse/density
            if not np.isfinite(value) or density <= 0:
                raise ValueError("invalid reference delta-method MCSE")
            mcse.append(dict(probability=p, cdf_mcse=cdf_mcse, scale_density=density,
                             quantile_mcse=value, relative_quantile_mcse=value/q))
        result['reference_uncertainty'] = dict(method='ArviZ mean MCSE of per-draw CDF, divided by mixture scale density',
                                                quantiles=mcse, caveat=CAVEAT)
        result['original_noise_vs_deterministic_relative'] = (noisy/np.array([deterministic['p50'], deterministic['p95']])-1).tolist()
    return result


def compare(result, reference):
    qref = np.array([reference['deterministic']['p50'], reference['deterministic']['p95']])
    for name in ('original_noise', 'deterministic'):
        q = np.array([result[name]['p50'], result[name]['p95']])
        errors = q/qref-1
        result[name]['relative_errors'] = errors.tolist()
        result[name]['within_2pct_5pct'] = bool(np.all(np.abs(errors) <= TOL))
    result['reference_uncertainty'] = reference['reference_uncertainty']
    result['reference_caveat'] = CAVEAT


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo-root', type=Path, default=HERE.parents[2])
    parser.add_argument('--out', type=Path, default=HERE)
    args = parser.parse_args()
    start = time.perf_counter()
    deadline = start+300
    source = args.repo_root.resolve()/'STUDIES'/'online_sv_quote_v2'
    sources = {}
    result = dict(kind='post-hoc estimator diagnostic only; no qualification verdict changed',
                  created_utc=datetime.now(timezone.utc).isoformat(), planned_reference_origins=6, planned_warm_rows=54,
                  plan=identity(HERE/'PLAN.md'), source=identity(Path(__file__)),
                  environment=dict(python=sys.version, numpy=np.__version__, scipy=scipy.__version__,
                                   arviz=az.__version__, platform=platform.platform(), machine=platform.machine()),
                  local_timing_caveat='Local postprocessing only, no sampling or production latency measurement',
                  numerical_fixtures=fixtures(deadline), origins=[], rows=[])
    # Fixtures are completed before the protocol or archived outcomes are loaded.
    proto = json.loads((source/'protocol.json').read_text())
    for p in (source/'protocol.json', source/'analyze.py'):
        sources[str(p.resolve())] = identity(p)
    for dataset in ('sim', 'real'):
        for tick in TICKS:
            origin_start = time.perf_counter()
            origin = dict(dataset=dataset, tick=tick, status='pending', reference_caveat=CAVEAT)
            reference = None
            try:
                check_deadline(deadline)
                cell = source/'artifacts'/'cells'/f'ref-{dataset}-N250'
                rec = records(cell, sources).get(tick)
                if rec is None or rec.get('status') != 'ok':
                    raise ValueError('reference record missing or not ok')
                a, idx = load(cell, rec, tick, True, sources)
                reference = compute(a, idx, tick, proto, deadline, reference=True)
                origin.update(status='ok', reference=reference,
                              original_reference_metadata={k:rec.get(k) for k in ('attempt','seed','kept','flagged','rhat_h_next')})
            except (OSError, ValueError, KeyError, TimeoutError, IndexError) as exc:
                origin.update(status='budget_exhausted' if isinstance(exc,TimeoutError) else 'invalid_or_missing', error=str(exc))
            for k in KS:
                for seed in SEEDS:
                    cell_id = f'warm{k}-{dataset}-N250-s{seed}'
                    row = dict(dataset=dataset, tick=tick, K=k, seed=seed, cell=cell_id,
                               status='pending', reference_caveat=CAVEAT)
                    try:
                        check_deadline(deadline)
                        if reference is None:
                            raise ValueError('reference unavailable')
                        cell = source/'artifacts'/'cells'/cell_id
                        rec = records(cell, sources).get(tick)
                        if rec is None or rec.get('status') != 'ok':
                            raise ValueError('warm record missing or not ok')
                        a, idx = load(cell, rec, tick, False, sources)
                        computed = compute(a, idx, tick, proto, deadline)
                        compare(computed, reference)
                        row.update(status='ok', **computed,
                                   original_warm_metadata={name:rec.get(name) for name in ('chains','draws','kept','divergences','wall_seconds')})
                    except (OSError, ValueError, KeyError, TimeoutError, IndexError) as exc:
                        row.update(status='budget_exhausted' if isinstance(exc,TimeoutError) else 'invalid_or_missing', error=str(exc))
                    result['rows'].append(row)
            origin['local_total_processing_seconds'] = time.perf_counter()-origin_start
            result['origins'].append(origin)
    groups = []
    for dataset in ('sim', 'real'):
        for k in KS:
            rows = [r for r in result['rows'] if r['dataset']==dataset and r['K']==k]
            good = [r for r in rows if r['status']=='ok']
            group = dict(dataset=dataset, K=k, planned=len(rows), processed=len(good))
            for estimator in ('original_noise','deterministic'):
                group[estimator] = dict(within_tolerance=sum(r[estimator]['within_2pct_5pct'] for r in good),
                    median_absolute_relative_error=[float(np.median([abs(r[estimator]['relative_errors'][i]) for r in good])) for i in (0,1)] if good else None,
                    median_local_processing_seconds=float(np.median([r[estimator]['processing_seconds'] for r in good])) if good else None)
            groups.append(group)
    result['groups'] = groups
    result['input_identities'] = list(sources.values())
    result['input_integrity_after'] = all(identity(Path(p))['sha256']==v['sha256'] for p,v in sources.items())
    if not result['input_integrity_after']:
        raise ValueError('an input changed during read-only analysis')
    result['total_local_processing_seconds'] = time.perf_counter()-start
    result['processed_warm_rows'] = sum(r['status']=='ok' for r in result['rows'])
    args.out.mkdir(parents=True,exist_ok=True)
    (args.out/'results.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps(dict(processed=result['processed_warm_rows'], planned=54,
                         seconds=result['total_local_processing_seconds'], groups=groups),indent=2))


if __name__ == '__main__':
    main()
