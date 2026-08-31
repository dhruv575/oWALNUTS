"""Post-processing only: gates and summary for every arm artifact present.

Usage: python analyze.py  (writes artifacts/summary.json and prints a table)
"""
import json
import math
from pathlib import Path

import arviz as az
import numpy as np

HERE = Path(__file__).resolve().parent
ART = HERE / "artifacts"
PROTOCOL = json.loads((HERE / "protocol.json").read_text(encoding="utf-8"))
G = PROTOCOL["gates"]
ARMS = ["F50", "F"]
PHI = lambda z: 0.5 * (1 + math.erf(z / math.sqrt(2)))


def diagnostics(x):
    """x: (chains, draws). Returns rank R-hat, bulk ESS, tail ESS."""
    return (
        float(az.rhat(x)),
        float(az.ess(x, method="bulk")),
        float(az.ess(x, method="tail", prob=(0.05, 0.95))),
    )


def analyze(name):
    path = ART / f"{name}.json"
    if not path.is_file():
        return None
    a = json.loads(path.read_text(encoding="utf-8"))
    s = np.asarray(a["samples"], dtype=np.float64)  # (chains, draws, dim)
    omega, x1 = s[:, :, 0], s[:, :, 1]
    out = {"arm": name, "chains": int(s.shape[0]), "retained_per_chain": int(s.shape[1])}
    r = {}
    for label, arr in (("omega", omega), ("x1", x1)):
        rhat, bulk, tail = diagnostics(arr)
        r[label] = {"rhat": rhat, "bulk_ess": bulk, "tail_ess": tail}
    out["functionals"] = r
    pooled = omega.reshape(-1)
    tail_ess = r["omega"]["tail_ess"]
    bulk_ess = r["omega"]["bulk_ess"]
    out["omega_mean"] = float(pooled.mean())
    out["omega_mean_mcse"] = float(pooled.std(ddof=1) / math.sqrt(max(bulk_ess, 1)))
    out["omega_variance"] = float(pooled.var(ddof=1))
    out["omega_per_chain_mean"] = [float(c.mean()) for c in omega]
    out["omega_per_chain_min"] = [float(c.min()) for c in omega]
    tails = []
    for thr, exact in zip(G["tail_mass_thresholds"], G["tail_mass_exact"]):
        p = float((pooled < thr).mean())
        half = 1.96 * math.sqrt(exact * (1 - exact) / max(tail_ess, 1))
        tails.append({
            "threshold": thr, "observed": p, "exact": exact,
            "interval_half_width": half, "z": (p - exact) / (half / 1.96),
            "within": abs(p - exact) <= half,
            "per_chain": [float((c < thr).mean()) for c in omega],
        })
    out["tail_mass"] = tails
    out["omega_quantiles"] = {
        q: {"observed": float(np.quantile(pooled, float(q))), "exact": v}
        for q, v in G["exact_omega_quantiles"].items()
    }
    # health counters
    if a.get("sampler", "owalnuts").startswith("walnutpie"):
        out["sampler"] = a["sampler"]
        out["final_step_sizes"] = [c["final_step_size"] for c in a["chains"]]
        out["wall_seconds"] = a["wall_seconds_including_warmup"]
        out["target_calls_total_including_warmup"] = a["target_calls_observed_total"]
        health = {"divergences": None, "invalid_evaluation_stops": None,
                  "refinement_exhaustion_stops": None, "maximum_depth_stops": None}
        out["health_available"] = False
    else:
        out["sampler"] = "owalnuts " + a["algorithm_revision"]
        out["settings"] = a["settings"]
        out["wall_seconds"] = a["wall_seconds_including_discarded"]
        out["target_calls_total"] = a["target_callbacks_started"]
        ret = [c["retained"] for c in a["chains"]]
        health = {k: sum(c[k] for c in ret) for k in
                  ("divergences", "invalid_evaluation_stops", "refinement_exhaustion_stops",
                   "maximum_depth_stops", "reverse_coarser_stops", "target_calls", "leaves_built")}
        out["retained_depth_histogram"] = [sum(h) for h in zip(*[c["depth_histogram"] for c in ret])]
        out["retained_refinement_level_histogram"] = [
            sum(h) for h in zip(*[c["selected_refinement_level_histogram"] for c in ret])]
        stops = {}
        for c in ret:
            for k, v in c["stop_reasons"].items():
                stops[k] = stops.get(k, 0) + v
        out["retained_stop_reasons"] = stops
        out["retained_max_abs_energy_error"] = max(c["max_absolute_energy_error"] for c in ret)
        out["mean_target_calls_per_retained_transition"] = float(np.mean(
            [c["mean_target_calls_per_transition"] for c in ret]))
        out["health_available"] = True
    out["health"] = health
    gates = {
        "rhat_omega": r["omega"]["rhat"] <= G["rhat_max"],
        "rhat_x1": r["x1"]["rhat"] <= G["rhat_max"],
        "bulk_ess_omega": r["omega"]["bulk_ess"] >= G["bulk_ess_min"],
        "tail_ess_omega": r["omega"]["tail_ess"] >= G["tail_ess_min"],
        "bulk_ess_x1": r["x1"]["bulk_ess"] >= G["bulk_ess_min"],
        "tail_ess_x1": r["x1"]["tail_ess"] >= G["tail_ess_min"],
        "health": (None if not out["health_available"] else
                   health["divergences"] == 0 and health["invalid_evaluation_stops"] == 0
                   and health["refinement_exhaustion_stops"] == 0),
        "tail_mass_minus5": tails[0]["within"],
        "tail_mass_minus6": tails[1]["within"],
    }
    out["gates"] = gates
    out["convergence_gates_pass"] = all(v for k, v in gates.items() if k not in ("health", "tail_mass_minus5", "tail_mass_minus6"))
    out["paper_claim_gates_pass"] = (gates["health"] is not False) and gates["tail_mass_minus5"] and gates["tail_mass_minus6"]
    return out


