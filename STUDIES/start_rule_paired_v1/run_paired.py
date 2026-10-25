#!/usr/bin/env python3
"""WP60 start_rule_paired_v1 driver: Init::uniform() vs Init::best_of(16), paired by seed, at f097391c.

    python run_paired.py run       # every model / seed / arm in protocol order (resumable; no reruns)
    python run_paired.py analyze   # artifacts/summary.json + results-table.md

Each cell writes artifacts/cells/<model>-<arm>-<seed>.json (metrics, no draws);
constrained draws go to artifacts/draws/ (uncommitted). Failures are cells with status != "ok".
"""
from __future__ import annotations

import functools
import hashlib
import json
import math
import os
import platform
import statistics
import subprocess
import sys
import time
import traceback
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
PROTOCOL = json.loads((HERE / "protocol.json").read_text(encoding="utf-8"))
ART = Path(os.environ["WP60_SMOKE_ART"]) if os.environ.get("WP60_SMOKE_ART") else HERE / "artifacts"
SEEDS = [int(x) for x in os.environ["WP60_SMOKE_SEEDS"].split(",")] if os.environ.get("WP60_SMOKE_SEEDS") else PROTOCOL["seeds"]
CELLS = ART / "cells"
DRAWS = ART / "draws"
MODELS = HERE / "models"
PDB_PATH = (HERE / PROTOCOL["posteriordb"]["path"]).resolve()
HARNESS = HERE / "target" / "release" / "start-rule-paired-v1.exe"
ARMS = PROTOCOL["arms_order"]
MODEL_LIST = PROTOCOL["models"]
TIMEOUT = PROTOCOL["cell_timeout_seconds"]


def short(model: str) -> str:
    return model.replace("-", "__")


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def check_commit() -> str:
    if os.environ.get("WP60_SMOKE_ART"):
        return "smoke-test-not-evidence"
    commit = PROTOCOL["source_commit_under_test"]
    diff = subprocess.run(["git", "-C", str(REPO), "diff", "--quiet", commit, "HEAD", "--",
                           "src", "integrations", "Cargo.toml", "tests"], capture_output=True)
    dirty = subprocess.run(["git", "-C", str(REPO), "diff", "--quiet", "HEAD", "--", "src", "integrations", "Cargo.toml"],
                           capture_output=True)
    if diff.returncode != 0 or dirty.returncode != 0:
        raise SystemExit(f"library source differs from the commit under test {commit}")
    tracked = subprocess.run(["git", "-C", str(REPO), "ls-files", "--error-unmatch", str(HERE / "PREREGISTRATION.md")],
                             capture_output=True)
    if tracked.returncode != 0:
        raise SystemExit("PREREGISTRATION.md must be committed before the first cell")
    return commit


def bridgestan_name(name: str) -> str:
    parts = name.split(".")
    if len(parts) == 1 or not all(p.isdigit() for p in parts[1:]):
        return name
    return f"{parts[0]}[{','.join(parts[1:])}]"


def arviz_stats(arr: np.ndarray) -> dict:
    import arviz as az

    ds = az.convert_to_dataset({"p": arr})
    with np.errstate(all="ignore"):
        bulk = np.asarray(az.ess(ds, method="bulk").p.values, dtype=float)
        tail = np.asarray(az.ess(ds, method="tail", prob=(0.05, 0.95)).p.values, dtype=float)
        rhat = np.asarray(az.rhat(ds, method="rank").p.values, dtype=float)
        mcse = np.asarray(az.mcse(ds, method="mean").p.values, dtype=float)
    flat = arr.reshape(-1, arr.shape[-1])
    return {"mean": flat.mean(0), "sd": flat.std(0, ddof=1), "bulk_ess": bulk, "tail_ess": tail, "rhat": rhat, "mcse": mcse}


def reference(model: str) -> dict:
    from posteriordb import PosteriorDatabase

    ref = PosteriorDatabase(str(PDB_PATH)).posterior(model).reference_draws()
    names = list(ref[0].keys())
    arr = np.transpose(np.asarray([[c[n] for n in names] for c in ref], dtype=np.float64), (0, 2, 1))
    return {"names": names, **arviz_stats(arr)}


@functools.lru_cache(maxsize=None)
def bridgestan_model(model: str):
    import bridgestan as bs

    bs.compile.windows_dll_path_setup()
    return bs.StanModel(str(MODELS / f"{short(model)}_model.so"),
                        data=(MODELS / f"{short(model)}.data.json").read_text(encoding="utf-8"), seed=1)


