"""Seed medians of the kernel_efficiency harness output.

Reads artifacts/kernel_efficiency.json, writes artifacts/summary.json and
artifacts/results-table.md.
"""

import json
import statistics
from pathlib import Path

HERE = Path(__file__).resolve().parent
ART = HERE / "artifacts"
data = json.loads((ART / "kernel_efficiency.json").read_text())

FIELDS = [
    "ess_per_gradient",
    "ess_sq_per_gradient",
    "min_bulk_ess",
    "gradients_per_transition",
    "leaves_per_transition",
    "non_leaf_gradients_per_transition",
    "initial_evaluations_per_transition",
    "mean_depth",
    "refined_fraction",
]
STOPS = ["uturn", "outer_uturn", "recursive_uturn", "refinement_exhausted", "reverse_coarser", "max_depth", "divergent"]

summary = {"draws": data["draws"], "warmup": data["warmup"], "seeds": data["seeds"], "targets": {}}
lines = []
for target in data["targets"]:
    name = target["target"]
    arms = {}
    for seed in target["seeds"]:
        for arm in seed["arms"]:
            arms.setdefault(arm["arm"], []).append(arm)
    ref = statistics.median(a["ess_per_gradient"] for a in arms["nuts-ref"])
    table = {}
    for arm_name, cells in arms.items():
        row = {f: statistics.median(c[f] for c in cells) for f in FIELDS}
        row["ess_per_gradient_seeds"] = [c["ess_per_gradient"] for c in cells]
        row["ratio_to_reference"] = row["ess_per_gradient"] / ref
        # ESS per gradient if the initial re-evaluation were cached (exact:
        # the draws do not change).
        row["ess_per_gradient_cached"] = statistics.median(
            c["min_bulk_ess"] / (c["gradients"] - c["initial_evaluations_per_transition"] * c["gradients"] / c["gradients_per_transition"])
            for c in cells
        )
        row["ratio_to_reference_cached"] = row["ess_per_gradient_cached"] / ref
        row["stops"] = {
            s: statistics.median(c["stops"].get(s, 0.0) for c in cells)
            for s in STOPS
            if any(s in c["stops"] for c in cells)
        }
        row["divergent"] = sum(c["divergent"] for c in cells)
        if "draws_identical_to_default" in cells[0]:
            row["draws_identical_to_default"] = all(c["draws_identical_to_default"] for c in cells)
        table[arm_name] = row
    summary["targets"][name] = {"reference_ess_per_gradient": ref, "arms": table}

    lines.append(f"## {name} ({target['dimension']}-D)\n")
    lines.append("| arm | min bulk ESS/grad x1e3 | vs NUTS | with cache x1e3 | vs NUTS | ESS(x^2)/grad x1e3 | grad/transition | leaves/transition | non-leaf grad/tr | depth | refined | stops |")
    lines.append("|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|")
    for arm_name, row in table.items():
        stops = ", ".join(f"{k} {v:.3f}" for k, v in row["stops"].items())
        lines.append(
            f"| {arm_name} | {row['ess_per_gradient']*1e3:.2f} | {row['ratio_to_reference']:.2f}x | "
            f"{row['ess_per_gradient_cached']*1e3:.2f} | {row['ratio_to_reference_cached']:.2f}x | "
            f"{row['ess_sq_per_gradient']*1e3:.2f} | {row['gradients_per_transition']:.1f} | "
            f"{row['leaves_per_transition']:.1f} | {row['non_leaf_gradients_per_transition']:.2f} | "
            f"{row['mean_depth']:.2f} | {row['refined_fraction']:.3f} | {stops} |"
        )
    lines.append("")
    seeds = ", ".join(
        f"{arm}: " + "/".join(f"{v*1e3:.2f}" for v in table[arm]["ess_per_gradient_seeds"])
        for arm in ("nuts-ref", "default", "rhosum", "exhaust-accept+rhosum", "levels1-accept+rhosum")
    )
    lines.append(f"Per-seed min bulk ESS/grad x1e3: {seeds}\n")

(ART / "summary.json").write_text(json.dumps(summary, indent=1))
(ART / "results-table.md").write_text(
    f"# kernel_efficiency_v1 results (seed medians over {len(data['seeds'])} seeds, "
    f"4 chains x {data['warmup']} warmup / {data['draws']} draws)\n\n" + "\n".join(lines)
)
print("\n".join(lines))
