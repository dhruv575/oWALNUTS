#!/usr/bin/env python3
"""Validate and analyze all 84 WP37A outcomes under Amendment 1."""
from __future__ import annotations

import hashlib
import json
import math
import statistics
import struct
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Iterable

import arviz as az
import numpy as np

import run_study as runner

HERE = Path(__file__).resolve().parent
ARTIFACTS = HERE / "artifacts"
CELLS = ARTIFACTS / "cells"
SUMMARY = ARTIFACTS / "summary.json"
GATE_TABLE = ARTIFACTS / "gate-table.md"
RESULTS_TABLE = ARTIFACTS / "results-table.md"
VERDICT = ARTIFACTS / "verdict.md"
EXACT_P5 = 0.0477903522728147
EXACT_P6 = 0.0227501319481792
EXACT_VARIANCE = 9.0
FUNCTIONALS = ("mu", "tau", "mean_theta", "sd_theta", "theta_1", "theta_8")
REQUIRED_WORK_FIELDS = {
    "transitions",
    "momentum_refreshes",
    "standard_normal_components",
    "target_calls_initial",
    "target_calls_forward",
    "target_calls_reverse",
    "target_calls_total",
    "forward_refinement_attempts",
    "forward_micro_steps_executed",
    "reverse_coarsening_attempts",
    "reverse_micro_steps_executed",
    "leaves_attempted",
    "leaves_built",
    "direction_draws",
    "uniform_draws",
    "maximum_depth_stops",
    "recoverable_target_failures",
    "zero_density_evaluations",
    "divergences",
    "invalid_evaluation_stops",
    "refinement_exhaustion_stops",
    "reverse_coarser_stops",
    "reverse_coarser_rejections",
    "accepted_forward_micro_steps",
    "refinement_level_built",
}


def finite_positive(value: Any) -> bool:
    return isinstance(value, (int, float)) and math.isfinite(value) and value > 0


def geometric_mean(values: Iterable[float]) -> float:
    values = list(values)
    if not values or not all(finite_positive(value) for value in values):
        return math.nan
    return float(np.exp(np.mean(np.log(np.asarray(values, dtype=np.float64)))))


def median(values: Iterable[float]) -> float:
    values = list(values)
    if not values or not all(math.isfinite(value) for value in values):
        return math.nan
    return float(statistics.median(values))


def descriptive_ratio(numerator: float, denominator: float) -> float | None:
    if denominator == 0:
        return 1.0 if numerator == 0 else None
    value = numerator / denominator
    return float(value) if math.isfinite(value) else None


def json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_safe(item) for item in value]
    if isinstance(value, np.generic):
        return json_safe(value.item())
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def tail_ess(values: np.ndarray) -> float:
    low = float(az.ess(values, method="quantile", prob=0.05))
    high = float(az.ess(values, method="quantile", prob=0.95))
    return min(low, high)


def scalar_stats(values: np.ndarray) -> dict[str, float]:
    values = np.asarray(values, dtype=np.float64)
    flat = values.reshape(-1)
    return {
        "mean": float(np.mean(flat)),
        "sd": float(np.std(flat, ddof=1)),
        "variance": float(np.var(flat, ddof=1)),
        "mcse_mean": float(az.mcse(values, method="mean")),
        "rank_rhat": float(az.rhat(values, method="rank")),
        "bulk_ess": float(az.ess(values, method="bulk")),
        "tail_ess": tail_ess(values),
    }


def rust_f64_hash(domain: bytes, shape: Iterable[int], values: np.ndarray) -> str:
    shape = tuple(int(extent) for extent in shape)
    array = np.asarray(values, dtype="<f8", order="C")
    digest = hashlib.sha256()
    digest.update(domain)
    digest.update(struct.pack("<Q", len(shape)))
    for extent in shape:
        digest.update(struct.pack("<Q", extent))
    digest.update(array.tobytes(order="C"))
    return digest.hexdigest()


def initial_position_hash(values: Iterable[float]) -> str:
    array = np.asarray(list(values), dtype=np.float64)
    return rust_f64_hash(
        b"delta2_sidechecks_v1.initial_position.v1", array.shape, array
    )


def sum_work(raw: dict[str, Any], phase: str, field: str) -> int:
    return sum(int(chain["work"][phase][field]) for chain in raw["chains_data"])


def aggregate_histogram(raw: dict[str, Any], phase: str = "retained") -> list[int]:
    histograms = [
        list(map(int, chain["work"][phase]["refinement_level_built"]))
        for chain in raw["chains_data"]
    ]
    width = max((len(values) for values in histograms), default=0)
    return [
        sum(values[level] if level < len(values) else 0 for values in histograms)
        for level in range(width)
    ]


def telemetry(raw: dict[str, Any]) -> dict[str, Any]:
    fields = (
        "target_calls_total",
        "divergences",
        "invalid_evaluation_stops",
        "refinement_exhaustion_stops",
        "maximum_depth_stops",
        "reverse_coarser_stops",
        "reverse_coarser_rejections",
    )
    return {
        phase: {
            **{field: sum_work(raw, phase, field) for field in fields},
            "refinement_level_built": aggregate_histogram(raw, phase),
        }
        for phase in ("warmup", "retained", "total")
    }


def final_records(raw: dict[str, Any]) -> dict[str, Any]:
    return {
        "initial_position_sha256_by_chain": raw[
            "initial_position_sha256_by_chain"
        ],
        "phase_target_callbacks": raw["phase_target_callbacks"],
        "final_step_sizes": [
            chain["final_step_size"] for chain in raw["chains_data"]
        ],
        "final_max_errors": [
            chain["final_max_error"] for chain in raw["chains_data"]
        ],
        "final_mass_diagonal": [
            chain["final_mass_diagonal"] for chain in raw["chains_data"]
        ],
        "final_tuning_sha256_by_chain": raw["final_tuning_sha256_by_chain"],
        "final_metric_sha256_by_chain": raw["final_metric_sha256_by_chain"],
        "retained_diagnostics_sha256_by_chain": raw[
            "retained_diagnostics_sha256_by_chain"
        ],
    }


def process_record_valid(
    row: dict[str, Any],
    marker_path: Path,
    process_path: Path,
    raw_path: Path,
) -> tuple[bool, list[str], dict[str, Any] | None, dict[str, Any] | None]:
    errors: list[str] = []
    marker: dict[str, Any] | None = None
    process: dict[str, Any] | None = None
    try:
        marker = json.loads(marker_path.read_text(encoding="utf-8"))
    except Exception as error:
        errors.append(f"launch marker missing or malformed: {error}")
    try:
        process = json.loads(process_path.read_text(encoding="utf-8"))
    except Exception as error:
        errors.append(f"process record missing or malformed: {error}")
    if marker is None or process is None:
        return False, errors, marker, process
    if marker.get("schema") != "owalnuts-delta2-sidechecks-v1-launch":
        errors.append("launch marker schema")
    if process.get("schema") != "owalnuts-delta2-sidechecks-v1-process":
        errors.append("process record schema")
    if marker.get("manifest") != row or process.get("manifest") != row:
        errors.append("marker/process tuple mismatch")
    if (
        not isinstance(marker.get("nonce"), str)
        or len(marker["nonce"]) != 64
        or marker.get("nonce") != process.get("nonce")
    ):
        errors.append("marker/process nonce mismatch")
    if marker.get("command") != process.get("command"):
        errors.append("marker/process command mismatch")
    if marker.get("provenance_record_sha256") != runner.sha256(runner.PROVENANCE):
        errors.append("launch marker provenance hash mismatch")
    if marker.get("binary_sha256") != runner.sha256(runner.BINARY):
        errors.append("launch marker binary hash mismatch")
    if marker.get("timeout_seconds") != runner.TIMEOUTS[row["target"]]:
        errors.append("marker timeout mismatch")
    if process.get("timeout_seconds") != runner.TIMEOUTS[row["target"]]:
        errors.append("process timeout mismatch")
    if process.get("process_created") is not True:
        errors.append("child not created")
    if process.get("timed_out") is not False:
        errors.append("child timed out")
    return_code = process.get("return_code", {})
    if (
        return_code.get("signed_32") != 0
        or return_code.get("unsigned_32") != 0
        or return_code.get("hex_32") != "0x00000000"
    ):
        errors.append("child did not exit once with status zero")
    for stream_name in ("stdout", "stderr"):
        stream = process.get(stream_name, {})
        path = HERE / str(stream.get("path", ""))
        if not path.is_file():
            errors.append(f"{stream_name} file missing")
            continue
        data = path.read_bytes()
        if (
            stream.get("closed") is not True
            or stream.get("bytes") != len(data)
            or stream.get("sha256") != hashlib.sha256(data).hexdigest()
        ):
            errors.append(f"{stream_name} size/hash/closed mismatch")
    raw_record = process.get("raw_result", {})
    if (
        raw_record.get("state") != "atomically_published_before_exit"
        or raw_record.get("exists") is not True
        or not raw_path.is_file()
    ):
        errors.append("raw result was not atomically published before clean exit")
    elif (
        raw_record.get("bytes") != raw_path.stat().st_size
        or raw_record.get("sha256") != runner.sha256(raw_path)
        or raw_record.get("mtime_ns") != raw_path.stat().st_mtime_ns
        or raw_record.get("parse_error") is not None
    ):
        errors.append("raw result size/hash/parse record mismatch")
    required_process = {
        "command",
        "timestamps",
        "stdout",
        "stderr",
        "timeout_seconds",
        "timed_out",
        "return_code",
        "raw_result",
        "failure_reasons",
    }
    if not required_process.issubset(process):
        errors.append("process record is incomplete")
    if process.get("process_valid") is not True or process.get("status") != "process_valid":
        errors.append("parent process assessment failed")
    return not errors, errors, marker, process