def main():
    results = [r for r in (analyze(n) for n in ARMS) if r]
    summary = {"schema": "owalnuts-funnel-bias-fix-summary/v1",
               "executed_utc_date": "2026-08-31", "arms": results}
    (ART / "summary.json").write_text(json.dumps(summary, indent=1), encoding="utf-8")
    hdr = ("| arm | draws | R-hat ω | R-hat x1 | bulk/tail ESS ω | bulk/tail ESS x1 | mean ω (MCSE) | var ω | "
           "P(ω<-5) obs/exact ±hw | P(ω<-6) obs/exact ±hw | q1% / q0.5% obs (exact −6.98/−7.73) | div/inval/exhaust/depthcap | calls | wall s | conv | claim |")
    print(hdr)
    print("|" + "---|" * (hdr.count("|") - 1))
    for o in results:
        f = o["functionals"]
        h = o["health"]
        hs = ("n/a" if not o["health_available"] else
              f"{h['divergences']}/{h['invalid_evaluation_stops']}/{h['refinement_exhaustion_stops']}/{h['maximum_depth_stops']}")
        t5, t6 = o["tail_mass"]
        calls = o.get("target_calls_total", o.get("target_calls_total_including_warmup"))
        print(f"| {o['arm']} | 4×{o['retained_per_chain']} | {f['omega']['rhat']:.4f} | {f['x1']['rhat']:.4f} | "
              f"{f['omega']['bulk_ess']:.0f}/{f['omega']['tail_ess']:.0f} | {f['x1']['bulk_ess']:.0f}/{f['x1']['tail_ess']:.0f} | "
              f"{o['omega_mean']:+.3f} ({o['omega_mean_mcse']:.3f}) | {o['omega_variance']:.2f} | "
              f"{t5['observed']:.4f}/{t5['exact']:.4f} ±{t5['interval_half_width']:.4f} | "
              f"{t6['observed']:.4f}/{t6['exact']:.4f} ±{t6['interval_half_width']:.4f} | "
              f"{o['omega_quantiles']['0.01']['observed']:.2f} / {o['omega_quantiles']['0.005']['observed']:.2f} | {hs} | {calls} | "
              f"{o['wall_seconds']:.1f} | {'pass' if o['convergence_gates_pass'] else 'FAIL'} | "
              f"{'pass' if o['paper_claim_gates_pass'] else 'FAIL'} |")


if __name__ == "__main__":
    main()