def failure(model: str, arm: str, seed: int, status: str, message: str) -> dict:
    return {"schema": "start-rule-paired-v1-cell-metrics", "model": model, "arm": arm, "seed": seed,
            "status": status, "error": message, "passed": False, "gates": {"no_sampler_error": False}}


def run_cell(model: str, arm: str, seed: int, ref: dict) -> dict:
    so, data = MODELS / f"{short(model)}_model.so", MODELS / f"{short(model)}.data.json"
    DRAWS.mkdir(parents=True, exist_ok=True)
    raw = DRAWS / f"{short(model)}-{arm}-{seed}.raw.json"
    if raw.exists():
        raw.unlink()
    try:
        cp = subprocess.run([str(HARNESS), str(so), str(data), arm, str(seed), str(raw), str(PROTOCOL["threads"])],
                            capture_output=True, text=True, timeout=TIMEOUT)
    except subprocess.TimeoutExpired:
        return failure(model, arm, seed, "timeout", f"exceeded {TIMEOUT}s")
    if cp.returncode != 0 or not raw.exists():
        return failure(model, arm, seed, "error", cp.stderr.strip()[-2000:] or f"exit {cp.returncode}")
    out = json.loads(raw.read_text(encoding="utf-8"))
    if out.get("status") != "ok":
        return failure(model, arm, seed, "error", out.get("error", "unknown"))
    sm = bridgestan_model(model)
    cnames = [bridgestan_name(n) for n in sm.param_names(include_tp=True, include_gq=False)]
    unc = np.asarray([c["samples"] for c in out["chains_data"]], dtype=np.float64)
    con = np.empty(unc.shape[:2] + (len(cnames),))
    for c in range(unc.shape[0]):
        for d in range(unc.shape[1]):
            con[c, d] = sm.param_constrain(unc[c, d], include_tp=True, include_gq=False)
    index = {n: i for i, n in enumerate(cnames)}
    names = ref["names"]
    draws = con[:, :, [index[n] for n in names]]
    st = arviz_stats(draws)
    chains = out["chains_data"]
    grads_total = out["target_calls_total"]
    div = sum(c["divergences"] for c in chains)
    min_bulk, min_tail, max_rhat = float(np.nanmin(st["bulk_ess"])), float(np.nanmin(st["tail_ess"])), float(np.nanmax(st["rhat"]))
    z = (st["mean"] - ref["mean"]) / np.sqrt(st["mcse"] ** 2 + ref["mcse"] ** 2)
    g = PROTOCOL["gates"]
    gates = {"max_rank_rhat": max_rhat <= g["max_rank_rhat"], "min_bulk_ess": min_bulk >= g["min_bulk_ess"],
             "min_tail_ess": min_tail >= g["min_tail_ess"], "sampling_divergences": div == 0,
             "finite_draws": bool(np.isfinite(draws).all()), "no_sampler_error": True}
    steps = [c["final_step_size"] for c in chains]
    med_step = statistics.median(steps)
    per_chain_ess = [float(np.nanmin(arviz_stats(draws[i:i + 1])["bulk_ess"])) for i in range(draws.shape[0])]
    cell = {
        "schema": "start-rule-paired-v1-cell-metrics", "model": model, "arm": arm, "seed": seed, "status": "ok",
        "wall_seconds": out["wall_seconds"], "gradients_total": grads_total,
        "gradients_warmup": sum(c["warmup_target_calls"] for c in chains),
        "gradients_sampling": sum(c["retained_target_calls"] for c in chains),
        "start_search_calls": out["init"]["start_search_calls"],
        "min_bulk_ess": min_bulk, "min_tail_ess": min_tail, "max_rank_rhat": max_rhat, "divergences": div,
        "argmin_bulk_ess": names[int(np.nanargmin(st["bulk_ess"]))],
        "min_bulk_ess_per_gradient": min_bulk / grads_total,
        "max_abs_z": float(np.nanmax(np.abs(z))), "argmax_abs_z": names[int(np.nanargmax(np.abs(z)))],
        "gates": gates, "passed": all(gates.values()),
        "start_log_densities": out["start_log_densities"],
        "end_of_warmup_step": steps,
        "end_of_warmup_step_min_over_median": min(steps) / med_step if med_step else None,
        "warmup_step_trace_every_50": [c["warmup_step_trace_every_50"] for c in chains],
        "warmup_gradients_per_chain": [c["warmup_target_calls"] for c in chains],
        "retained_gradients_per_chain": [c["retained_target_calls"] for c in chains],
        "per_chain_bulk_ess_min": per_chain_ess,
        "max_depth_stops": sum(c["maximum_depth_stops"] for c in chains),
        "refinement_exhaustions": sum(c["refinement_exhaustions"] for c in chains),
        "nonfinite_position_rejections": sum(c["retained_work"]["nonfinite_position_rejections"] + c["warmup_work"]["nonfinite_position_rejections"] for c in chains),
        "chain_warnings": out.get("chain_warnings", []),
        "init": out["init"]["detail"], "defaults": out["defaults"], "execution": out.get("execution"),
        "algorithm_revision": out["algorithm_revision"],
    }
    np.savez_compressed(DRAWS / f"{short(model)}-{arm}-{seed}.npz", draws=draws, names=np.asarray(names), unconstrained=unc)
    raw.unlink()
    return cell