def validate_work(work: Any, where: str, errors: list[str]) -> None:
    if not isinstance(work, dict) or set(work) != REQUIRED_WORK_FIELDS:
        errors.append(f"{where}: work fields mismatch")
        return
    for field, value in work.items():
        if field == "refinement_level_built":
            if not isinstance(value, list) or not all(
                isinstance(item, int) and item >= 0 for item in value
            ):
                errors.append(f"{where}: invalid refinement histogram")
        elif not isinstance(value, int) or value < 0:
            errors.append(f"{where}: invalid {field}")


def schema_validate(
    row: dict[str, Any], raw_path: Path
) -> tuple[bool, list[str], dict[str, Any] | None, np.ndarray | None]:
    errors: list[str] = []
    try:
        raw = json.loads(raw_path.read_text(encoding="utf-8"))
    except Exception as error:
        return False, [f"raw malformed: {error}"], None, None
    if not isinstance(raw, dict):
        return False, ["raw is not an object"], None, None
    expected = {
        "target": row["target"],
        "seed": row["seed"],
        "arm": row["arm"],
        "zero_based_repetition": row["zero_based_repetition"],
        "repetition_sentinel": row["sentinel"],
        "manifest": row,
    }
    if raw.get("schema") != runner.RAW_SCHEMA or raw.get("schema_version") != 1:
        errors.append("raw schema mismatch")
    if raw.get("completion_sentinel") != runner.RAW_COMPLETE:
        errors.append("raw completion sentinel mismatch")
    for key, value in expected.items():
        if raw.get(key) != value:
            errors.append(f"raw {key} mismatch")
    variant = raw.get("variant")
    if variant not in {"samples_complete", "sampler_error"}:
        errors.append("raw variant is not permitted")
    config = raw.get("effective_config", {})
    dimension = {"funnel": 10, "eight_schools_strict": 10, "gaussian100": 100}[
        row["target"]
    ]
    retained = {"funnel": 20000, "eight_schools_strict": 1000, "gaussian100": 1000}[
        row["target"]
    ]
    if (
        raw.get("dimension") != dimension
        or raw.get("chains") != 4
        or raw.get("retained") != retained
        or raw.get("timeout_seconds") != runner.TIMEOUTS[row["target"]]
        or not isinstance(config, dict)
    ):
        errors.append("target dimensions/counts/config fields mismatch")
    draws: np.ndarray | None = None
    if variant == "samples_complete":
        chains = raw.get("chains_data")
        if not isinstance(chains, list) or len(chains) != 4:
            errors.append("chains_data is not four chains")
        else:
            try:
                draws = np.asarray([chain["samples"] for chain in chains], dtype=np.float64)
            except Exception as error:
                errors.append(f"samples cannot form float array: {error}")
            if draws is not None and draws.shape != (4, retained, dimension):
                errors.append(f"sample shape {draws.shape} is wrong")
            for index, chain in enumerate(chains):
                if chain.get("chain") != index:
                    errors.append(f"chain {index}: index mismatch")
                position = chain.get("initial_position")
                if (
                    not isinstance(position, list)
                    or len(position) != dimension
                    or chain.get("initial_position_sha256")
                    != initial_position_hash(position)
                ):
                    errors.append(f"chain {index}: initial position/hash mismatch")
                if chain.get("chain_rescue_events") != 0:
                    errors.append(f"chain {index}: chain rescue event present")
                work = chain.get("work", {})
                for phase in ("warmup", "retained", "total"):
                    validate_work(work.get(phase), f"chain {index}/{phase}", errors)
                for key in (
                    "adaptation_target_calls",
                    "target_calls_including_adaptation",
                ):
                    if not isinstance(work.get(key), int) or work[key] < 0:
                        errors.append(f"chain {index}: invalid {key}")
                mass = chain.get("final_mass_diagonal")
                if not isinstance(mass, list) or len(mass) != dimension:
                    errors.append(f"chain {index}: final metric shape mismatch")
                if chain.get("final_max_error") != (
                    1.0 if row["arm"] == "fixed1" else 2.0
                ):
                    errors.append(f"chain {index}: final max_error mismatch")
        required_hashes = (
            "retained_draw_bytes_sha256",
            "retained_diagnostics_sha256_by_chain",
            "final_tuning_sha256_by_chain",
            "final_metric_sha256_by_chain",
            "initial_position_sha256_by_chain",
        )
        for name in required_hashes:
            value = raw.get(name)
            if name.endswith("_by_chain"):
                if not isinstance(value, list) or len(value) != 4:
                    errors.append(f"{name} shape")
            elif not isinstance(value, str) or len(value) != 64:
                errors.append(f"{name} shape")
        phase = raw.get("phase_target_callbacks")
        if not isinstance(phase, dict) or set(phase) != {
            "warmup_kernel",
            "retained_kernel",
            "adaptation",
            "total_started",
        }:
            errors.append("phase target callback fields mismatch")
        elif not all(isinstance(value, int) and value >= 0 for value in phase.values()):
            errors.append("phase target callbacks invalid")
        if (
            draws is not None
            and draws.shape == (4, retained, dimension)
            and raw.get("retained_draw_bytes_sha256")
            != rust_f64_hash(
                b"delta2_sidechecks_v1.retained_draws.v1",
                draws.shape,
                draws,
            )
        ):
            errors.append("retained draw-byte hash mismatch")
        if isinstance(chains, list) and len(chains) == 4:
            initial_hashes = [
                chain.get("initial_position_sha256") for chain in chains
            ]
            if raw.get("initial_position_sha256_by_chain") != initial_hashes:
                errors.append("top-level initial-position hashes mismatch")
            metric_hashes = []
            for chain in chains:
                mass = chain.get("final_mass_diagonal")
                if isinstance(mass, list):
                    metric_hashes.append(
                        rust_f64_hash(
                            b"delta2_sidechecks_v1.final_metric.v1",
                            (len(mass),),
                            np.asarray(mass, dtype=np.float64),
                        )
                    )
            if raw.get("final_metric_sha256_by_chain") != metric_hashes:
                errors.append("final metric hashes mismatch")
            expected_phase = {
                "warmup_kernel": sum(
                    chain["work"]["warmup"]["target_calls_total"]
                    for chain in chains
                ),
                "retained_kernel": sum(
                    chain["work"]["retained"]["target_calls_total"]
                    for chain in chains
                ),
                "adaptation": sum(
                    chain["work"]["adaptation_target_calls"] for chain in chains
                ),
                "total_started": sum(
                    chain["work"]["target_calls_including_adaptation"]
                    for chain in chains
                ),
            }
            if phase != expected_phase:
                errors.append("phase callback counts disagree with chain telemetry")
        if row["target"] == "eight_schools_strict":
            if raw.get("callback_cap") != 10_000_000:
                errors.append("strict-track callback cap mismatch")
            if not isinstance(raw.get("constructor_admission_bound"), int):
                errors.append("strict-track admission bound missing")
            if not isinstance(phase, dict) or raw.get("target_atomic_calls") != phase.get(
                "total_started"
            ):
                errors.append("strict-track target atomic calls mismatch")
    else:
        if not all(
            isinstance(raw.get(name), str) and raw[name]
            for name in ("error_stage", "error_class", "error_message")
        ):
            errors.append("sampler_error lacks stage/class/message")
        if not isinstance(raw.get("known_counters"), dict):
            errors.append("sampler_error lacks known counters")
    return not errors, errors, raw, draws


