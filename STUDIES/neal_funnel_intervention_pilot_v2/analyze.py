"""Frozen analysis and selection rule for Neal funnel intervention pilot v2."""
import argparse
import json
import os
import tempfile
from pathlib import Path

import arviz as az
import numpy as np

SEEDS = [2026091101, 2026091102, 2026091103]
EXPECTED = [
    (seed, initialization, adaptation)
    for seed in SEEDS
    for initialization in ("Dispersed", "CommonZero")
    for adaptation in ("Baseline", "Robust")
]


def atomic_create(path: Path, value: object) -> None:
    if path.exists():
        raise FileExistsError(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary = tempfile.mkstemp(prefix=path.name, suffix=".pending", dir=path.parent)
    try:
        with os.fdopen(handle, "w") as stream:
            json.dump(value, stream, indent=2)
            stream.flush()
            os.fsync(stream.fileno())
        os.link(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def coordinate_diagnostics(samples: np.ndarray) -> list[dict]:
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
                "variance": float(values.var()),
            }
        )
    return rows


def analyze(directory: Path) -> dict:
    paths = sorted(directory.glob("cell-??.json"))
    if len(paths) != 12:
        raise RuntimeError("exactly 12 complete cell artifacts are required")
    cells = []
    for index, (path, expected) in enumerate(zip(paths, EXPECTED)):
        raw = json.loads(path.read_text())
        if (
            raw.get("cell_index") != index
            or (raw.get("seed"), raw.get("initialization"), raw.get("adaptation")) != expected
            or raw.get("callback_cap") != 1_000_000_000
            or raw.get("wall_cap_seconds") != 300
            or raw.get("retained") != 10_000
        ):
            raise RuntimeError(f"cell {index} metadata differs from frozen protocol")
        samples = np.asarray(raw.pop("samples"), dtype=np.float64)
        if samples.shape != (4, 10_000, 10):
            raise RuntimeError(f"cell {index} sample shape is invalid")
        diagnostics = coordinate_diagnostics(samples)
        totals = {
            key: sum(chain[key] for chain in raw["chains"])
            for key in (
                "target_calls",
                "divergences",
                "invalid_stops",
                "refinement_exhaustions",
                "maximum_depth_stops",
                "recoverable_target_failures",
                "reverse_coarser_stops",
                "reverse_coarser_rejections",
            )
        }
        scale = diagnostics[0]
        steps = [chain["qualified_step_size"] for chain in raw["chains"]]
        gates = {
            "zero_divergences": totals["divergences"] == 0,
            "zero_invalid": totals["invalid_stops"] == 0,
            "zero_refinement_exhaustion": totals["refinement_exhaustions"] == 0,
            "zero_recoverable": totals["recoverable_target_failures"] == 0,
            "maximum_depth_rate": totals["maximum_depth_stops"] / 40_000 <= 0.01,
            "rank_rhat": max(row["rank_rhat"] for row in diagnostics) <= 1.05,
            "scale_bulk_ess": scale["bulk_ess"] >= 100,
            "scale_tail_ess": scale["tail_ess"] >= 100,
            "scale_mean": abs(scale["mean"]) <= 1.0,
            "scale_variance": 6.0 <= scale["variance"] <= 13.5,
            "projected_bulk_ess": 5.0 * scale["bulk_ess"] >= 400,
            "projected_tail_ess": 5.0 * scale["tail_ess"] >= 400,
            "step_size_ratio": max(steps) / min(steps) <= 4.0,
        }
        raw.update(
            {
                "coordinate_diagnostics": diagnostics,
                "health_totals": totals,
                "scale_bulk_ess_per_target_call": scale["bulk_ess"] / totals["target_calls"],
                "gates": gates,
                "eligible": all(gates.values()),
            }
        )
        cells.append(raw)

    lookup = {
        (cell["seed"], cell["initialization"], cell["adaptation"]): cell for cell in cells
    }
    dispersed_ratios = []
    sensitivity_ratios = []
    for seed in SEEDS:
        dispersed_baseline = lookup[(seed, "Dispersed", "Baseline")]
        dispersed_robust = lookup[(seed, "Dispersed", "Robust")]
        zero_robust = lookup[(seed, "CommonZero", "Robust")]
        dispersed_ratios.append(
            dispersed_robust["scale_bulk_ess_per_target_call"]
            / dispersed_baseline["scale_bulk_ess_per_target_call"]
        )
        sensitivity_ratios.append(
            zero_robust["scale_bulk_ess_per_target_call"]
            / dispersed_robust["scale_bulk_ess_per_target_call"]
        )
    robust = [cell for cell in cells if cell["adaptation"] == "Robust"]
    selection = {
        "all_robust_cells_eligible": all(cell["eligible"] for cell in robust),
        "dispersed_seed_ratios": dispersed_ratios,
        "dispersed_median_ratio": float(np.median(dispersed_ratios)),
        "robust_start_sensitivity_ratios": sensitivity_ratios,
    }
    selected = (
        selection["all_robust_cells_eligible"]
        and selection["dispersed_median_ratio"] >= 1.5
        and min(dispersed_ratios) >= 0.8
        and all(0.67 <= ratio <= 1.5 for ratio in sensitivity_ratios)
    )
    selection["selected"] = selected
    return {
        "schema": "neal-funnel-intervention-pilot-v2-summary",
        "evidence_class": "mechanism-and-feasibility pilot; not confirmation",
        "cells": cells,
        "selection": selection,
        "decision": "advance robust policy to confirmation" if selected else "no selection",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    atomic_create(args.output, analyze(args.input))


if __name__ == "__main__":
    main()
