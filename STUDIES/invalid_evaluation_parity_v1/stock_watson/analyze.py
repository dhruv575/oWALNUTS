"""Post-processing only: gates and summary for every arm artifact present.

Usage: python analyze.py  (writes artifacts/summary.json and prints a table)
"""
import json
from pathlib import Path

import arviz as az
import numpy as np

HERE = Path(__file__).resolve().parent
ART = HERE / "artifacts"
PROTOCOL = json.loads((HERE / "protocol.json").read_text(encoding="utf-8"))
G = PROTOCOL["gates"]
ARMS = list(PROTOCOL["arms"])


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
    f = np.asarray(a["functionals"], dtype=np.float64)  # (chains, draws, k)
    names = a["functional_names"]
    out = {"arm": name, "chains": int(f.shape[0]), "retained_per_chain": int(f.shape[1]),
           "settings": a["settings"], "algorithm_revision": a["algorithm_revision"],
           "wall_seconds": a["wall_seconds_including_discarded"], "threads": a["threads"]}
    r = {}
    for i, label in enumerate(names):
        rhat, bulk, tail = diagnostics(f[:, :, i])
        pooled = f[:, :, i].reshape(-1)
        r[label] = {"rhat": rhat, "bulk_ess": bulk, "tail_ess": tail,
                    "mean": float(pooled.mean()), "sd": float(pooled.std(ddof=1)),
                    "per_chain_mean": [float(c.mean()) for c in f[:, :, i]]}
    out["functionals"] = r
    ret = [c["retained"] for c in a["chains"]]
    health = {k: sum(c[k] for c in ret) for k in
              ("target_calls", "divergences", "invalid_evaluation_stops", "refinement_exhaustion_stops",
               "reverse_coarser_stops", "maximum_depth_stops", "leaves_built", "forward_micro_steps")}
    transitions = sum(sum(c["depth_histogram"]) for c in ret)
    health["retained_transitions"] = transitions
    health["maximum_depth_rate"] = health["maximum_depth_stops"] / max(transitions, 1)
    health["mean_target_calls_per_transition"] = health["target_calls"] / max(transitions, 1)
    out["health"] = health
    out["depth_histogram"] = [sum(c["depth_histogram"][d] for c in ret) for d in range(len(ret[0]["depth_histogram"]))]
    out["selected_refinement_level_histogram"] = [
        sum(c["selected_refinement_level_histogram"][d] for c in ret)
        for d in range(len(ret[0]["selected_refinement_level_histogram"]))]
    # Energy error headline: pooled retained per-orbit Hamiltonian range and max |dH|.
    ranges, maxerr = [], []
    for c in a["chains"]:
        cols = c["trace_columns"]
        ir, ie, ip = cols.index("hamiltonian_range"), cols.index("max_abs_energy_error"), cols.index("retained_phase")
        for row in c["trace"]:
            if row[ip] == 1:
                if np.isfinite(row[ir]):
                    ranges.append(row[ir])
                if np.isfinite(row[ie]):
                    maxerr.append(row[ie])
    def summ(v):
        v = np.asarray(v)
        if v.size == 0:
            return {"count": 0}
        return {"count": int(v.size), "q50": float(np.quantile(v, .5)), "q90": float(np.quantile(v, .9)),
                "q99": float(np.quantile(v, .99)), "max": float(v.max()),
                "fraction_gt_1": float((v > 1).mean()), "fraction_gt_2": float((v > 2).mean()),
                "fraction_gt_5": float((v > 5).mean())}
    out["hamiltonian_range"] = summ(ranges)
    out["max_abs_energy_error"] = summ(maxerr)
    out["final_tuning_per_chain"] = [c["final_tuning"] for c in a["chains"]]
    out["paper_adaptation_updates"] = [c["paper_adaptation_updates"] for c in a["chains"]]
    # Gates.
    gates = {}
    for label in G["functionals"]:
        gates[f"rhat_{label}"] = r[label]["rhat"] <= G["rhat_max"]
        gates[f"bulk_ess_{label}"] = r[label]["bulk_ess"] >= G["bulk_ess_min"]
        gates[f"tail_ess_{label}"] = r[label]["tail_ess"] >= G["tail_ess_min"]
    gates["divergences"] = health["divergences"] <= G["retained_divergences_max"]
    gates["invalid_evaluations"] = health["invalid_evaluation_stops"] <= G["retained_invalid_evaluations_max"]
    gates["refinement_exhaustions"] = health["refinement_exhaustion_stops"] <= G["retained_refinement_exhaustions_max"]
    gates["maximum_depth_rate"] = health["maximum_depth_rate"] <= G["maximum_depth_rate_max"]
    out["gates"] = gates
    out["all_gates_passed"] = all(gates.values())
    out["ess_per_call"] = {label: r[label]["bulk_ess"] / max(health["target_calls"], 1) for label in G["functionals"]}
    out["ess_per_second"] = {label: r[label]["bulk_ess"] / max(out["wall_seconds"], 1e-9) for label in G["functionals"]}
    return out


def main():
    results = {name: analyze(name) for name in ARMS}
    results = {k: v for k, v in results.items() if v is not None}
    claim = None
    if "F" in results and "N" in results:
        f_ok = results["F"]["all_gates_passed"] and results["F"]["hamiltonian_range"].get("fraction_gt_2", 1) <= 0.01
        n_bad = results["N"]["hamiltonian_range"].get("fraction_gt_2", 0) > 0.10
        claim = {"arm_F_gates_and_energy_ok": bool(f_ok), "arm_N_energy_fraction_gt_2_exceeds_0.10": bool(n_bad),
                 "paper_claim_reproduced": bool(f_ok and n_bad)}
    summary = {"schema": "owalnuts-paper-stock-watson-summary/v1", "arms": results, "paper_claim": claim}
    (ART / "summary.json").write_text(json.dumps(summary, indent=1), encoding="utf-8")
    print(f"{'arm':4} {'pass':5} {'maxRhat':8} {'minBulk':8} {'minTail':8} {'div':4} {'exh':4} {'depth%':7} {'calls':11} {'wall s':8} {'H>2':7} {'H q99':8}")
    for name, res in results.items():
        fx = [res["functionals"][l] for l in G["functionals"]]
        h = res["health"]
        print(f"{name:4} {str(res['all_gates_passed']):5} {max(x['rhat'] for x in fx):8.4f} {min(x['bulk_ess'] for x in fx):8.1f} "
              f"{min(x['tail_ess'] for x in fx):8.1f} {h['divergences']:4d} {h['refinement_exhaustion_stops']:4d} "
              f"{100*h['maximum_depth_rate']:7.2f} {h['target_calls']:11d} {res['wall_seconds']:8.1f} "
              f"{res['hamiltonian_range'].get('fraction_gt_2', float('nan')):7.4f} {res['hamiltonian_range'].get('q99', float('nan')):8.3f}")
    print("paper_claim:", claim)


if __name__ == "__main__":
    main()