def config_validate(
    row: dict[str, Any],
    raw: dict[str, Any] | None,
    provenance: dict[str, Any],
) -> tuple[bool, list[str]]:
    if raw is None:
        return False, ["no schema-valid raw for configuration authentication"]
    errors: list[str] = []
    key = f"{row['target']}/{row['arm']}"
    registered = provenance["effective_configs"][key]
    if (
        raw.get("effective_config") != registered["config"]
        or raw.get("effective_config_sha256") != registered["sha256"]
    ):
        errors.append("effective config/hash mismatch")
    if raw.get("harness_source_commit") != provenance["harness_source"]["commit"]:
        errors.append("harness source commit mismatch")
    if raw.get("harness_source_tree") != provenance["harness_source"]["tree"]:
        errors.append("harness source tree mismatch")
    if raw.get("binary") != {
        "bytes": provenance["binary"]["bytes"],
        "sha256": provenance["binary"]["sha256"],
    }:
        errors.append("binary record mismatch")
    if raw.get("algorithm_revision") != provenance["algorithm_revision"]:
        errors.append("algorithm revision mismatch")
    if raw.get("provenance_record_sha256") != runner.sha256(runner.PROVENANCE):
        errors.append("provenance record hash mismatch")
    expected_bindings = {
        "baseline": provenance["baseline"],
        "normalized_source_files": provenance["normalized_source_files"],
        "harness_source": provenance["harness_source"],
        "binary": provenance["binary"],
        "cargo_lock": provenance["cargo_lock"],
        "manifest_sha256": provenance["manifest"]["sha256"],
    }
    if raw.get("provenance_bindings") != expected_bindings:
        errors.append("raw provenance bindings mismatch")
    kernel = raw.get("effective_config", {}).get("kernel", {})
    if kernel.get("max_error") != (1.0 if row["arm"] == "fixed1" else 2.0):
        errors.append("arm max_error mismatch")
    adaptation = raw.get("effective_config", {}).get("adaptation", {})
    if (
        adaptation.get("chain_rescue") is not None
        or adaptation.get("inherits_default_chain_rescue") is not False
    ):
        errors.append("no-rescue config mismatch")
    return not errors, errors


def strip_arm_difference(config: dict[str, Any]) -> dict[str, Any]:
    value = json.loads(json.dumps(config))
    value["arm"] = None
    value["kernel"]["max_error"] = None
    return value


