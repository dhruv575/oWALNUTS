import hashlib
import math
import struct
import unittest

import numpy as np

import run_rescue as study


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


if __name__ == "__main__":
    unittest.main()
