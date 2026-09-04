import hashlib
import json
import math
import struct
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch

import numpy as np

import run_rescue as study


def warmup_config(arm):
    return {
        "mode": "dual_averaging",
        "target_accept": 0.8,
        "mass_adaptation": True,
        "warmup_exhaustion_rule": "AcceptUnlessDivergent",
        "metric_regularization": "Stan",
        "explicit_arm": True,
        "inherits_default_chain_rescue": False,
        "chain_rescue": {
            "mode": "RestartFromBest",
            "policy": {
                "observe": "ObserveOnly",
                "current": "Immediate",
                "two_hit": "TwoHit",
            }[arm],
            "step_ratio": 0.1,
            "log_density_iqr_factor": 3.0,
            "minimum_window_transitions": 10,
            "source_tie_rule": (
                "larger step, then larger median log density, then higher chain index"
            ),
        },
    }


def sampler_error_raw(stage):
    target = study.MODELS[0]
    seed = 7
    starts = [[float(index)] for index in range(4)] if stage == "run" else []
    return {
        "schema": "chain-rescue-v2-cell-raw",
        "schema_version": 1,
        "complete": True,
        "telemetry_complete": False,
        "telemetry_unknown": stage == "run",
        "rescue_history": "unavailable" if stage == "run" else "known_zero",
        "status": "sampler_error",
        "stage": stage,
        "error": "synthetic",
        "target": target,
        "seed": seed,
        "arm": "observe",
        "chains": 4,
        "warmup": 1000,
        "retained": 1000,
        "threads": 4,
        "dimension": 1,
        "initial_positions": starts,
        "initial_position_sha256": [
            study.initial_position_sha256(position) for position in starts
        ],
        "init": {
            "rule": "owalnuts::sampler::Init::uniform()",
            "radius": 2.0,
            "max_attempts": 100,
            "start_search_calls": 4,
        },
        "warmup_config": warmup_config("observe"),
        "algorithm_revision": "test",
        "chains_data": None if stage == "run" else [],
        "actions": None if stage == "run" else [],
    }


def successful_raw(arm="observe", restart=False):
    target = study.MODELS[0]
    seed = 7
    starts = [[float(index)] for index in range(4)]
    hashes = [study.initial_position_sha256(position) for position in starts]
    chains = []
    actions = []
    for chain_index in range(4):
        hit = restart and chain_index == 0
        median = -4.0 if hit else 0.0
        criterion = "LogDensity" if hit else None
        outcome = "restarted" if hit else "kept"
        installed = [3.0] if hit else None
        event = {
            "target": target,
            "seed": seed,
            "arm": arm,
            "window_index": 0,
            "transition": 100,
            "chain": chain_index,
            "window_transitions": 50,
            "initial_position_sha256": hashes[chain_index],
            "current_step": 1.0,
            "median_log_density": median,
            "log_density_iqr": 1.0,
            "eligible": True,
            "skip_reason": None,
            "median_step": 1.0,
            "step_threshold": 0.1,
            "step_hit": False,
            "density_reference": 0.0,
            "density_spread": 1.0,
            "density_gap": 4.0 if hit else 0.0,
            "density_threshold": 3.0,
            "density_hit": hit,
            "observed_canonical_criterion": criterion,
            "prior_criterion": None,
            "prior_streak": 0,
            "resulting_criterion": None,
            "resulting_streak": 0,
            "proposed_source_chain": 3,
            "pre_action_unconstrained_position": starts[chain_index],
            "actual_source_chain": 3 if hit else None,
            "source_window_position_index": 0 if hit else None,
            "installed_step": 1.0 if hit else None,
            "installed_unconstrained_position": installed,
            "installed_position_sha256": (
                study.installed_position_sha256(installed) if hit else None
            ),
            "outcome": outcome,
            "outcome_criterion": criterion,
        }
        if hit:
            actions.append(event)
        samples = [[float(chain_index)] for _ in range(1000)]
        chains.append(
            {
                "chain": chain_index,
                "initial_position": starts[chain_index],
                "initial_position_sha256": hashes[chain_index],
                "samples": samples,
                "retained_unconstrained_sha256": study.rust_retained_sha256(
                    np.asarray(samples)
                ),
                "retained_diagnostics_sha256": "1" * 64,
                "non_rescue_telemetry_sha256": "2" * 64,
                "final_step_size": 1.0,
                "final_max_error": 1.0,
                "mass_diagonal": [1.0],
                "final_metric_sha256": "3" * 64,
                "final_tuning_sha256": "4" * 64,
                "work": {
                    "discarded": {
                        name: [] if name == "refinement_level_built" else 0
                        for name in study.WORK_FIELDS
                    },
                    "retained": {
                        name: [] if name == "refinement_level_built" else 0
                        for name in study.WORK_FIELDS
                    },
                    "total": {
                        name: [] if name == "refinement_level_built" else 0
                        for name in study.WORK_FIELDS
                    },
                    "adaptation_target_calls": 0,
                    "target_calls_including_adaptation": 0,
                },
                "retained_diagnostics": {
                    name: 0 for name in study.DIAGNOSTIC_FIELDS
                },
                "chain_rescues": [event],
            }
        )
    return {
        "schema": "chain-rescue-v2-cell-raw",
        "schema_version": 1,
        "complete": True,
        "telemetry_complete": True,
        "telemetry_unknown": False,
        "rescue_history": "complete",
        "status": "ok",
        "target": target,
        "seed": seed,
        "arm": arm,
        "chains": 4,
        "warmup": 1000,
        "retained": 1000,
        "threads": 4,
        "dimension": 1,
        "initial_positions": starts,
        "initial_position_sha256": hashes,
        "warmup_config": warmup_config(arm),
        "init": {
            "rule": "owalnuts::sampler::Init::uniform()",
            "radius": 2.0,
            "max_attempts": 100,
            "start_search_calls": 1,
        },
        "tuning": {},
        "algorithm_revision": "test",
        "target_calls_total": 1,
        "chains_data": chains,
        "actions": actions,
    }


