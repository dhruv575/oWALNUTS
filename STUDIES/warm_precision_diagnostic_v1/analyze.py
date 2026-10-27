"""Fixed analysis from PLAN.md; read-only sampler/reference inputs, bounded arithmetic run."""
import argparse
import hashlib
import json
import math
import platform
import time
from datetime import datetime, timezone
from pathlib import Path

import arviz as az
import numpy as np
import scipy
from scipy.optimize import brentq
from scipy.special import ndtr, ndtri

HERE = Path(__file__).resolve().parent
PROTO = json.loads((HERE / "protocol.json").read_text())
PS = (.5, .95)
TOLS = np.array([PROTO["tolerance_p50"], PROTO["tolerance_p95"]])
ESTIMATORS = ("noise_vs_noise", "noise_vs_cdf", "cdf_vs_cdf")


def identity(path):
    return dict(path=str(path), bytes=path.stat().st_size, sha256=hashlib.sha256(path.read_bytes()).hexdigest())


def records(path):
    if not path.exists():
        return {}, ["missing ticks.jsonl"]
    result, errors = {}, []
    for number, line in enumerate(path.read_text().splitlines(), 1):
        try:
            rec = json.loads(line)
            tick = rec["tick"]
            if tick in result:
                errors.append(f"duplicate tick {tick}")
                continue
            result[tick] = rec
        except (ValueError, KeyError) as exc:
            errors.append(f"line {number}: {exc}")
    return result, errors


def load(path, rec, reference):
    raw = np.fromfile(path, dtype="<f4")
    if raw.size != rec["chains"] * rec["draws"] * 3:
        raise ValueError("compact draw size mismatch")
    a = raw.reshape(rec["chains"], rec["draws"], 3).astype(float)
    idx = rec.get("kept", list(range(rec["chains"])))
    if len(idx) != len(set(idx)) or any(c < 0 or c > 3 for c in idx):
        raise ValueError("invalid original chain identities")
    if reference:
        a = a[idx]
    if len(a) != len(idx) or not np.isfinite(a).all():
        raise ValueError("invalid draws/chain count")
    return a, idx


def analytic(a):
    """Arithmetic-only timer includes transformation, bracketing and both root solves."""
    start = time.perf_counter()
    m = a[..., 0] + PROTO["rho"] * (a[..., 2] - a[..., 0])
    sd = np.exp(a[..., 1])
    if not np.isfinite(sd).all() or (sd <= 0).any():
        raise ValueError("invalid conditional scale")
    lo, hi = float(np.min(m-12*sd)), float(np.max(m+12*sd))
    roots, residuals = [], []
    for p in PS:
        f = lambda h: float(ndtr((h-m)/sd).mean()) - p
        if not f(lo) < 0 < f(hi):
            raise ValueError("invalid CDF bracket")
        h = brentq(f, lo, hi, xtol=1e-12, rtol=1e-12, maxiter=100)
        residual = abs(f(h))
        if residual > 1e-9:
            raise ValueError("CDF inversion residual too large")
        roots.append(float(h))
        residuals.append(float(residual))
    q = np.exp(np.array(roots)/2)
    if not np.isfinite(q).all() or (q <= 0).any():
        raise ValueError("invalid analytic quantile")
    return dict(quantiles=q.tolist(), roots=roots, residuals=residuals, bracket=[lo, hi],
                arithmetic_seconds=time.perf_counter()-start)


def compute(a, idx, tick):
    start = time.perf_counter()
    m = a[..., 0] + PROTO["rho"] * (a[..., 2] - a[..., 0])
    sd = np.exp(a[..., 1])
    eps = np.random.default_rng(PROTO["eps_seed_base"]+tick).normal(size=(4, 20000))[idx, :a.shape[1]]
    hn = m + sd*eps
    scale = np.exp(hn/2)
    noisy = np.quantile(scale, PS)
    noise_time = time.perf_counter()-start
    cdf = analytic(a)
    start_diag = time.perf_counter()
    cdf_mcse, noisy_mcse = [], []
    for p, h, q, nq in zip(PS, cdf["roots"], cdf["quantiles"], noisy):
        z = (h-m)/sd
        f_scale = float(np.mean(2*np.exp(-z*z/2)/(np.sqrt(2*np.pi)*q*sd)))
        if f_scale <= 0 or not np.isfinite(f_scale):
            raise ValueError("invalid mixture density")
        cdf_mcse.append(float(az.mcse(ndtr(z), method="mean"))/(q*f_scale))
        noisy_mcse.append(float(az.mcse(scale, method="quantile", prob=p))/float(nq))
    if not np.isfinite(cdf_mcse+noisy_mcse).all():
        raise ValueError("nonfinite MCSE")
    return dict(noise=dict(quantiles=noisy.tolist(), arithmetic_seconds=noise_time, relative_mcse=noisy_mcse),
                cdf=dict(**cdf, relative_mcse=cdf_mcse), diagnostic_seconds=time.perf_counter()-start_diag,
                chain_medians_log_sigma=np.median(a[..., 1], axis=1).tolist(),
                chain_medians_h_last=np.median(a[..., 2], axis=1).tolist(),
                pooled_median_log_sigma=float(np.median(a[..., 1])), pooled_median_h_last=float(np.median(a[..., 2])))