def identity_signature(raw: dict[str, Any]) -> str:
    signature = {
        "retained_draw_bytes_sha256": raw["retained_draw_bytes_sha256"],
        "phase_target_callbacks": raw["phase_target_callbacks"],
        "final_tuning_sha256_by_chain": raw["final_tuning_sha256_by_chain"],
        "final_metric_sha256_by_chain": raw["final_metric_sha256_by_chain"],
        "retained_diagnostics_sha256_by_chain": raw[
            "retained_diagnostics_sha256_by_chain"
        ],
        "retained_work_by_chain": [
            chain["work"]["retained"] for chain in raw["chains_data"]
        ],
    }
    return hashlib.sha256(
        json.dumps(signature, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def funnel_metrics(draws: np.ndarray) -> dict[str, Any]:
    omega = draws[:, :, 0]
    below5 = (omega < -5.0).astype(np.float64)
    below6 = (omega < -6.0).astype(np.float64)
    p5 = float(np.mean(below5))
    p6 = float(np.mean(below6))
    return {
        "p_omega_lt_minus5": p5,
        "p_omega_lt_minus5_mcse": float(az.mcse(below5, method="mean")),
        "p_omega_lt_minus6": p6,
        "p_omega_lt_minus6_mcse": float(az.mcse(below6, method="mean")),
        "omega_mean": float(np.mean(omega)),
        "omega_variance": float(np.var(omega, ddof=1)),
        "omega_rank_rhat": float(az.rhat(omega, method="rank")),
        "omega_bulk_ess": float(az.ess(omega, method="bulk")),
        "omega_tail_ess": tail_ess(omega),
    }


def functional_arrays(draws: np.ndarray) -> dict[str, np.ndarray]:
    mu = draws[..., 0]
    tau = np.exp(draws[..., 1])
    theta = mu[..., None] + tau[..., None] * draws[..., 2:]
    return {
        "mu": mu,
        "tau": tau,
        "mean_theta": np.mean(theta, axis=-1),
        "sd_theta": np.std(theta, axis=-1, ddof=1),
        "theta_1": theta[..., 0],
        "theta_8": theta[..., 7],
    }


def eight_metrics(draws: np.ndarray, callbacks: int) -> dict[str, Any]:
    values = functional_arrays(draws)
    metrics = {name: scalar_stats(value) for name, value in values.items()}
    for item in metrics.values():
        item["bulk_ess_per_callback"] = item["bulk_ess"] / callbacks
        item["tail_ess_per_callback"] = item["tail_ess"] / callbacks
    return {
        "functionals": metrics,
        "minimum_bulk_ess_per_callback": min(
            item["bulk_ess_per_callback"] for item in metrics.values()
        ),
        "minimum_tail_ess_per_callback": min(
            item["tail_ess_per_callback"] for item in metrics.values()
        ),
    }


def gaussian_metrics(draws: np.ndarray, retained_calls: int) -> dict[str, Any]:
    coordinates = []
    for coordinate in range(draws.shape[-1]):
        stats = scalar_stats(draws[:, :, coordinate])
        coordinates.append(stats)
    mean_bulk = float(np.mean([item["bulk_ess"] for item in coordinates]))
    mean_tail = float(np.mean([item["tail_ess"] for item in coordinates]))
    return {
        "coordinates": coordinates,
        "mean_coordinate_bulk_ess": mean_bulk,
        "mean_coordinate_tail_ess": mean_tail,
        "mean_bulk_ess_per_retained_call": mean_bulk / retained_calls,
        "mean_tail_ess_per_retained_call": mean_tail / retained_calls,
    }


def load_cells(
    entries: list[dict[str, Any]], provenance: dict[str, Any]
) -> tuple[dict[tuple[Any, ...], dict[str, Any]], list[str]]:
    cells: dict[tuple[Any, ...], dict[str, Any]] = {}
    global_errors: list[str] = []
    expected_names = {f"{runner.cell_id(row)}.json" for row in entries}
    for directory in (runner.LAUNCHES, runner.PROCESSES, runner.RAW):
        actual = {path.name for path in directory.glob("*.json")} if directory.exists() else set()
        if actual != expected_names:
            global_errors.append(
                f"{directory.name} files differ: missing={sorted(expected_names-actual)}, "
                f"extra={sorted(actual-expected_names)}"
            )
    for row in entries:
        identifier = runner.cell_id(row)
        process_valid, process_errors, marker, process = process_record_valid(
            row,
            runner.LAUNCHES / f"{identifier}.json",
            runner.PROCESSES / f"{identifier}.json",
            runner.RAW / f"{identifier}.json",
        )
        schema_valid, schema_errors, raw, draws = schema_validate(
            row, runner.RAW / f"{identifier}.json"
        )
        config_valid, config_errors = config_validate(row, raw, provenance)
        variant = raw.get("variant") if raw else None
        finite_draws = bool(draws is not None and np.isfinite(draws).all())
        scientific_finite = finite_draws
        metrics: dict[str, Any] | None = None
        if (
            process_valid
            and schema_valid
            and config_valid
            and variant == "samples_complete"
            and draws is not None
        ):
            try:
                target = row["target"]
                if target == "funnel":
                    metrics = funnel_metrics(draws)
                elif target == "eight_schools_strict":
                    callbacks = int(raw["phase_target_callbacks"]["total_started"])
                    metrics = eight_metrics(draws, callbacks)
                else:
                    retained_calls = int(
                        raw["phase_target_callbacks"]["retained_kernel"]
                    )
                    metrics = gaussian_metrics(draws, retained_calls)
                scientific_finite = finite_draws and all_finite(metrics)
            except Exception as error:
                scientific_finite = False
                schema_errors.append(f"required estimator failure: {type(error).__name__}: {error}")
        key = (
            row["target"],
            row["seed"],
            row["zero_based_repetition"],
            row["arm"],
        )
        cells[key] = {
            "manifest": row,
            "cell_id": identifier,
            "process_valid": process_valid,
            "process_errors": process_errors,
            "schema_valid": schema_valid,
            "schema_errors": schema_errors,
            "configuration_authenticated": config_valid,
            "configuration_errors": config_errors,
            "variant": variant,
            "sampler_error": variant == "sampler_error",
            "finite_draws": finite_draws,
            "scientific_finite": scientific_finite,
            "raw": raw,
            "draws": draws,
            "metrics": metrics,
            "process": process,
            "marker": marker,
        }
    return cells, global_errors


def all_finite(value: Any) -> bool:
    if isinstance(value, dict):
        return all(all_finite(item) for item in value.values())
    if isinstance(value, list):
        return all(all_finite(item) for item in value)
    if isinstance(value, float):
        return math.isfinite(value)
    return True


def authenticate_pairing(cells: dict[tuple[Any, ...], dict[str, Any]]) -> list[str]:
    errors: list[str] = []
    for target in ("funnel", "gaussian100"):
        for seed in range(93101, 93113):
            pair = [cells[(target, seed, 0, arm)] for arm in ("fixed1", "fixed2")]
            hashes = [
                cell["raw"].get("initial_position_sha256_by_chain")
                if cell["raw"]
                else None
                for cell in pair
            ]
            if hashes[0] is None or hashes[0] != hashes[1]:
                errors.append(f"{target}/{seed}: paired initial-position hashes differ")
    for seed in range(93101, 93107):
        for arm in ("fixed1", "fixed2"):
            hashes = [
                cells[("eight_schools_strict", seed, repetition, arm)]["raw"].get(
                    "initial_position_sha256_by_chain"
                )
                if cells[("eight_schools_strict", seed, repetition, arm)]["raw"]
                else None
                for repetition in range(3)
            ]
            if hashes[0] is None or len({json.dumps(value) for value in hashes}) != 1:
                errors.append(
                    f"eight_schools_strict/{seed}/{arm}: repetition starts differ"
                )
        left = cells[("eight_schools_strict", seed, 0, "fixed1")]["raw"]
        right = cells[("eight_schools_strict", seed, 0, "fixed2")]["raw"]
        if (
            left is None
            or right is None
            or left.get("initial_position_sha256_by_chain")
            != right.get("initial_position_sha256_by_chain")
        ):
            errors.append(f"eight_schools_strict/{seed}: paired starts differ")
    return errors


def identity_assessment(
    cells: dict[tuple[Any, ...], dict[str, Any]]
) -> tuple[dict[str, Any], list[str]]:
    results: dict[str, Any] = {}
    errors: list[str] = []
    for seed in range(93101, 93107):
        for arm in ("fixed1", "fixed2"):
            group = [
                cells[("eight_schools_strict", seed, repetition, arm)]
                for repetition in range(3)
            ]
            signatures = []
            for cell in group:
                raw = cell["raw"]
                if (
                    not cell["process_valid"]
                    or not cell["schema_valid"]
                    or not cell["configuration_authenticated"]
                    or raw is None
                    or raw.get("variant") != "samples_complete"
                ):
                    signatures.append(None)
                else:
                    signatures.append(identity_signature(raw))
            identical = (
                signatures[0] is not None
                and len(set(signatures)) == 1
                and len(signatures) == 3
            )
            key = f"{seed}/{arm}"
            results[key] = {"signatures": signatures, "bit_identical": identical}
            if not identical:
                errors.append(f"{key}: three repetitions are not bit-identical")
    return results, errors


def valid_complete(cell: dict[str, Any]) -> bool:
    return (
        cell["process_valid"]
        and cell["schema_valid"]
        and cell["configuration_authenticated"]
        and cell["variant"] == "samples_complete"
        and cell["finite_draws"]
        and cell["scientific_finite"]
        and cell["metrics"] is not None
    )


def funnel_analysis(cells: dict[tuple[Any, ...], dict[str, Any]]) -> dict[str, Any]:
    by_arm: dict[str, Any] = {}
    for arm in ("fixed1", "fixed2"):
        arm_cells = [cells[("funnel", seed, 0, arm)] for seed in range(93101, 93113)]
        complete = all(valid_complete(cell) for cell in arm_cells)
        pooled_draws = (
            np.concatenate([cell["draws"] for cell in arm_cells], axis=0)
            if complete
            else None
        )
        pooled = funnel_metrics(pooled_draws) if pooled_draws is not None else None
        if pooled is not None:
            omega = pooled_draws[:, :, 0]
            for threshold, key, exact in (
                (-5.0, "minus5", EXACT_P5),
                (-6.0, "minus6", EXACT_P6),
            ):
                batches = (omega < threshold).reshape(48, 40, 500).mean(axis=2).reshape(-1)
                batch_mcse = float(np.std(batches, ddof=1) / math.sqrt(1920))
                estimate = float(np.mean(omega < threshold))
                pooled[f"p_omega_lt_{key}_batch_mcse"] = batch_mcse
                pooled[f"p_omega_lt_{key}_batch_z"] = (
                    (estimate - exact) / batch_mcse if batch_mcse > 0 else math.nan
                )
                pooled[f"p_omega_lt_{key}_arviz_z"] = (
                    (estimate - exact) / pooled[f"p_omega_lt_{key}_mcse"]
                    if pooled[f"p_omega_lt_{key}_mcse"] > 0
                    else math.nan
                )
        healthy = []
        gross_safe = []
        per_seed = {}
        totals = Counter()
        hist: list[int] = []
        for seed, cell in zip(range(93101, 93113), arm_cells):
            raw, metrics = cell["raw"], cell["metrics"]
            telem = telemetry(raw) if valid_complete(cell) else None
            if telem:
                for field in (
                    "divergences",
                    "invalid_evaluation_stops",
                    "refinement_exhaustion_stops",
                    "maximum_depth_stops",
                    "reverse_coarser_stops",
                    "reverse_coarser_rejections",
                    "target_calls_total",
                ):
                    totals[field] += telem["retained"][field]
                values = telem["retained"]["refinement_level_built"]
                hist += [0] * max(0, len(values) - len(hist))
                for index, value in enumerate(values):
                    hist[index] += value
            is_healthy = bool(
                valid_complete(cell)
                and metrics["omega_rank_rhat"] <= 1.01
                and metrics["omega_bulk_ess"] >= 400
                and metrics["omega_tail_ess"] >= 400
                and telem["retained"]["divergences"] == 0
                and telem["retained"]["invalid_evaluation_stops"] == 0
                and telem["retained"]["refinement_exhaustion_stops"] == 0
            )
            is_gross_safe = bool(
                valid_complete(cell)
                and metrics["omega_rank_rhat"] <= 1.05
                and abs(metrics["p_omega_lt_minus5"] - EXACT_P5) <= 0.025
                and abs(metrics["p_omega_lt_minus6"] - EXACT_P6) <= 0.015
                and 5 <= metrics["omega_variance"] <= 13
                and telem["retained"]["divergences"] == 0
            )
            if is_healthy:
                healthy.append(seed)
            if is_gross_safe:
                gross_safe.append(seed)
            per_seed[str(seed)] = {
                "metrics": metrics,
                "telemetry": telem,
                "final": final_records(raw) if valid_complete(cell) else None,
                "healthy": is_healthy,
                "gross_safe": is_gross_safe,
                "sampler_error": cell["sampler_error"],
            }
        by_arm[arm] = {
            "complete": complete,
            "pooled": pooled,
            "per_seed": per_seed,
            "healthy_seeds": healthy,
            "healthy_count": len(healthy),
            "gross_safe_seeds": gross_safe,
            "retained_totals": dict(totals),
            "retained_refinement_level_built": hist,
        }
    f1 = all(
        cell["process_valid"]
        and cell["schema_valid"]
        and cell["configuration_authenticated"]
        and valid_complete(cell)
        for key, cell in cells.items()
        if key[0] == "funnel"
    )
    fixed1 = by_arm["fixed1"]["pooled"]
    fixed2 = by_arm["fixed2"]["pooled"]
    arm_accuracy = {}
    if fixed1 and fixed2:
        for arm, pooled in (("fixed1", fixed1), ("fixed2", fixed2)):
            arm_accuracy[arm] = {
                "p5": abs(pooled["p_omega_lt_minus5"] - EXACT_P5) <= 0.006,
                "p6": abs(pooled["p_omega_lt_minus6"] - EXACT_P6) <= 0.004,
                "variance": abs(pooled["omega_variance"] - EXACT_VARIANCE) <= 1.0,
            }
        agreement = {
            "p5": abs(fixed2["p_omega_lt_minus5"] - fixed1["p_omega_lt_minus5"])
            <= 0.004,
            "p6": abs(fixed2["p_omega_lt_minus6"] - fixed1["p_omega_lt_minus6"])
            <= 0.003,
            "variance": abs(fixed2["omega_variance"] - fixed1["omega_variance"])
            <= 0.75,
        }
    else:
        arm_accuracy = {
            arm: {"p5": False, "p6": False, "variance": False}
            for arm in ("fixed1", "fixed2")
        }
        agreement = {"p5": False, "p6": False, "variance": False}
    f2 = all(all(values.values()) for values in arm_accuracy.values()) and all(
        agreement.values()
    )
    f3 = len(by_arm["fixed2"]["gross_safe_seeds"]) == 12
    f4 = (
        by_arm["fixed2"]["healthy_count"] >= 9
        and by_arm["fixed2"]["healthy_count"] >= by_arm["fixed1"]["healthy_count"]
    )
    count_fields = (
        "divergences",
        "invalid_evaluation_stops",
        "refinement_exhaustion_stops",
    )
    counter_nonregression = {
        field: by_arm["fixed2"]["retained_totals"].get(field, 0)
        <= by_arm["fixed1"]["retained_totals"].get(field, 0)
        for field in count_fields
    }
    f5 = all(counter_nonregression.values())
    paired_mechanisms = {}
    paired_scientific = {}
    for seed in range(93101, 93113):
        a = by_arm["fixed1"]["per_seed"][str(seed)]["telemetry"]
        b = by_arm["fixed2"]["per_seed"][str(seed)]["telemetry"]
        ma = by_arm["fixed1"]["per_seed"][str(seed)]["metrics"]
        mb = by_arm["fixed2"]["per_seed"][str(seed)]["metrics"]
        if ma and mb:
            paired_scientific[str(seed)] = {
                field: {
                    "fixed1": ma[field],
                    "fixed2": mb[field],
                    "difference_fixed2_minus_fixed1": mb[field] - ma[field],
                    "ratio_fixed2_fixed1": descriptive_ratio(mb[field], ma[field]),
                }
                for field in (
                    "p_omega_lt_minus5",
                    "p_omega_lt_minus6",
                    "omega_variance",
                    "omega_bulk_ess",
                    "omega_tail_ess",
                )
            }
        if a and b:
            paired_mechanisms[str(seed)] = {
                "counts": {
                    field: {
                        "fixed1": a["retained"][field],
                        "fixed2": b["retained"][field],
                        "ratio_fixed2_fixed1": descriptive_ratio(
                            b["retained"][field], a["retained"][field]
                        ),
                    }
                    for field in (
                        "reverse_coarser_stops",
                        "reverse_coarser_rejections",
                        "target_calls_total",
                    )
                },
                "refinement_level_built": [
                    {
                        "level": level,
                        "fixed1": (
                            a["retained"]["refinement_level_built"][level]
                            if level
                            < len(a["retained"]["refinement_level_built"])
                            else 0
                        ),
                        "fixed2": (
                            b["retained"]["refinement_level_built"][level]
                            if level
                            < len(b["retained"]["refinement_level_built"])
                            else 0
                        ),
                        "ratio_fixed2_fixed1": descriptive_ratio(
                            (
                                b["retained"]["refinement_level_built"][level]
                                if level
                                < len(b["retained"]["refinement_level_built"])
                                else 0
                            ),
                            (
                                a["retained"]["refinement_level_built"][level]
                                if level
                                < len(a["retained"]["refinement_level_built"])
                                else 0
                            ),
                        ),
                    }
                    for level in range(
                        max(
                            len(a["retained"]["refinement_level_built"]),
                            len(b["retained"]["refinement_level_built"]),
                        )
                    )
                ],
            }
    pooled_comparison = None
    if fixed1 and fixed2:
        pooled_comparison = {
            field: {
                "fixed1": fixed1[field],
                "fixed2": fixed2[field],
                "difference_fixed2_minus_fixed1": fixed2[field] - fixed1[field],
                "ratio_fixed2_fixed1": descriptive_ratio(fixed2[field], fixed1[field]),
            }
            for field in (
                "p_omega_lt_minus5",
                "p_omega_lt_minus6",
                "omega_variance",
                "omega_bulk_ess",
                "omega_tail_ess",
            )
        }
    return {
        "arms": by_arm,
        "pool_layout": {"chains": 48, "draws_per_chain": 20_000},
        "pooled_comparison": pooled_comparison,
        "paired_scientific": paired_scientific,
        "paired_mechanisms": paired_mechanisms,
        "F1": {"passed": f1},
        "F2": {
            "passed": f2,
            "arm_accuracy": arm_accuracy,
            "agreement": agreement,
        },
        "F3": {"passed": f3},
        "F4": {"passed": f4},
        "F5": {"passed": f5, "counter_nonregression": counter_nonregression},
    }


def eight_analysis(
    cells: dict[tuple[Any, ...], dict[str, Any]],
    identity: dict[str, Any],
) -> dict[str, Any]:
    rep0: dict[str, dict[int, dict[str, Any]]] = {
        arm: {
            seed: cells[("eight_schools_strict", seed, 0, arm)]
            for seed in range(93101, 93107)
        }
        for arm in ("fixed1", "fixed2")
    }
    all_valid = all(
        cell["process_valid"] and cell["schema_valid"] and cell["configuration_authenticated"]
        for key, cell in cells.items()
        if key[0] == "eight_schools_strict"
    )
    all_identical = all(value["bit_identical"] for value in identity.values())
    e1 = all_valid and all_identical
    pooled: dict[str, Any] = {}
    for arm in ("fixed1", "fixed2"):
        complete = all(valid_complete(cell) for cell in rep0[arm].values()) and all_identical
        if complete:
            draws = np.concatenate(
                [rep0[arm][seed]["draws"] for seed in range(93101, 93107)], axis=0
            )
            pooled[arm] = {
                name: scalar_stats(values)
                for name, values in functional_arrays(draws).items()
            }
        else:
            pooled[arm] = None
    e2_functionals = {}
    if all(pooled.values()):
        for name in FUNCTIONALS:
            a, b = pooled["fixed1"][name], pooled["fixed2"][name]
            s_pool = math.sqrt((a["sd"] ** 2 + b["sd"] ** 2) / 2)
            u_combined = math.sqrt(a["mcse_mean"] ** 2 + b["mcse_mean"] ** 2)
            mean_lhs = abs(b["mean"] - a["mean"]) + 2 * u_combined
            mean_rhs = 0.10 * s_pool
            sd_lhs = abs(b["sd"] - a["sd"])
            sd_rhs = 0.15 * s_pool
            finite = all(
                math.isfinite(value)
                for value in (s_pool, u_combined, mean_lhs, mean_rhs, sd_lhs, sd_rhs)
            ) and s_pool > 0
            e2_functionals[name] = {
                "fixed1": a,
                "fixed2": b,
                "s_pool": s_pool,
                "u_combined": u_combined,
                "mean_lhs": mean_lhs,
                "mean_bound": mean_rhs,
                "sd_difference": sd_lhs,
                "sd_bound": sd_rhs,
                "mean_passed": finite and mean_lhs <= mean_rhs,
                "sd_passed": finite and sd_lhs <= sd_rhs,
                "passed": finite and mean_lhs <= mean_rhs and sd_lhs <= sd_rhs,
            }
    e2 = len(e2_functionals) == 6 and all(
        value["passed"] for value in e2_functionals.values()
    )
    per_seed: dict[str, dict[str, Any]] = {}
    ratios = []
    tail_ratios = []
    healthy: dict[str, list[int]] = {"fixed1": [], "fixed2": []}
    for seed in range(93101, 93107):
        per_seed[str(seed)] = {}
        for arm in ("fixed1", "fixed2"):
            cell = rep0[arm][seed]
            raw, metrics = cell["raw"], cell["metrics"]
            telem = telemetry(raw) if valid_complete(cell) else None
            total_callbacks = (
                int(raw["phase_target_callbacks"]["total_started"])
                if valid_complete(cell)
                else 0
            )
            score = (
                metrics["minimum_bulk_ess_per_callback"]
                if metrics is not None
                else math.nan
            )
            tail_score = (
                metrics["minimum_tail_ess_per_callback"]
                if metrics is not None
                else math.nan
            )
            functional_health = bool(
                metrics
                and all(
                    item["bulk_ess"] >= 400
                    and item["tail_ess"] >= 400
                    and item["rank_rhat"] <= 1.01
                    for item in metrics["functionals"].values()
                )
            )
            is_healthy = bool(
                valid_complete(cell)
                and functional_health
                and telem["retained"]["divergences"] <= 40
                and telem["retained"]["maximum_depth_stops"] <= 40
                and telem["retained"]["invalid_evaluation_stops"] == 0
                and telem["retained"]["refinement_exhaustion_stops"] == 0
            )
            if is_healthy:
                healthy[arm].append(seed)
            per_seed[str(seed)][arm] = {
                "metrics": metrics,
                "telemetry": telem,
                "final": final_records(raw) if valid_complete(cell) else None,
                "total_callbacks_started": total_callbacks,
                "minimum_bulk_ess_per_callback": score,
                "minimum_tail_ess_per_callback": tail_score,
                "healthy": is_healthy,
            }
        left = per_seed[str(seed)]["fixed1"]
        right = per_seed[str(seed)]["fixed2"]
        ratios.append(
            right["minimum_bulk_ess_per_callback"]
            / left["minimum_bulk_ess_per_callback"]
            if finite_positive(right["minimum_bulk_ess_per_callback"])
            and finite_positive(left["minimum_bulk_ess_per_callback"])
            else math.nan
        )
        tail_ratios.append(
            right["minimum_tail_ess_per_callback"]
            / left["minimum_tail_ess_per_callback"]
            if finite_positive(right["minimum_tail_ess_per_callback"])
            and finite_positive(left["minimum_tail_ess_per_callback"])
            else math.nan
        )
    e3_ratio = geometric_mean(ratios)
    e3 = finite_positive(e3_ratio) and e3_ratio >= 0.90
    no_healthy_regression = all(
        seed in healthy["fixed2"] for seed in healthy["fixed1"]
    )
    introduced: list[str] = []
    for seed in range(93101, 93107):
        for repetition in range(3):
            fixed1 = cells[("eight_schools_strict", seed, repetition, "fixed1")]
            fixed2 = cells[("eight_schools_strict", seed, repetition, "fixed2")]
            for label, predicate in (
                ("process", lambda cell: not cell["process_valid"]),
                ("sampler", lambda cell: cell["sampler_error"]),
                ("nonfinite", lambda cell: not cell["scientific_finite"]),
            ):
                if not predicate(fixed1) and predicate(fixed2):
                    introduced.append(f"{seed}/r{repetition}/{label}")
        fixed1 = rep0["fixed1"][seed]
        fixed2 = rep0["fixed2"][seed]
        if valid_complete(fixed1) and valid_complete(fixed2):
            ta, tb = telemetry(fixed1["raw"]), telemetry(fixed2["raw"])
            for label, field in (
                ("divergence", "divergences"),
                ("invalid_stop", "invalid_evaluation_stops"),
                ("refinement_exhaustion", "refinement_exhaustion_stops"),
            ):
                if ta["retained"][field] == 0 and tb["retained"][field] > 0:
                    introduced.append(f"{seed}/{label}")
    e4 = (
        len(healthy["fixed2"]) >= 5
        and len(healthy["fixed2"]) >= len(healthy["fixed1"])
        and no_healthy_regression
        and not introduced
    )
    timing_medians = {
        f"{seed}/{arm}": median(
            cells[("eight_schools_strict", seed, repetition, arm)]["raw"][
                "wall_seconds"
            ]
            for repetition in range(3)
            if cells[("eight_schools_strict", seed, repetition, arm)]["raw"]
        )
        for seed in range(93101, 93107)
        for arm in ("fixed1", "fixed2")
    }
    return {
        "identity": identity,
        "pool_layout": {
            "chains": 24,
            "draws_per_chain": 1_000,
            "repetition": 0,
        },
        "pooled": pooled,
        "E2_functionals": e2_functionals,
        "per_seed": per_seed,
        "paired_bulk_score_ratios": ratios,
        "paired_tail_score_ratios": tail_ratios,
        "geomean_bulk_score_ratio": e3_ratio,
        "geomean_tail_score_ratio": geometric_mean(tail_ratios),
        "healthy_seeds": healthy,
        "introduced_failures": introduced,
        "timing_medians_seconds": timing_medians,
        "E1": {"passed": e1},
        "E2": {"passed": e2},
        "E3": {"passed": e3},
        "E4": {"passed": e4},
    }


def gaussian_analysis(cells: dict[tuple[Any, ...], dict[str, Any]]) -> dict[str, Any]:
    by_arm: dict[str, Any] = {}
    for arm in ("fixed1", "fixed2"):
        arm_cells = [cells[("gaussian100", seed, 0, arm)] for seed in range(93101, 93113)]
        complete = all(valid_complete(cell) for cell in arm_cells)
        pooled = None
        if complete:
            draws = np.concatenate([cell["draws"] for cell in arm_cells], axis=0)
            pooled = gaussian_metrics(
                draws,
                sum(
                    int(cell["raw"]["phase_target_callbacks"]["retained_kernel"])
                    for cell in arm_cells
                ),
            )
        healthy = []
        per_seed = {}
        totals = Counter()
        scores = []
        tail_scores = []
        for seed, cell in zip(range(93101, 93113), arm_cells):
            metrics, raw = cell["metrics"], cell["raw"]
            telem = telemetry(raw) if valid_complete(cell) else None
            if telem:
                for field in (
                    "divergences",
                    "invalid_evaluation_stops",
                    "refinement_exhaustion_stops",
                ):
                    totals[field] += telem["retained"][field]
            is_healthy = bool(
                valid_complete(cell)
                and all(
                    item["bulk_ess"] >= 400
                    and item["tail_ess"] >= 400
                    and item["rank_rhat"] <= 1.01
                    for item in metrics["coordinates"]
                )
                and telem["retained"]["divergences"] == 0
                and telem["retained"]["invalid_evaluation_stops"] == 0
                and telem["retained"]["refinement_exhaustion_stops"] == 0
            )
            if is_healthy:
                healthy.append(seed)
            score = (
                metrics["mean_bulk_ess_per_retained_call"]
                if metrics
                else math.nan
            )
            tail_score = (
                metrics["mean_tail_ess_per_retained_call"]
                if metrics
                else math.nan
            )
            scores.append(score)
            tail_scores.append(tail_score)
            per_seed[str(seed)] = {
                "metrics": metrics,
                "telemetry": telem,
                "final": final_records(raw) if valid_complete(cell) else None,
                "healthy": is_healthy,
            }
        by_arm[arm] = {
            "complete": complete,
            "pooled": pooled,
            "per_seed": per_seed,
            "healthy_seeds": healthy,
            "healthy_count": len(healthy),
            "scores": scores,
            "tail_scores": tail_scores,
            "score_median": median(scores),
            "tail_score_median": median(tail_scores),
            "retained_counter_totals": dict(totals),
        }
    g1 = all(
        valid_complete(cell)
        for key, cell in cells.items()
        if key[0] == "gaussian100"
    )
    coordinate_gates = []
    if by_arm["fixed1"]["pooled"] and by_arm["fixed2"]["pooled"]:
        a = by_arm["fixed1"]["pooled"]["coordinates"]
        b = by_arm["fixed2"]["pooled"]["coordinates"]
        for coordinate, (left, right) in enumerate(zip(a, b)):
            coordinate_gates.append(
                {
                    "coordinate": coordinate,
                    "fixed1_mean": abs(left["mean"]) <= 0.08,
                    "fixed1_variance": 0.85 <= left["variance"] <= 1.15,
                    "fixed2_mean": abs(right["mean"]) <= 0.08,
                    "fixed2_variance": 0.85 <= right["variance"] <= 1.15,
                    "mean_agreement": abs(right["mean"] - left["mean"]) <= 0.08,
                    "variance_agreement": abs(right["variance"] - left["variance"])
                    <= 0.12,
                }
            )
    g2 = len(coordinate_gates) == 100 and all(
        all(value for key, value in row.items() if key != "coordinate")
        for row in coordinate_gates
    )
    median_ratio = (
        by_arm["fixed2"]["score_median"] / by_arm["fixed1"]["score_median"]
        if finite_positive(by_arm["fixed1"]["score_median"])
        and finite_positive(by_arm["fixed2"]["score_median"])
        else math.nan
    )
    paired_ratios = [
        b / a if finite_positive(a) and finite_positive(b) else math.nan
        for a, b in zip(by_arm["fixed1"]["scores"], by_arm["fixed2"]["scores"])
    ]
    paired_tail_ratios = [
        b / a if finite_positive(a) and finite_positive(b) else math.nan
        for a, b in zip(
            by_arm["fixed1"]["tail_scores"], by_arm["fixed2"]["tail_scores"]
        )
    ]
    g3 = finite_positive(median_ratio) and median_ratio >= 0.90 and all(
        finite_positive(value) for value in paired_ratios + paired_tail_ratios
    )
    no_healthy_regression = all(
        seed in by_arm["fixed2"]["healthy_seeds"]
        for seed in by_arm["fixed1"]["healthy_seeds"]
    )
    count_nonregression = {
        field: by_arm["fixed2"]["retained_counter_totals"].get(field, 0)
        <= by_arm["fixed1"]["retained_counter_totals"].get(field, 0)
        for field in (
            "divergences",
            "invalid_evaluation_stops",
            "refinement_exhaustion_stops",
        )
    }
    g4 = (
        by_arm["fixed2"]["healthy_count"] >= 11
        and by_arm["fixed2"]["healthy_count"] >= by_arm["fixed1"]["healthy_count"]
        and no_healthy_regression
        and all(count_nonregression.values())
    )
    return {
        "arms": by_arm,
        "pool_layout": {"chains": 48, "draws_per_chain": 1_000},
        "coordinate_gates": coordinate_gates,
        "fixed2_median_over_fixed1_median_bulk_score": median_ratio,
        "median_paired_bulk_score_ratio": median(paired_ratios),
        "paired_bulk_score_ratios": paired_ratios,
        "median_paired_tail_score_ratio": median(paired_tail_ratios),
        "paired_tail_score_ratios": paired_tail_ratios,
        "count_nonregression": count_nonregression,
        "G1": {"passed": g1},
        "G2": {"passed": g2},
        "G3": {"passed": g3},
        "G4": {"passed": g4},
    }


def gate_rows(
    funnel: dict[str, Any], eight: dict[str, Any], gaussian: dict[str, Any]
) -> list[dict[str, Any]]:
    descriptions = {
        "F1": "24 process/schema/finite/config-complete funnel cells",
        "F2": "pooled funnel accuracy and arm agreement",
        "F3": "all 12 fixed2 funnel seeds gross-safe",
        "F4": "fixed2 funnel health count >=9 and >=fixed1",
        "F5": "funnel retained failure-counter nonregression",
        "E1": "36 valid/authenticated cells and 3-repeat byte identity",
        "E2": "amended conservative six-functional equivalence",
        "E3": "geomean min-bulk-ESS/callback ratio >=0.90",
        "E4": "strict-track no-new-failure and health nonregression",
        "G1": "24 process/schema/finite/config-complete Gaussian cells",
        "G2": "100-coordinate pooled accuracy and arm agreement",
        "G3": "fixed2/fixed1 median ESS/retained-call ratio >=0.90",
        "G4": "Gaussian health/count nonregression",
    }
    rows = []
    for source, names in (
        (funnel, ("F1", "F2", "F3", "F4", "F5")),
        (eight, ("E1", "E2", "E3", "E4")),
        (gaussian, ("G1", "G2", "G3", "G4")),
    ):
        for name in names:
            rows.append(
                {
                    "gate": name,
                    "passed": bool(source[name]["passed"]),
                    "description": descriptions[name],
                }
            )
    return rows


def decision(
    rows: list[dict[str, Any]],
    validity_errors: list[str],
    funnel: dict[str, Any],
    eight: dict[str, Any],
    gaussian: dict[str, Any],
) -> tuple[str, list[str]]:
    failed = [row["gate"] for row in rows if not row["passed"]]
    if validity_errors or any(name in failed for name in ("F1", "E1", "G1")):
        return "INCONCLUSIVE_NOT_QUALIFIED", failed
    candidate_or_agreement = []
    f2 = funnel["F2"]
    if not all(f2["arm_accuracy"]["fixed2"].values()) or not all(
        f2["agreement"].values()
    ):
        candidate_or_agreement.append("F2")
    for gate in ("F3", "F4", "F5"):
        if not funnel[gate]["passed"]:
            candidate_or_agreement.append(gate)
    for gate in ("E2", "E3", "E4"):
        if not eight[gate]["passed"]:
            candidate_or_agreement.append(gate)
    if gaussian["coordinate_gates"]:
        if any(
            not row["fixed2_mean"]
            or not row["fixed2_variance"]
            or not row["mean_agreement"]
            or not row["variance_agreement"]
            for row in gaussian["coordinate_gates"]
        ):
            candidate_or_agreement.append("G2")
    elif not gaussian["G2"]["passed"]:
        candidate_or_agreement.append("G2")
    for gate in ("G3", "G4"):
        if not gaussian[gate]["passed"]:
            candidate_or_agreement.append(gate)
    if candidate_or_agreement:
        return "FIXED2_NOT_QUALIFIED_FOR_ADAPTIVE_TO_2", failed
    if failed:
        return "INCONCLUSIVE_NOT_QUALIFIED", failed
    return "QUALIFIED_FOR_SEPARATE_ADAPTIVE_DELTA_STUDY", failed


def cell_public_record(cell: dict[str, Any]) -> dict[str, Any]:
    return {
        key: value
        for key, value in cell.items()
        if key not in {"raw", "draws", "marker", "process"}
    }


def markdown_gate_table(rows: list[dict[str, Any]], label: str) -> str:
    lines = [
        "| gate | result | frozen predicate |",
        "|---|---|---|",
        *[
            f"| {row['gate']} | {'PASS' if row['passed'] else 'FAIL'} | {row['description']} |"
            for row in rows
        ],
        "",
        f"Mechanical label: `{label}`",
        "",
    ]
    return "\n".join(lines)


def results_markdown(
    funnel: dict[str, Any],
    eight: dict[str, Any],
    gaussian: dict[str, Any],
    runtime: dict[str, Any],
) -> str:
    f1, f2 = funnel["arms"]["fixed1"]["pooled"], funnel["arms"]["fixed2"]["pooled"]
    lines = [
        "## Funnel pooled results",
        "",
        "| arm | P(omega<-5) | P(omega<-6) | Var(omega) | healthy |",
        "|---|---:|---:|---:|---:|",
    ]
    for arm, pooled in (("fixed1", f1), ("fixed2", f2)):
        lines.append(
            f"| {arm} | {pooled['p_omega_lt_minus5']:.6f} | "
            f"{pooled['p_omega_lt_minus6']:.6f} | {pooled['omega_variance']:.6f} | "
            f"{funnel['arms'][arm]['healthy_count']}/12 |"
        )
    lines += [
        "",
        "## Eight Schools",
        "",
        f"- Repeat identity: {all(v['bit_identical'] for v in eight['identity'].values())}.",
        f"- Geomean fixed2/fixed1 minimum bulk ESS/callback: {eight['geomean_bulk_score_ratio']:.6f}.",
        f"- Healthy seeds: fixed1 {len(eight['healthy_seeds']['fixed1'])}/6; fixed2 {len(eight['healthy_seeds']['fixed2'])}/6.",
        "",
        "## Gaussian",
        "",
        f"- Fixed2 median / fixed1 median mean-bulk-ESS per retained call: {gaussian['fixed2_median_over_fixed1_median_bulk_score']:.6f}.",
        f"- Median paired bulk work ratio: {gaussian['median_paired_bulk_score_ratio']:.6f}.",
        f"- Healthy seeds: fixed1 {gaussian['arms']['fixed1']['healthy_count']}/12; fixed2 {gaussian['arms']['fixed2']['healthy_count']}/12.",
        "",
        "## Runtime",
        "",
        f"- Sum of child durations: {runtime['sum_child_duration_seconds']:.3f} seconds.",
        f"- End-to-end marker span: {runtime['marker_span_seconds']:.3f} seconds.",
        "",
    ]
    return "\n".join(lines)


def analyze() -> dict[str, Any]:
    if az.__version__ != runner.EXPECTED_ARVIZ:
        raise RuntimeError(f"ArviZ {az.__version__} != {runner.EXPECTED_ARVIZ}")
    if any(path.exists() for path in (SUMMARY, GATE_TABLE, RESULTS_TABLE, VERDICT)):
        raise RuntimeError("analysis outputs already exist; evidence analysis is immutable")
    provenance = json.loads(runner.PROVENANCE.read_text(encoding="utf-8"))
    provenance_errors: list[str] = []
    try:
        runner.verify_static(require_provenance=False)
        if provenance["binary"]["sha256"] != runner.sha256(runner.BINARY):
            provenance_errors.append("binary hash mismatch")
        if provenance["cargo_lock"]["sha256"] != runner.sha256(HERE / "Cargo.lock"):
            provenance_errors.append("Cargo.lock hash mismatch")
        if provenance["conformance"] != runner.file_record(runner.CONFORMANCE):
            provenance_errors.append("conformance hash mismatch")
        tracked = subprocess_run_git_show_provenance()
        if tracked != runner.PROVENANCE.read_bytes():
            provenance_errors.append("committed PROVENANCE.json differs from working file")
        provenance_commit = runner.git(
            "log",
            "-1",
            "--format=%H",
            "--",
            runner.PROVENANCE.relative_to(runner.REPOSITORY).as_posix(),
        )
        if not provenance_commit:
            provenance_errors.append("no pre-evidence provenance commit")
        merge_base = runner.git(
            "merge-base", provenance["harness_source"]["commit"], provenance_commit
        )
        if merge_base != provenance["harness_source"]["commit"]:
            provenance_errors.append(
                "harness source commit is not an ancestor of provenance commit"
            )
        for target in ("funnel", "eight_schools_strict", "gaussian100"):
            fixed1 = provenance["effective_configs"][f"{target}/fixed1"]["config"]
            fixed2 = provenance["effective_configs"][f"{target}/fixed2"]["config"]
            if strip_arm_difference(fixed1) != strip_arm_difference(fixed2):
                provenance_errors.append(
                    f"{target}: registered arms differ outside max_error"
                )
    except Exception as error:
        provenance_errors.append(f"provenance verification error: {error}")
    entries = runner.parse_manifest()
    cells, global_errors = load_cells(entries, provenance)
    pairing_errors = authenticate_pairing(cells)
    identity, identity_errors = identity_assessment(cells)
    validity_errors = provenance_errors + global_errors + pairing_errors + identity_errors
    funnel = funnel_analysis(cells)
    eight = eight_analysis(cells, identity)
    gaussian = gaussian_analysis(cells)
    rows = gate_rows(funnel, eight, gaussian)
    label, failed = decision(rows, validity_errors, funnel, eight, gaussian)
    process_records = [
        cell["process"] for cell in cells.values() if isinstance(cell["process"], dict)
    ]
    durations = [
        float(record["duration_seconds"])
        for record in process_records
        if isinstance(record.get("duration_seconds"), (int, float))
    ]
    marker_times = sorted(
        marker["created_utc"]
        for marker in (cell["marker"] for cell in cells.values())
        if isinstance(marker, dict) and isinstance(marker.get("created_utc"), str)
    )
    marker_span = (
        (
            np.datetime64(marker_times[-1]) - np.datetime64(marker_times[0])
        ).astype("timedelta64[us]").astype(float)
        / 1_000_000
        if len(marker_times) == 84
        else math.nan
    )
    runtime = {
        "sum_child_duration_seconds": sum(durations),
        "median_child_duration_seconds": median(durations),
        "marker_span_seconds": float(marker_span),
        "by_target": {
            target: {
                "sum_seconds": sum(
                    float(cell["process"]["duration_seconds"])
                    for key, cell in cells.items()
                    if key[0] == target
                    and isinstance(cell["process"], dict)
                    and isinstance(cell["process"].get("duration_seconds"), (int, float))
                ),
                "median_seconds": median(
                    float(cell["process"]["duration_seconds"])
                    for key, cell in cells.items()
                    if key[0] == target
                    and isinstance(cell["process"], dict)
                    and isinstance(cell["process"].get("duration_seconds"), (int, float))
                ),
            }
            for target in runner.TIMEOUTS
        },
    }
    predictions = {
        "P1": bool(
            all(funnel["F2"]["arm_accuracy"]["fixed1"].values())
            and all(funnel["F2"]["arm_accuracy"]["fixed2"].values())
            and funnel["arms"]["fixed2"]["healthy_count"]
            >= funnel["arms"]["fixed1"]["healthy_count"]
            and sum(funnel["arms"]["fixed2"]["retained_refinement_level_built"][1:])
            < sum(funnel["arms"]["fixed1"]["retained_refinement_level_built"][1:])
            and (
                funnel["arms"]["fixed2"]["retained_totals"].get(
                    "reverse_coarser_rejections", 0
                )
                + funnel["arms"]["fixed2"]["retained_totals"].get(
                    "reverse_coarser_stops", 0
                )
                < funnel["arms"]["fixed1"]["retained_totals"].get(
                    "reverse_coarser_rejections", 0
                )
                + funnel["arms"]["fixed1"]["retained_totals"].get(
                    "reverse_coarser_stops", 0
                )
            )
        ),
        "P2": bool(eight["E1"]["passed"] and eight["E2"]["passed"] and eight["E3"]["passed"]),
        "P3": bool(
            gaussian["G2"]["passed"]
            and gaussian["G3"]["passed"]
            and gaussian["G4"]["passed"]
        ),
        "P4": label == "QUALIFIED_FOR_SEPARATE_ADAPTIVE_DELTA_STUDY",
    }
    summary = {
        "schema": "owalnuts-delta2-sidechecks-v1-summary",
        "schema_version": 1,
        "analysis_environment": {
            "python": sys.version,
            "arviz": az.__version__,
            "numpy": np.__version__,
        },
        "provenance_sha256": runner.sha256(runner.PROVENANCE),
        "manifest_sha256": runner.sha256(runner.MANIFEST),
        "planned_cells": 84,
        "process_records": len(process_records),
        "validity_errors": validity_errors,
        "all_validity_predicates_passed": not validity_errors,
        "gate_table": rows,
        "failed_gates": failed,
        "mechanical_label": label,
        "predictions_held": predictions,
        "runtime": runtime,
        "funnel": funnel,
        "eight_schools_strict": eight,
        "gaussian100": gaussian,
        "cells": {
            cell["cell_id"]: cell_public_record(cell)
            for cell in cells.values()
        },
        "scope": {
            "default_changed": False,
            "fixed2_selected_as_default": False,
            "adaptive_delta_implemented": False,
        },
    }
    safe_summary = json_safe(summary)
    for cell in cells.values():
        safe_cell = json_safe(cell_public_record(cell))
        runner.atomic_write_new(
            CELLS / f"{cell['cell_id']}.json",
            (
                json.dumps(
                    safe_cell, indent=2, sort_keys=True, allow_nan=False
                )
                + "\n"
            ).encode("utf-8"),
        )
    runner.atomic_write_new(
        SUMMARY,
        (
            json.dumps(
                safe_summary, indent=2, sort_keys=True, allow_nan=False
            )
            + "\n"
        ).encode("utf-8"),
    )
    runner.atomic_write_new(GATE_TABLE, markdown_gate_table(rows, label).encode("utf-8"))
    runner.atomic_write_new(
        RESULTS_TABLE,
        results_markdown(funnel, eight, gaussian, runtime).encode("utf-8"),
    )
    verdict_text = (
        f"# WP37A verdict\n\n`{label}`\n\n"
        f"Failed gates: {', '.join(failed) if failed else 'none'}.\n\n"
        "No sampler default or production code was changed. Fixed 2 remains "
        "ineligible for default selection.\n"
    )
    runner.atomic_write_new(VERDICT, verdict_text.encode("utf-8"))
    print(markdown_gate_table(rows, label))
    return safe_summary


def subprocess_run_git_show_provenance() -> bytes:
    import subprocess

    relative = runner.PROVENANCE.relative_to(runner.REPOSITORY).as_posix()
    completed = subprocess.run(
        ["git", "-C", str(runner.REPOSITORY), "show", f"HEAD:{relative}"],
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError("PROVENANCE.json is not committed at HEAD")
    return completed.stdout


if __name__ == "__main__":
    analyze()