class HashTests(unittest.TestCase):
    def test_initial_position_encoding_is_exact(self):
        values = [-0.0, 1.5, -2.25]
        digest = hashlib.sha256()
        digest.update(b"chain_rescue_v2.initial_position.v1")
        digest.update(struct.pack("<Q", 3))
        digest.update(struct.pack("<Q", 0x8000000000000000))
        digest.update(struct.pack("<Q", 0x3FF8000000000000))
        digest.update(struct.pack("<Q", 0xC002000000000000))
        self.assertEqual(study.initial_position_sha256(values), digest.hexdigest())

    def test_rust_retained_hash_preserves_shape_and_bits(self):
        values = np.asarray([[-0.0, 1.0], [2.0, 3.0]], dtype="<f8")
        digest = hashlib.sha256()
        digest.update(b"chain_rescue_v2.retained_unconstrained.v1")
        digest.update(struct.pack("<Q", 2))
        digest.update(struct.pack("<Q", 2))
        digest.update(values.tobytes(order="C"))
        self.assertEqual(study.rust_retained_sha256(values), digest.hexdigest())

    def test_identity_comparison_includes_work_adaptation_and_diagnostics(self):
        base = {
            "unconstrained_sha256": "u",
            "constrained_sha256": "c",
            "target_calls_total": 10,
            "final_step_size": [1.0],
            "final_metric_sha256": ["m"],
            "final_tuning_sha256": ["t"],
            "retained_diagnostics_sha256": ["d"],
            "non_rescue_telemetry_sha256": ["n"],
        }
        changed = dict(base, retained_diagnostics_sha256=["changed"])
        self.assertNotEqual(
            study.identity_signature(base), study.identity_signature(changed)
        )

    def test_full_draw_and_name_hashes_cover_shape_order_and_all_dimensions(self):
        values = np.arange(24, dtype=np.float64).reshape(2, 3, 4)
        self.assertNotEqual(study.array_sha256(values), study.array_sha256(values[:, :, :1]))
        self.assertNotEqual(
            study.names_sha256(["omega", "x[1]"]),
            study.names_sha256(["x[1]", "omega"]),
        )


