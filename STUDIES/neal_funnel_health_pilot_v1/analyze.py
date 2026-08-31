"""Checksumable post-run analysis for the frozen Neal funnel health pilot."""
import hashlib
import json
from pathlib import Path

import arviz as az
import numpy as np

ROOT = Path(__file__).resolve().parent
RESULTS = ROOT / "artifacts" / "results-corrected"
OUT = ROOT / "artifacts" / "summary-corrected.json"


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def diagnostics(samples):
    rows = []
    for coordinate in range(samples.shape[2]):
        values = samples[:, :, coordinate]
        rows.append(
            {
                "coordinate": coordinate,
                "rank_rhat": float(az.rhat(values, method="rank")),
                "bulk_ess": float(az.ess(values, method="bulk")),
                "tail_ess": float(az.ess(values, method="tail", prob=(0.05, 0.95))),
                "mean": float(values.mean()),
                "variance_population": float(values.var()),
            }
        )
    return rows


cells = []
for path in sorted(RESULTS.glob("*.json")):
    raw = json.loads(path.read_text())
    samples = np.asarray(raw.pop("samples"), dtype=np.float64)
    rows = diagnostics(samples)
    chains = raw["chains"]
    retained = samples.shape[0] * samples.shape[1]
    health = {
        key: int(sum(chain[key] for chain in chains))
        for key in (
            "target_calls",
            "divergences",
            "invalid_evaluation_stops",
            "refinement_exhaustion_stops",
            "reverse_coarser_stops",
            "reverse_coarser_rejections",
            "maximum_depth_stops",
            "recoverable_target_failures",
            "forward_refinement_attempts",
            "forward_micro_steps",
            "reverse_coarsening_attempts",
            "reverse_micro_steps",
        )
    }
    gates = {
        "rank_rhat": max(row["rank_rhat"] for row in rows) <= 1.01,
        "bulk_ess": min(row["bulk_ess"] for row in rows) >= 400,
        "tail_ess": min(row["tail_ess"] for row in rows) >= 400,
        "zero_divergences": health["divergences"] == 0,
        "zero_invalid": health["invalid_evaluation_stops"] == 0,
        "zero_recoverable": health["recoverable_target_failures"] == 0,
        "zero_refinement_exhaustion": health["refinement_exhaustion_stops"] == 0,
        "maximum_depth_rate": health["maximum_depth_stops"] / retained <= 0.01,
    }
    scale = rows[0]
    scale_se = np.sqrt(scale["variance_population"] / scale["bulk_ess"])
    scale["mean_mc_interval_95_descriptive"] = [
        scale["mean"] - 1.96 * scale_se,
        scale["mean"] + 1.96 * scale_se,
    ]
    scale["moment_gate_status"] = (
        "not classifiable: frozen protocol did not specify the interval construction"
    )
    raw.update(
        {
            "artifact": path.name,
            "artifact_sha256": sha256(path),
            "coordinate_diagnostics": rows,
            "health_totals": health,
            "retained_maximum_depth_rate": health["maximum_depth_stops"] / retained,
            "scale_bulk_ess_per_second": scale["bulk_ess"]
            / raw["kernel_seconds_including_warmup"],
            "scale_bulk_ess_per_target_call": scale["bulk_ess"]
            / health["target_calls"],
            "specified_health_gates": gates,
            "specified_health_gates_passed": all(gates.values()),
            "eligible": False,
            "eligibility_note": (
                "specified rank/ESS/health gates failed"
                if not all(gates.values())
                else "moment gates are under-specified in protocol v1"
            ),
        }
    )
    cells.append(raw)

complete = len(cells) == 12
all_specified_health = complete and all(cell["specified_health_gates_passed"] for cell in cells)
summary = {
    "schema": "owalnuts-neal-funnel-health-pilot-summary-v1",
    "evidence_class": "authorized bounded pilot; not confirmation",
    "complete": complete,
    "all_specified_health_gates_passed": all_specified_health,
    "all_required_cells_eligible": False,
    "selected_setting": None,
    "decision": (
        "No selection: no cell passed the specified rank/ESS/health gates on all seeds. "
        "Additionally, frozen moment gates omitted their interval construction."
    ),
    "cells": cells,
}
OUT.write_text(json.dumps(summary, indent=2))
print(json.dumps({k: summary[k] for k in summary if k != "cells"}, indent=2))