def cell_path(model: str, arm: str, seed: int) -> Path:
    return CELLS / f"{short(model)}-{arm}-{seed}.json"


def run_all() -> None:
    log(f"commit under test: {check_commit()}")
    CELLS.mkdir(parents=True, exist_ok=True)
    machine = ART / "measured_on.json"
    if not machine.exists():
        machine.write_text(json.dumps({"platform": platform.platform(), "processor": platform.processor(),
                                       "cpu_count": os.cpu_count(), "python": sys.version.split()[0],
                                       "started_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                                       "note": "shared machine; walls contended"}, indent=2) + "\n", encoding="utf-8")
    for model in MODEL_LIST:
        log(f"== {model}")
        ref = reference(model)
        for seed in SEEDS:
            for arm in ARMS:
                if cell_path(model, arm, seed).exists():
                    continue
                try:
                    cell = run_cell(model, arm, seed, ref)
                except Exception as e:  # noqa: BLE001
                    cell = failure(model, arm, seed, "error", f"{e}\n{traceback.format_exc()[-1500:]}")
                cell_path(model, arm, seed).write_text(json.dumps(cell, indent=1, sort_keys=True) + "\n", encoding="utf-8")
                if cell["status"] == "ok":
                    log(f"  {arm} {seed}: grads {cell['gradients_total']} minbulk {cell['min_bulk_ess']:.0f} mintail {cell['min_tail_ess']:.0f} "
                        f"rhat {cell['max_rank_rhat']:.4f} div {cell['divergences']} max|z| {cell['max_abs_z']:.2f} "
                        f"ess/grad {cell['min_bulk_ess_per_gradient']:.3e} steps {[round(x, 4) for x in cell['end_of_warmup_step']]} passed {cell['passed']}")
                else:
                    log(f"  {arm} {seed}: {cell['status']}: {cell['error'][:200]}")


def geomean(xs: list[float]) -> float:
    xs = [x for x in xs if x is not None and math.isfinite(x) and x > 0]
    return float(math.exp(sum(math.log(x) for x in xs) / len(xs))) if xs else float("nan")


def analyze() -> None:
    cells: dict = {}
    for p in sorted(CELLS.glob("*.json")):
        c = json.loads(p.read_text(encoding="utf-8"))
        cells.setdefault(c["model"], {}).setdefault(c["arm"], {})[str(c["seed"])] = c
    per_model = {}
    for m in MODEL_LIST:
        u, b = cells.get(m, {}).get("uniform", {}), cells.get(m, {}).get("best_of_16", {})
        paired = [s for s in map(str, SEEDS) if u.get(s, {}).get("status") == "ok" and b.get(s, {}).get("status") == "ok"]
        ratios = {s: b[s]["min_bulk_ess_per_gradient"] / u[s]["min_bulk_ess_per_gradient"] for s in paired}
        row = {"paired_seeds": paired, "per_seed_ratio": ratios, "ratio_geomean": geomean(list(ratios.values())),
               "ratio_median": statistics.median(ratios.values()) if ratios else None,
               "seeds_below_1": sum(1 for r in ratios.values() if r < 1)}
        for arm, cs in (("uniform", u), ("best_of_16", b)):
            ok = [c for c in cs.values() if c["status"] == "ok"]
            row[arm] = {"n": len(cs), "n_ok": len(ok), "passed": sum(1 for c in ok if c["passed"]),
                        "ess_per_gradient_geomean": geomean([c["min_bulk_ess_per_gradient"] for c in ok]),
                        "gradients_median": statistics.median(c["gradients_total"] for c in ok) if ok else None,
                        "warmup_gradients_median": statistics.median(c["gradients_warmup"] for c in ok) if ok else None,
                        "min_bulk_ess_median": statistics.median(c["min_bulk_ess"] for c in ok) if ok else None,
                        "start_log_density_median": statistics.median(x for c in ok for x in c["start_log_densities"] if x is not None) if ok else None,
                        "step_min_over_median": [round(c["end_of_warmup_step_min_over_median"], 3) for c in ok],
                        "collapsed_step_chains": sum(1 for c in ok for x in c["end_of_warmup_step"] if x < 0.2 * statistics.median(c["end_of_warmup_step"])),
                        "max_abs_z_max": max((c["max_abs_z"] for c in ok), default=None),
                        "errors": {s: c.get("error", "")[:200] for s, c in cs.items() if c["status"] != "ok"}}
        per_model[m] = row
    model_ratios = [per_model[m]["ratio_geomean"] for m in MODEL_LIST]
    complete = all(len(per_model[m]["paired_seeds"]) == len(SEEDS) for m in MODEL_LIST)
    g = geomean(model_ratios)
    below = sum(1 for r in model_ratios if r is not None and math.isfinite(r) and r < 1.0)
    dr = PROTOCOL["decision_rule"]
    if g < dr["revert_below"] and below >= dr["revert_min_models_below_1"]:
        decision = "REVERT_RECOMMENDED: recommend Init::uniform() as the default (best_of opt-in)"
    elif g >= dr["keep_at_or_above"]:
        decision = "KEEP: recommend keeping Init::best_of(16) as the default"
    else:
        decision = "INCONCLUSIVE: keep Init::best_of(16) and document the number"
    if g < 0.9:
        hyp = "H1 supported (the start rule causes a per-gradient drop)"
    elif g >= 0.95:
        hyp = "H0 supported (the start rule is not the cause; seeds / rescue removal are)"
    else:
        hyp = "neither hypothesis supported (0.9 <= g < 0.95)"
    pooled = geomean([r for m in MODEL_LIST for r in per_model[m]["per_seed_ratio"].values()])
    summary = {"schema": "start-rule-paired-v1-summary", "commit": PROTOCOL["source_commit_under_test"],
               "complete": complete, "paired_geomean_over_models": g, "models_below_1": below,
               "pooled_geomean_over_all_pairs": pooled, "decision": decision, "hypothesis": hyp,
               "passes": {a: sum(per_model[m][a]["passed"] for m in MODEL_LIST) for a in ARMS},
               "per_model": per_model,
               "protocol_sha256": hashlib.sha256((HERE / "protocol.json").read_bytes()).hexdigest(),
               "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    (ART / "summary.json").write_text(json.dumps(summary, indent=1, sort_keys=True) + "\n", encoding="utf-8")

    def f(x, fmt):
        return "—" if x is None or (isinstance(x, float) and not math.isfinite(x)) else format(x, fmt)

    lines = ["# start_rule_paired_v1 (WP60) — results", "", f"Commit `{summary['commit']}`; 5 seeds paired; ratio = best_of_16 / uniform min-bulk-ESS per gradient.", "",
             "| model | paired | ratio geomean | per-seed ratios | seeds < 1 | passes u / b | grads median u / b | warmup grads median u / b | start log density median u / b | min-step / median-step u ; b | max abs z u / b |",
             "|---|---:|---:|---|---:|---|---|---|---|---|---|"]
    for m in MODEL_LIST:
        r = per_model[m]
        u, b = r["uniform"], r["best_of_16"]
        lines.append(f"| {m} | {len(r['paired_seeds'])} | **{f(r['ratio_geomean'], '.3f')}** | {', '.join(f'{x:.2f}' for x in r['per_seed_ratio'].values())} | {r['seeds_below_1']} | "
                     f"{u['passed']}/{u['n']} / {b['passed']}/{b['n']} | {f(u['gradients_median'], ',.0f')} / {f(b['gradients_median'], ',.0f')} | "
                     f"{f(u['warmup_gradients_median'], ',.0f')} / {f(b['warmup_gradients_median'], ',.0f')} | {f(u['start_log_density_median'], '.1f')} / {f(b['start_log_density_median'], '.1f')} | "
                     f"{u['step_min_over_median']} ; {b['step_min_over_median']} | {f(u['max_abs_z_max'], '.2f')} / {f(b['max_abs_z_max'], '.2f')} |")
    lines += ["", f"**Paired geomean over the six models: {f(g, '.3f')}** ({below}/6 models below 1.0; pooled over all pairs {f(pooled, '.3f')}); complete: {complete}",
              f"**Hypothesis:** {hyp}", f"**Decision (frozen rule):** {decision}",
              f"Passes: uniform {summary['passes']['uniform']}/30, best_of_16 {summary['passes']['best_of_16']}/30"]
    (ART / "results-table.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    a = sys.argv[1:]
    if not a or a[0] == "run":
        run_all()
    elif a[0] == "analyze":
        analyze()
    else:
        raise SystemExit(__doc__)