class FormulaAndClassificationTests(unittest.TestCase):
    def test_reference_z_uses_both_mcse_terms(self):
        self.assertAlmostEqual(study.reference_z(3.0, 1.0, 1.2, 1.6), 1.0)

    def test_decisive_disagreement_is_strict_in_z_and_inclusive_in_d(self):
        self.assertFalse(study.decisive_reference_disagreement(4.0, 1.0))
        self.assertFalse(study.decisive_reference_disagreement(4.1, 0.099))
        self.assertTrue(study.decisive_reference_disagreement(-4.1, 0.10))

    def test_stable_separated_origin_uses_observe_halves_and_other_chains(self):
        draws = np.zeros((4, 1000, 1), dtype=float)
        draws[0, :, 0] = 4.0
        result = study.stable_separated_origins(
            draws, ["theta"], np.asarray([0.0]), np.asarray([2.0])
        )
        self.assertEqual(result["chains"], [0])
        self.assertEqual(
            result["by_chain"]["0"]["parameters"],
            ["theta"],
        )

    def test_unstable_subject_half_is_not_an_origin(self):
        draws = np.zeros((4, 1000, 1), dtype=float)
        draws[0, :500, 0] = 4.0
        draws[0, 500:, 0] = 5.0
        result = study.stable_separated_origins(
            draws, ["theta"], np.asarray([0.0]), np.asarray([2.0])
        )
        self.assertEqual(result["chains"], [])

    def test_diagnostic_gate_is_conjunctive(self):
        passed, gates = study.diagnostic_pass(1.01, 400, 400, 0, True, False)
        self.assertTrue(passed)
        self.assertTrue(all(gates.values()))
        failed, _ = study.diagnostic_pass(1.0101, 400, 400, 0, True, False)
        self.assertFalse(failed)

    def test_nonfinite_required_metric_fails_without_nan_skipping(self):
        passed, gates = study.diagnostic_pass(
            math.nan, 500, 500, 0, True, False, required_metrics_finite=False
        )
        self.assertFalse(passed)
        self.assertFalse(gates["required_parameter_metrics_finite"])
        fake_stats = {
            "mean": np.asarray([0.0, 0.0]),
            "sd": np.asarray([1.0, 1.0]),
            "mcse": np.asarray([0.1, 0.1]),
            "bulk_ess": np.asarray([500.0, math.nan]),
            "tail_ess": np.asarray([500.0, 500.0]),
            "rhat": np.asarray([1.0, 1.0]),
        }
        reference = {
            "mean": np.asarray([0.0, 0.0]),
            "sd": np.asarray([1.0, 1.0]),
            "mcse": np.asarray([0.1, 0.1]),
        }
        with patch.object(study, "arviz_stats", return_value=fake_stats):
            result = study.reference_metrics(
                np.zeros((4, 10, 2)), ["a", "b"], reference
            )
        self.assertFalse(result["required_metrics_finite"])
        self.assertEqual(result["nonfinite_required_parameters"], ["b"])
        self.assertIsNone(result["min_bulk_ess"])

    def test_all_process_valid_red_line_survives_missing_sibling(self):
        candidate = {
            "target": "model",
            "seed": 1,
            "arm": "two_hit",
            "origin_overwritten": True,
            "decisive_reference_disagreements": ["theta"],
            "unknown_run_error_safety_failure": False,
        }
        findings = study.all_process_safety_findings([candidate], "two_hit")
        self.assertEqual(findings["origin_overwritten"], ["model/1"])
        self.assertEqual(findings["reference"], ["model/1/theta"])

    def test_unique_restarted_chains_not_event_count(self):
        raw = {"actions": [{"chain": 1, "outcome_criterion": "Step"}] * 3}
        summary = study.action_summary(raw)
        self.assertEqual(summary["restart_actions"], 3)
        self.assertEqual(summary["unique_restarted_chains"], 1)

    def test_prediction_scopes_are_exact(self):
        current = {"unique_chain_occurrences": 2, "events": 3}
        two_hit = {"unique_chain_occurrences": 1, "events": 2}
        self.assertTrue(study.prediction_p3_held(1, current, two_hit))
        self.assertFalse(study.prediction_p3_held(0, current, two_hit))
        self.assertFalse(study.prediction_p4_held([], [], []))
        self.assertTrue(study.prediction_p4_held([], [], ["raw-z-event"]))
        self.assertTrue(study.prediction_p6_held(10, []))
        self.assertFalse(
            study.prediction_p6_held(10, ["mesquite/seed/two_hit"])
        )


class SignTestTests(unittest.TestCase):
    def test_nine_wins_of_ten_passes_exact_one_sided_test(self):
        result = study.exact_sign_test(
            [1] * 9 + [0], [0] * 9 + [1], higher_is_better=True
        )
        self.assertEqual(result["wins"], 9)
        self.assertEqual(result["non_tied_blocks"], 10)
        self.assertAlmostEqual(result["one_sided_exact_p"], 11 / 1024)
        self.assertTrue(result["passed"])

    def test_exact_ties_are_omitted_but_complete_blocks_remain(self):
        result = study.exact_sign_test(
            [1] * 9 + [0, 5], [0] * 9 + [1, 5], higher_is_better=True
        )
        self.assertEqual(result["complete_blocks"], 11)
        self.assertEqual(result["non_tied_blocks"], 10)
        self.assertEqual(result["ties"], 1)

    def test_fewer_is_better_orientation(self):
        result = study.exact_sign_test(
            [0] * 10, [1] * 10, higher_is_better=False
        )
        self.assertEqual(result["wins"], 10)
        self.assertTrue(result["passed"])


