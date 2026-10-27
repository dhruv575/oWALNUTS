#!/usr/bin/env python3
"""Metadata/hash inventory only. Does not fit baselines or score observations."""
import hashlib
import json
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SOURCE = HERE.parent / "pool_confirm_v1"
RUN_COMMIT = "a355bae52233b9e5ede69953bb23fb899a43859f"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git_digest(relative):
    raw = subprocess.check_output(["git", "show", f"{RUN_COMMIT}:{relative}"], cwd=ROOT)
    return hashlib.sha256(raw).hexdigest()


def build():
    protocol = json.loads((SOURCE / "protocol.json").read_text())
    cells = SOURCE / "artifacts/cells"
    hashes = {}
    for line in (SOURCE / "CHECKSUMS.sha256").read_text().splitlines():
        expected, relative = line.split("  ", 1)
        hashes[relative] = expected
    datasets = []
    for dataset in ("sim", "real"):
        data_path = SOURCE / protocol["datasets"][dataset]["file"]
        data = json.loads(data_path.read_text())
        assert digest(data_path) == protocol["datasets"][dataset]["sha256"]
        origins = []
        for tick in range(1, 101):
            n = 250 + tick
            assert n < len(data["y"])
            ref_id = f"ref-{dataset}-{'lo' if tick <= 50 else 'hi'}"
            requests = [("reference", ref_id, None)] + [
                ("warm_K200", f"warm200-{dataset}-s{seed}", seed)
                for seed in protocol["arms"]["seeds"][dataset]
            ]
            sources = []
            for arm, cell_id, seed in requests:
                raw_lines = (cells / cell_id / "ticks.jsonl").read_bytes().splitlines(keepends=True)
                selected = [line for line in raw_lines if json.loads(line).get("tick") == tick]
                assert len(selected) == 1
                record = json.loads(selected[0])
                assert record["status"] == "ok" and record["n"] == n
                filename = record["file"] if arm == "reference" else f"tick-{tick:03}.f32"
                path = cells / cell_id / filename
                relative = path.relative_to(SOURCE).as_posix()
                actual = digest(path)
                assert actual == hashes[relative]
                assert path.stat().st_size == record["chains"] * record["draws"] * 4 * 4
                sources.append({
                    "arm": arm, "seed": seed, "cell": cell_id,
                    "file_relative_to_wp97": relative, "sha256": actual,
                    "record_sha256": hashlib.sha256(selected[0]).hexdigest(),
                    "shape": [record["chains"], record["draws"], 4],
                    "kept_chains": record["kept"],
                    "selected_reference_attempt": record.get("attempt") if arm == "reference" else None,
                })
            origins.append({
                "tick": tick, "sv_observed_indices": [0, n],
                "sv_observed_slice": f"y[:{n}]", "next_label_index": n,
                "rolling_t5_training_slice": [tick, n],
                "nig_training_response_indices": [max(1, n - 256), n],
                "nig_forecast_lag_index": n - 1,
                "sources": sources,
            })
        datasets.append({
            "dataset": dataset, "data_file_relative_to_wp97": protocol["datasets"][dataset]["file"],
            "data_sha256": digest(data_path), "returns_available": len(data["y"]),
            "scheduled_origins": 100, "next_label_indices_inclusive": [251, 350],
            "origins": origins,
        })
    baseline_sources = []
    for relative in (
        "STUDIES/market_uncertainty_v1/historical_evaluation/evaluate.py",
        "STUDIES/market_uncertainty_v1/forecast_baseline/forecast.py",
    ):
        baseline_sources.append({
            "path_relative_to_repo": relative, "working_file_sha256": digest(ROOT / relative),
            "git_blob_sha256_at_source_run_commit": git_digest(relative),
        })
    return {
        "status": "inventory_only_no_predictive_outcomes",
        "source_study": "WP97-POOL-CONFIRM-V1", "source_run_commit": RUN_COMMIT,
        "source_protocol_git_blob_sha256": git_digest("STUDIES/pool_confirm_v1/protocol.json"),
        "source_evidence_archive_sha256": "19a89ac0ac401e0700d3140e33e71637658d0cc791a52806dc3eaa38013de595",
        "raw_schema": ["mu", "log_sigma", "beta", "h_last"], "raw_dtype": "little-endian float32",
        "index_convention": "All indices zero-based; slice pairs are [inclusive_start, exclusive_end].",
        "reference_distributions": 200, "warm_distributions": 600,
        "independent_observed_streams": 2,
        "scope": "Already-inspected simulated and real streams; retrospective current-target and warm-fidelity diagnostic only.",
        "baseline_source_identity": baseline_sources,
        "datasets": datasets,
    }


if __name__ == "__main__":
    output = HERE / "ORIGIN-INVENTORY.json"
    if output.exists():
        raise SystemExit(f"refusing to overwrite {output}")
    result = build()
    output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print("Inventoried 200 reference and 600 warm distributions; all 200 next labels exist. No scores computed.")
