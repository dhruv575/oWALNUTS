import hashlib
import json
import math
import struct
import tempfile
import unittest
from pathlib import Path

import numpy as np

import analyze
import run_study as runner


class ManifestTests(unittest.TestCase):
    def test_canonical_manifest_hash_count_order_and_rotation(self):
        rows = runner.parse_manifest()
        self.assertEqual(len(rows), 84)
        self.assertEqual([row["ordinal"] for row in rows], list(range(1, 85)))
        self.assertEqual(runner.sha256(runner.MANIFEST), runner.EXPECTED_MANIFEST_SHA256)
        self.assertEqual(
            [row["arm"] for row in rows[:8]],
            ["fixed1", "fixed2", "fixed2", "fixed1"] * 2,
        )

    def test_repetition_sentinels_are_exact(self):
        rows = [
            row
            for row in runner.parse_manifest()
            if row["target"] == "eight_schools_strict"
        ]
        for row in rows:
            self.assertEqual(
                row["sentinel"],
                f"REPEAT_{row['zero_based_repetition'] + 1}_OF_3",
            )


class HashAndProcessTests(unittest.TestCase):
    def test_initial_position_hash_preserves_shape_and_bits(self):
        values = np.asarray([-0.0, 1.5, -2.25], dtype="<f8")
        digest = hashlib.sha256()
        digest.update(b"delta2_sidechecks_v1.initial_position.v1")
        digest.update(struct.pack("<Q", 1))
        digest.update(struct.pack("<Q", 3))
        digest.update(values.tobytes())
        self.assertEqual(analyze.initial_position_hash(values), digest.hexdigest())

    def test_windows_exit_code_forms_are_stable(self):
        forms = runner.return_code_forms(-1073741819)
        self.assertEqual(forms["signed_32"], -1073741819)
        self.assertEqual(forms["unsigned_32"], 3221225477)
        self.assertEqual(forms["hex_32"], "0xC0000005")

    def test_atomic_create_new_never_replaces(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "record.json"
            runner.atomic_write_new(path, b"first")
            with self.assertRaises(FileExistsError):
                runner.atomic_write_new(path, b"second")
            self.assertEqual(path.read_bytes(), b"first")


class EstimatorAndGateTests(unittest.TestCase):
    def test_eight_schools_transforms_use_within_draw_ddof1(self):
        q = np.zeros((1, 1, 10), dtype=float)
        q[..., 0] = 2.0
        q[..., 1] = math.log(3.0)
        q[..., 2:] = np.arange(8)
        transformed = analyze.functional_arrays(q)
        theta = 2.0 + 3.0 * np.arange(8)
        self.assertAlmostEqual(transformed["mean_theta"].item(), theta.mean())
        self.assertAlmostEqual(
            transformed["sd_theta"].item(), theta.std(ddof=1)
        )
        self.assertAlmostEqual(transformed["theta_1"].item(), theta[0])
        self.assertAlmostEqual(transformed["theta_8"].item(), theta[-1])

    def test_conservative_e2_mean_uncertainty_is_on_left(self):
        s1, s2 = 2.0, 2.0
        u1, u2 = 0.03, 0.04
        s_pool = math.sqrt((s1**2 + s2**2) / 2)
        u_combined = math.sqrt(u1**2 + u2**2)
        self.assertAlmostEqual(s_pool, 2.0)
        self.assertAlmostEqual(u_combined, 0.05)
        self.assertTrue(abs(0.09 - 0.0) + 2 * u_combined <= 0.10 * s_pool)
        self.assertFalse(abs(0.11 - 0.0) + 2 * u_combined <= 0.10 * s_pool)

    def test_geomean_rejects_zero_and_nonfinite(self):
        self.assertTrue(math.isnan(analyze.geometric_mean([1.0, 0.0])))
        self.assertTrue(math.isnan(analyze.geometric_mean([1.0, math.nan])))
        self.assertAlmostEqual(analyze.geometric_mean([0.5, 2.0]), 1.0)

    def test_identity_signature_covers_required_fields(self):
        raw = {
            "retained_draw_bytes_sha256": "a",
            "phase_target_callbacks": {
                "warmup_kernel": 1,
                "retained_kernel": 2,
                "adaptation": 3,
                "total_started": 6,
            },
            "final_tuning_sha256_by_chain": ["t"] * 4,
            "final_metric_sha256_by_chain": ["m"] * 4,
            "retained_diagnostics_sha256_by_chain": ["d"] * 4,
            "chains_data": [
                {"work": {"retained": {"target_calls_total": index}}}
                for index in range(4)
            ],
        }
        changed = json.loads(json.dumps(raw))
        changed["chains_data"][0]["work"]["retained"]["target_calls_total"] = 99
        self.assertNotEqual(
            analyze.identity_signature(raw), analyze.identity_signature(changed)
        )

    def test_decision_precedence(self):
        rows = [
            {"gate": name, "passed": True}
            for name in (
                "F1",
                "F2",
                "F3",
                "F4",
                "F5",
                "E1",
                "E2",
                "E3",
                "E4",
                "G1",
                "G2",
                "G3",
                "G4",
            )
        ]
        funnel = {
            "F2": {
                "arm_accuracy": {
                    "fixed1": {"p5": True},
                    "fixed2": {"p5": True},
                },
                "agreement": {"p5": True},
            },
            **{name: {"passed": True} for name in ("F3", "F4", "F5")},
        }
        eight = {name: {"passed": True} for name in ("E2", "E3", "E4")}
        gaussian = {
            "coordinate_gates": [
                {
                    "fixed2_mean": True,
                    "fixed2_variance": True,
                    "mean_agreement": True,
                    "variance_agreement": True,
                }
            ],
            **{name: {"passed": True} for name in ("G2", "G3", "G4")},
        }
        label, _ = analyze.decision(
            rows, ["synthetic process fault"], funnel, eight, gaussian
        )
        self.assertEqual(label, "INCONCLUSIVE_NOT_QUALIFIED")
        rows[-1]["passed"] = False
        gaussian["G4"]["passed"] = False
        label, _ = analyze.decision(rows, [], funnel, eight, gaussian)
        self.assertEqual(label, "FIXED2_NOT_QUALIFIED_FOR_ADAPTIVE_TO_2")


if __name__ == "__main__":
    unittest.main()