def fixtures():
    a = np.zeros((4, 100, 3))
    a[..., 0] = a[..., 2] = -10.0
    a[..., 1] = np.log(.3)
    expected = np.exp((-10+.3*ndtri(PS))/2)
    actual = np.array(analytic(a)["quantiles"])
    error = float(np.max(abs(actual/expected-1)))
    if error > 1e-10:
        raise ValueError("analytic Gaussian fixture failed")
    return dict(single_gaussian_max_relative_error=error)


def qfinite(values, p):
    """Linear quantile with missing/error entries represented by +infinity (JSON null)."""
    if not values:
        return None
    a = sorted(values)
    x = (len(a)-1)*p
    lo, hi = math.floor(x), math.ceil(x)
    if not math.isfinite(a[lo]) or not math.isfinite(a[hi]):
        return None
    return float(a[lo] + (x-lo)*(a[hi]-a[lo]))


def latency(recs):
    walls = [recs[t]["wall_seconds"] if recs.get(t, {}).get("status") == "ok" else math.inf
             for t in range(1, PROTO["ticks"]+1)]
    return dict(planned=PROTO["ticks"], available=sum(math.isfinite(v) for v in walls),
                median_seconds=qfinite(walls, .5), p95_seconds=qfinite(walls, .95),
                p99_seconds=qfinite(walls, .99), maximum_seconds=qfinite(walls, 1),
                fraction_under_04=sum(v < .4 for v in walls)/len(walls),
                missing_are_infinite=True, nonfinite_quantiles_encoded_as_null=True,
                tick0=recs.get(0))


