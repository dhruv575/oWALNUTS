"""Post-processing only: gates and summary for the truncated-Gaussian arm.

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
EXACT = PROTOCOL["target"]["exact"]


def diagnostics(x):
    return (
        float(az.rhat(x)),
        float(az.ess(x, method="bulk")),
        float(az.ess(x, method="tail", prob=(0.05, 0.95))),
    )


def main():
    import sys
    name = sys.argv[1] if len(sys.argv) > 1 else "T"
    a = json.loads((ART / f"{name}.json").read_text(encoding="utf-8"))
    s = np.asarray(a["samples"], dtype=np.float64)  # (chains, draws, 2)
    x0, x1 = s[:, :, 0], s[:, :, 1]
    out = {
        "arm": name,
        "algorithm_revision": a["algorithm_revision"],
        "chains": int(s.shape[0]),
        "retained_per_chain": int(s.shape[1]),
        "wall_seconds": a["wall_seconds"],
        "total_target_calls": a["total_target_calls"],
        "total_recoverable_failures": a["total_recoverable_failures"],
    }
    ret = [c["retained"] for c in a["chains"]]
    out["retained"] = {
        k: int(sum(c[k] for c in ret))
        for k in (
            "target_calls", "divergences", "invalid_evaluation_stops",
            "refinement_exhaustion_stops", "reverse_coarser_stops", "maximum_depth_stops",
            "recoverable_target_failures", "zero_density_evaluations", "leaves_attempted",
            "leaves_built",
        )
    }
    out["retained"]["mean_depth"] = float(np.mean([c["mean_depth"] for c in ret]))
    out["retained"]["stops"] = {}
    for c in ret:
        for k, v in c["stops"].items():
            out["retained"]["stops"][k] = out["retained"]["stops"].get(k, 0) + v
    moments = {}
    for label, arr, mean_key, var_key in (("x0", x0, "mean_x0", "var_x0"), ("x1", x1, "mean_x1", "var_x1")):
        rhat, bulk, tail = diagnostics(arr)
        flat = arr.reshape(-1)
        mean = float(flat.mean())
        var = float(flat.var())
        sq = (arr - mean) ** 2
        ess_sq = float(az.ess(sq, method="bulk"))
        mcse_mean = math.sqrt(var / bulk)
        mcse_var = math.sqrt(float(sq.reshape(-1).var()) / ess_sq)
        moments[label] = {
            "rhat": rhat, "bulk_ess": bulk, "tail_ess": tail,
            "mean": mean, "exact_mean": EXACT[mean_key], "mean_z": (mean - EXACT[mean_key]) / mcse_mean,
            "variance": var, "exact_variance": EXACT[var_key], "variance_z": (var - EXACT[var_key]) / mcse_var,
        }
    out["moments"] = moments
    gates = {
        "all_draws_inside": bool((x0 > 0).all()),
        "invalid_evaluation_stops": out["retained"]["invalid_evaluation_stops"] <= G["retained_invalid_evaluation_stops_max"],
        "divergences": out["retained"]["divergences"] <= G["retained_divergences_max"],
        "recoverable_failures_present": out["retained"]["recoverable_target_failures"] >= G["recoverable_failures_min"],
        "zero_density_equals_recoverable": out["retained"]["zero_density_evaluations"] == out["retained"]["recoverable_target_failures"],
        "rhat": all(m["rhat"] <= G["rhat_max"] for m in moments.values()),
        "bulk_ess": all(m["bulk_ess"] >= G["bulk_ess_min"] for m in moments.values()),
        "tail_ess": all(m["tail_ess"] >= G["tail_ess_min"] for m in moments.values()),
        "moments": all(abs(m["mean_z"]) <= G["moment_z_max"] and abs(m["variance_z"]) <= G["moment_z_max"] for m in moments.values()),
    }
    out["gates"] = gates
    out["passed"] = all(gates.values())
    (ART / ("summary.json" if name == "T" else f"summary-{name}.json")).write_text(json.dumps(out, indent=1), encoding="utf-8")
    print(json.dumps({"gates": gates, "passed": out["passed"], "moments": {k: {kk: round(vv, 4) if isinstance(vv, float) else vv for kk, vv in v.items()} for k, v in moments.items()}, "retained": out["retained"]}, indent=1))


if __name__ == "__main__":
    main()