class ProcessProtocolTests(unittest.TestCase):
    def test_post_result_abnormal_exit_is_a_process_fault(self):
        reasons = study.process_failure_reasons(
            timed_out=False,
            return_code=-1073740940,
            raw_exists=True,
            raw_parse_error=None,
            raw_valid=True,
            heartbeat_complete=True,
        )
        self.assertEqual(len(reasons), 1)
        self.assertIn("return code", reasons[0])

    def test_sampler_error_with_clean_process_is_process_valid(self):
        reasons = study.process_failure_reasons(
            timed_out=False,
            return_code=0,
            raw_exists=True,
            raw_parse_error=None,
            raw_valid=True,
            heartbeat_complete=True,
        )
        self.assertEqual(reasons, [])

    def test_windows_return_code_forms(self):
        forms = study.return_code_forms(-1073740940)
        self.assertEqual(forms["hex_32"], "0xC0000374")
        self.assertEqual(forms["unsigned_32"], 3221226356)

    def test_plan_is_frozen_and_rotated(self):
        self.assertEqual(len(study.planned_cells()), 288)
        self.assertEqual(study.arm_order(0), ("observe", "current", "two_hit"))
        self.assertEqual(study.arm_order(1), ("current", "two_hit", "observe"))
        self.assertEqual(study.arm_order(2), ("two_hit", "observe", "current"))

    def test_heartbeat_sequence_covers_result_and_drop(self):
        sequence = study.expected_heartbeat_sequence()
        self.assertLess(sequence.index(("result", "after")), sequence.index(("drop", "before")))
        self.assertEqual(sequence[-1], ("process", "complete"))

    def test_launch_marker_creation_is_exclusive(self):
        with tempfile.TemporaryDirectory() as directory:
            marker = Path(directory) / "marker.json"
            study.exclusive_write_json(marker, {"claimed": 1})
            with self.assertRaises(FileExistsError):
                study.exclusive_write_json(marker, {"claimed": 2})
            self.assertEqual(json.loads(marker.read_text())["claimed"], 1)

    def test_process_record_without_marker_is_invalid(self):
        with tempfile.TemporaryDirectory() as directory:
            marker = Path(directory) / "missing.json"
            self.assertIn(
                "without required launch marker",
                study.validate_process_marker({}, marker)[0],
            )

    def test_raw_hash_authentication_detects_tamper(self):
        raw = sampler_error_raw("init")
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "raw.json"
            path.write_text(json.dumps(raw), encoding="utf-8")
            process = {
                "raw_output_path": str(path),
                "raw_output_bytes": path.stat().st_size,
                "raw_output_sha256": study.sha256(path),
            }
            authenticated = study.authenticate_raw(
                process, raw["target"], raw["arm"], raw["seed"]
            )
            self.assertEqual(authenticated["status"], "sampler_error")
            path.write_text(path.read_text() + " ", encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError, "size differs"):
                study.authenticate_raw(
                    process, raw["target"], raw["arm"], raw["seed"]
                )

    def test_init_and_run_sampler_errors_preserve_safety_semantics(self):
        init = sampler_error_raw("init")
        run = sampler_error_raw("run")
        self.assertTrue(study.validate_raw(init, init["target"], "observe", 7)[0])
        self.assertTrue(study.validate_raw(run, run["target"], "observe", 7)[0])
        init_cell = study.sampler_error_cell(
            init,
            {
                "cell_id": "init",
                "duration_seconds": 1,
                "raw_output_sha256": "a",
            },
        )
        run_cell = study.sampler_error_cell(
            run,
            {
                "cell_id": "run",
                "duration_seconds": 1,
                "raw_output_sha256": "b",
            },
        )
        self.assertFalse(init_cell["unknown_run_error_safety_failure"])
        self.assertTrue(run_cell["unknown_run_error_safety_failure"])
        self.assertEqual(init_cell["unique_restarted_chains"], 0)
        self.assertIsNone(run_cell["unique_restarted_chains"])

    def test_strict_telemetry_rejects_omission_wrong_chain_and_source(self):
        raw = successful_raw()
        self.assertTrue(study.validate_raw(raw, raw["target"], "observe", 7)[0])
        omitted = deepcopy(raw)
        del omitted["chains_data"][0]["chain_rescues"][0]["density_gap"]
        self.assertFalse(study.validate_raw(omitted, raw["target"], "observe", 7)[0])
        wrong_chain = deepcopy(raw)
        wrong_chain["chains_data"][0]["chain_rescues"][0]["chain"] = 2
        self.assertFalse(study.validate_raw(wrong_chain, raw["target"], "observe", 7)[0])
        wrong_source = successful_raw("current", restart=True)
        wrong_source["chains_data"][0]["chain_rescues"][0]["actual_source_chain"] = 2
        wrong_source["actions"][0]["actual_source_chain"] = 2
        valid, errors = study.validate_raw(
            wrong_source, wrong_source["target"], "current", 7
        )
        self.assertFalse(valid)
        self.assertTrue(any("source mismatch" in error for error in errors))

    def test_manifest_file_mismatch_is_detected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "exe"
            path.write_bytes(b"audited")
            record = study.file_record(path)
            self.assertTrue(study.file_matches_record(path, record))
            path.write_bytes(b"tampered")
            self.assertFalse(study.file_matches_record(path, record))


if __name__ == "__main__":
    unittest.main()