def summarize(rows):
    result = []
    for cell in PROTO["cells"]:
        for half in (1, 2):
            all_rows = [r for r in rows if r["cell"] == cell["id"] and r["half"] == half]
            good = [r for r in all_rows if r["status"] == "ok"]
            group = dict(cell=cell["id"], stream=cell["stream"], K=cell["K"], half=half,
                         planned=len(all_rows), available=len(good), unavailable=len(all_rows)-len(good),
                         stuck_ticks=sum(bool(r["stuck"]) for r in good),
                         divergent_ticks=sum(r["divergences"] > 0 for r in good), estimators={})
            group["combined_mcse_diagnostic_seconds_median"] = qfinite([r["computed"]["diagnostic_seconds"] for r in good], .5)
            for est in ESTIMATORS:
                passed = sum(r["comparisons"][est]["within_bands_no_stuck"] for r in good)
                e = np.array([r["comparisons"][est]["errors"] for r in good])
                method = "cdf" if est == "cdf_vs_cdf" else "noise"
                mcse = np.array([r["computed"][method]["relative_mcse"] for r in good])
                group["estimators"][est] = dict(within_bands_no_stuck=passed, descriptive_share=passed/len(all_rows),
                    signed_error_mean=e.mean(axis=0).tolist() if good else None,
                    signed_error_q05_q50_q95=np.quantile(e, [.05, .5, .95], axis=0).tolist() if good else None,
                    absolute_error_median=np.median(abs(e), axis=0).tolist() if good else None,
                    absolute_error_p95=np.quantile(abs(e), .95, axis=0).tolist() if good else None,
                    own_relative_mcse_median=np.median(mcse, axis=0).tolist() if good else None,
                    arithmetic_seconds_median=qfinite([r["computed"][method]["arithmetic_seconds"] for r in good], .5),
                    sampler_plus_separate_arithmetic_median=qfinite([r["sampler_seconds"]+r["computed"][method]["arithmetic_seconds"] for r in good], .5),
                    sampler_plus_arithmetic_plus_both_mcse_diagnostics_median=qfinite([r["sampler_seconds"]+r["computed"][method]["arithmetic_seconds"]+r["computed"]["diagnostic_seconds"] for r in good], .5))
            result.append(group)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifacts", type=Path, default=HERE/"artifacts")
    parser.add_argument("--references", type=Path, default=Path(PROTO["reference_artifacts"]))
    parser.add_argument("--out", type=Path, default=HERE/"analysis")
    args = parser.parse_args()
    if args.out.exists():
        raise SystemExit("Refusing existing analysis output")
    if not (args.artifacts/"DONE.json").exists():
        raise SystemExit("Sampling lanes must be drained before timed analysis")
    args.out.mkdir(parents=True)
    started = time.perf_counter()
    deadline = started + PROTO["analysis_seconds_cap"]
    result = dict(kind="fixed-budget single-seed diagnostic; no qualification", utc=datetime.now(timezone.utc).isoformat(),
                  source=identity(Path(__file__)), protocol=identity(HERE/"protocol.json"), plan=identity(HERE/"PLAN.md"),
                  environment=dict(python=platform.python_version(), platform=platform.platform(), numpy=np.__version__,
                                   scipy=scipy.__version__, arviz=az.__version__), fixtures=fixtures(), rows=[], references=[], cells=[], inputs=[])
    all_logs, all_log_errors = {}, {}
    for cell in PROTO["cells"]:
        log = args.artifacts/"cells"/cell["id"]/"ticks.jsonl"
        recs, errors = records(log)
        all_logs[cell["id"]] = recs
        all_log_errors[cell["id"]] = errors
        if log.exists():
            result["inputs"].append(identity(log))
        status = args.artifacts/"status"/(cell["id"]+".json")
        result["cells"].append(dict(cell=cell, record_errors=errors, latency=latency(recs),
                                    process_status=json.loads(status.read_text()) if status.exists() else None))
    for stream in ("shift", "control"):
        ref_cell = args.references/"cells"/("ref-"+stream)
        ref_recs, ref_errors = records(ref_cell/"ticks.jsonl")
        if (ref_cell/"ticks.jsonl").exists():
            result["inputs"].append(identity(ref_cell/"ticks.jsonl"))
        for tick in range(25, 2001, 25):
            reference = None
            ref = dict(stream=stream, tick=tick, status="pending", record_errors=ref_errors)
            try:
                if time.perf_counter() >= deadline:
                    raise TimeoutError("analysis budget exhausted")
                rec = ref_recs[tick]
                if ref_errors or rec["status"] != "ok":
                    raise ValueError("reference record invalid or original gate failed")
                path = ref_cell/rec["file"]
                a, idx = load(path, rec, True)
                reference = compute(a, idx, tick)
                result["inputs"].append(identity(path))
                ref.update(status="ok", computed=reference, original_selection={k: rec.get(k) for k in ("kept", "flagged", "seed", "attempt", "rhat_h_next")})
            except (ValueError, KeyError, OSError, TimeoutError) as exc:
                ref.update(status="unavailable", error=str(exc))
            result["references"].append(ref)
            for cell in (c for c in PROTO["cells"] if c["stream"] == stream):
                row = dict(cell=cell["id"], stream=stream, K=cell["K"], tick=tick, half=1 if tick <= 1000 else 2, status="pending")
                try:
                    if time.perf_counter() >= deadline:
                        raise TimeoutError("analysis budget exhausted")
                    if reference is None:
                        raise ValueError("reference unavailable")
                    if all_log_errors[cell["id"]]:
                        raise ValueError("warm log has invalid or duplicate records")
                    rec = all_logs[cell["id"]][tick]
                    if rec.get("status") != "ok":
                        raise ValueError("warm tick failed")
                    path = args.artifacts/"cells"/cell["id"]/f"tick-{tick:04}.f32"
                    a, idx = load(path, rec, False)
                    computed = compute(a, idx, tick)
                    result["inputs"].append(identity(path))
                    stuck = [idx[c] for c in range(len(a)) if abs(computed["chain_medians_log_sigma"][c]-reference["pooled_median_log_sigma"]) > 1
                             or abs(computed["chain_medians_h_last"][c]-reference["pooled_median_h_last"]) > 2]
                    comparisons = {}
                    for est, num, den in (("noise_vs_noise", "noise", "noise"), ("noise_vs_cdf", "noise", "cdf"), ("cdf_vs_cdf", "cdf", "cdf")):
                        errors = np.array(computed[num]["quantiles"])/reference[den]["quantiles"]-1
                        comparisons[est] = dict(errors=errors.tolist(), within_bands_no_stuck=bool(np.all(abs(errors) <= TOLS) and not stuck))
                    row.update(status="ok", computed=computed, comparisons=comparisons, stuck=stuck,
                               divergences=sum(rec.get("divergences", [])), sampler_seconds=rec["wall_seconds"], original_chain_ids=idx)
                except (ValueError, KeyError, OSError, TimeoutError) as exc:
                    row.update(status="unavailable", error=str(exc))
                result["rows"].append(row)
    result["elapsed_seconds"] = time.perf_counter()-started
    result["groups"] = summarize(result["rows"])
    result["status"] = "complete" if all(r["status"] == "ok" for r in result["rows"]) else "partial"
    (args.out/"results.json").write_text(json.dumps(result, indent=1, allow_nan=False)+"\n")
    (args.out/"summary.json").write_text(json.dumps({k: result[k] for k in ("status", "utc", "elapsed_seconds", "environment", "groups", "cells")}, indent=2, allow_nan=False)+"\n")
    print(json.dumps(dict(status=result["status"], warm_rows=len(result["rows"]), available=sum(r["status"] == "ok" for r in result["rows"]), seconds=result["elapsed_seconds"])))


if __name__ == "__main__":
    main()
