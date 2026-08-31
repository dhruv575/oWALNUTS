"""Post-processing only: gates, adaptation landing, and efficiency vs the F9 control.

Usage: python analyze.py  (writes artifacts/summary.json and prints tables)
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
CONTROL = HERE.parent / "funnel_bias_fix_v1" / "artifacts" / "summary.json"


def diagnostics(x):
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
    s = np.asarray(a["samples"], dtype=np.float64)
    omega, x1 = s[:, :, 0], s[:, :, 1]
    out = {"arm": name, "mode": a["settings"]["mode"], "chains": int(s.shape[0]),
           "retained_per_chain": int(s.shape[1]), "algorithm_revision": a["algorithm_revision"],
           "paper_adaptation_revision": a.get("paper_adaptation_revision"),
           "settings": a["settings"], "base_seed": a["base_seed"]}
    r = {}
    for label, arr in (("omega", omega), ("x1", x1)):
        rhat, bulk, tail = diagnostics(arr)
        r[label] = {"rhat": rhat, "bulk_ess": bulk, "tail_ess": tail}
    out["functionals"] = r
    pooled = omega.reshape(-1)
    tail_ess = r["omega"]["tail_ess"]
    out["omega_mean"] = float(pooled.mean())
    out["omega_mean_mcse"] = float(pooled.std(ddof=1) / math.sqrt(max(r["omega"]["bulk_ess"], 1)))
    out["omega_variance"] = float(pooled.var(ddof=1))
    out["omega_per_chain_mean"] = [float(c.mean()) for c in omega]
    out["omega_per_chain_min"] = [float(c.min()) for c in omega]
    tails = []
    for thr, exact, tol in zip(G["tail_mass_thresholds"], G["tail_mass_exact"], G["tail_mass_tolerance"]):
        p = float((pooled < thr).mean())
        half = 1.96 * math.sqrt(exact * (1 - exact) / max(tail_ess, 1))
        tails.append({"threshold": thr, "observed": p, "exact": exact, "tolerance": tol,
                      "mc_half_width": half, "z": (p - exact) / (half / 1.96),
                      "within_tolerance": abs(p - exact) <= tol,
                      "per_chain": [float((c < thr).mean()) for c in omega]})
    out["tail_mass"] = tails
    out["omega_quantiles"] = {q: {"observed": float(np.quantile(pooled, float(q))), "exact": v}
                              for q, v in G["exact_omega_quantiles"].items()}
    ret = [c["retained"] for c in a["chains"]]
    health = {k: sum(c[k] for c in ret) for k in
              ("divergences", "invalid_evaluation_stops", "refinement_exhaustion_stops",
               "maximum_depth_stops", "reverse_coarser_stops", "target_calls", "leaves_built")}
    out["health"] = health
    out["discarded"] = {k: sum(c["discarded"][k] for c in a["chains"]) for k in
                        ("target_calls", "divergences", "invalid_evaluation_stops",
                         "refinement_exhaustion_stops", "maximum_depth_stops")}
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
    out["wall_seconds"] = a["wall_seconds_including_discarded"]
    out["target_calls_total"] = a["target_callbacks_started"]
    out["retained_target_calls"] = health["target_calls"]
    out["bulk_ess_omega_per_retained_call"] = r["omega"]["bulk_ess"] / max(health["target_calls"], 1)
    out["tail_ess_omega_per_retained_call"] = r["omega"]["tail_ess"] / max(health["target_calls"], 1)
    out["pooled_retained_orbit_energy_range_quantiles"] = a["pooled_retained_orbit_energy_range_quantiles"]
    out["per_chain_energy_range_q95"] = [c["retained_orbit_energy_range_quantiles"]["q95"] for c in a["chains"]]
    finals = [c["final_tuning"] for c in a["chains"]]
    deltas = [f["max_error"] for f in finals]
    steps = [f["step_size"] for f in finals]
    out["final_delta_per_chain"] = deltas
    out["final_step_per_chain"] = steps
    out["final_delta_spread_ratio"] = max(deltas) / min(deltas)
    out["final_step_spread_ratio"] = max(steps) / min(steps)
    out["adaptation_updates_per_chain"] = [c["paper_adaptation_updates"] for c in a["chains"]]
    gates = {
        "tail_mass_minus5": tails[0]["within_tolerance"],
        "tail_mass_minus6": tails[1]["within_tolerance"],
        "omega_variance": G["omega_variance_interval"][0] <= out["omega_variance"] <= G["omega_variance_interval"][1],
        "health": health["divergences"] == 0 and health["invalid_evaluation_stops"] == 0
        and health["refinement_exhaustion_stops"] == 0,
        "rhat_omega": r["omega"]["rhat"] <= G["rhat_max"],
        "rhat_x1": r["x1"]["rhat"] <= G["rhat_max"],
        "bulk_ess_omega": r["omega"]["bulk_ess"] >= G["bulk_ess_min"],
        "tail_ess_omega": r["omega"]["tail_ess"] >= G["tail_ess_min"],
        "bulk_ess_x1": r["x1"]["bulk_ess"] >= G["bulk_ess_min"],
        "tail_ess_x1": r["x1"]["tail_ess"] >= G["tail_ess_min"],
    }
    out["gates"] = gates
    out["all_gates_pass"] = all(gates.values())
    return out


def control():
    if not CONTROL.is_file():
        return None
    c = json.loads(CONTROL.read_text(encoding="utf-8"))
    f9 = next(a for a in c["arms"] if a["arm"] == "F50")
    calls = f9["health"]["target_calls"]
    return {"arm": "F9 (funnel_bias_fix_v1 F50)", "bulk_ess_omega": f9["functionals"]["omega"]["bulk_ess"],
            "tail_ess_omega": f9["functionals"]["omega"]["tail_ess"], "retained_target_calls": calls,
            "bulk_ess_omega_per_retained_call": f9["functionals"]["omega"]["bulk_ess"] / calls,
            "tail_ess_omega_per_retained_call": f9["functionals"]["omega"]["tail_ess"] / calls,
            "omega_variance": f9["omega_variance"], "tail_mass": f9["tail_mass"],
            "final_delta": 0.21, "final_step": 0.36}


def main():
    arms = [r for r in (analyze(n) for n in ("C", "A2", "AD")) if r]
    ctrl = control()
    for o in arms:
        if ctrl and o["mode"] == "paper":
            o["bulk_ess_per_call_ratio_vs_F9"] = o["bulk_ess_omega_per_retained_call"] / ctrl["bulk_ess_omega_per_retained_call"]
            o["tail_ess_per_call_ratio_vs_F9"] = o["tail_ess_omega_per_retained_call"] / ctrl["tail_ess_omega_per_retained_call"]
    summary = {"schema": "owalnuts-paper-funnel-adaptive-summary/v1", "executed_utc_date": "2026-08-31",
               "control": ctrl, "arms": arms}
    (ART / "summary.json").write_text(json.dumps(summary, indent=1), encoding="utf-8")
    print("| arm | Δ | final δ per chain | final h per chain | R-hat ω/x1 | bulk/tail ESS ω | var ω | "
          "P(ω<-5) | P(ω<-6) | q1% | div/inval/exhaust/cap | retained calls | ESS/call ×F9 | gates |")
    print("|" + "---|" * 14)
    for o in arms:
        f = o["functionals"]
        h = o["health"]
        t5, t6 = o["tail_mass"]
        d = o["settings"]["paper"]["global_energy_bound"] if o["settings"]["paper"] else "fixed"
        ratio = o.get("bulk_ess_per_call_ratio_vs_F9")
        print(f"| {o['arm']} | {d} | {', '.join(f'{x:.3f}' for x in o['final_delta_per_chain'])} | "
              f"{', '.join(f'{x:.3f}' for x in o['final_step_per_chain'])} | "
              f"{f['omega']['rhat']:.4f}/{f['x1']['rhat']:.4f} | {f['omega']['bulk_ess']:.0f}/{f['omega']['tail_ess']:.0f} | "
              f"{o['omega_variance']:.2f} | {t5['observed']:.4f} (z {t5['z']:+.2f}) | {t6['observed']:.4f} (z {t6['z']:+.2f}) | "
              f"{o['omega_quantiles']['0.01']['observed']:.2f} | "
              f"{h['divergences']}/{h['invalid_evaluation_stops']}/{h['refinement_exhaustion_stops']}/{h['maximum_depth_stops']} | "
              f"{h['target_calls']} | {ratio if ratio is None else f'{ratio:.2f}'} | "
              f"{'pass' if o['all_gates_pass'] else 'FAIL'} |")
        if o["mode"] == "paper":
            print(f"  updates chain 0: " + "; ".join(
                f"t{u['transition']} w{u['window_index']} K95={u['inflation_quantile'] and round(u['inflation_quantile'], 2)} "
                f"δ {u['max_error_before']:.3f}->{u['max_error_after']:.3f} unref={u['unrefined_fraction_mean'] and round(u['unrefined_fraction_mean'], 3)} "
                f"h {u['step_before']:.3f}->{u['step_after']:.3f} [{u['outcome']}]"
                for u in o["adaptation_updates_per_chain"][0]))
        print(f"  energy-range quantiles (retained, pooled): {o['pooled_retained_orbit_energy_range_quantiles']}")
    if ctrl:
        print(f"control F9: bulk ESS/call {ctrl['bulk_ess_omega_per_retained_call']:.3e}, tail {ctrl['tail_ess_omega_per_retained_call']:.3e}")


if __name__ == "__main__":
    main()
