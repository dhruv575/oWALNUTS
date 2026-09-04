import unittest

import run_stress


class StressProtocolTests(unittest.TestCase):
    def test_frozen_matrix_is_exact_fresh_and_paired(self) -> None:
        comparator = run_stress.arm_cases("comparator")
        owned = run_stress.arm_cases("owned")
        self.assertEqual(len(comparator), 180)
        self.assertEqual(len(owned), 540)
        self.assertEqual(
            {shape: [case["shape"] for case in comparator].count(shape) for shape in ("sblrc", "diamonds", "mesquite")},
            {"sblrc": 60, "diamonds": 60, "mesquite": 60},
        )
        self.assertEqual(
            {shape: [case["shape"] for case in owned].count(shape) for shape in ("sblrc", "diamonds", "mesquite")},
            {"sblrc": 180, "diamonds": 180, "mesquite": 180},
        )
        paired = [case for case in owned if case["schedule"] == "paired"]
        self.assertEqual(
            [(case["shape"], case["seed"]) for case in comparator],
            [(case["shape"], case["seed"]) for case in paired],
        )
        self.assertNotIn(991001, [case["seed"] for case in owned])
        run_stress.validate_matrix()

    def test_return_codes_preserve_windows_forms(self) -> None:
        forms = run_stress.return_code_forms(0xC0000374)
        self.assertEqual(forms["unsigned_32"], 3221226356)
        self.assertEqual(forms["signed_32"], -1073740940)
        self.assertEqual(forms["hex_32"], "0xC0000374")

    def test_required_heartbeats_end_after_owner_drop(self) -> None:
        expected = run_stress.expected_heartbeats()
        self.assertEqual(
            expected[-3:],
            [("drop", "before"), ("drop", "after"), ("process", "complete")],
        )

    def test_event_1000_is_correlated_by_path_pid_and_start_time(self) -> None:
        unix_ms = 1788522458425
        filetime = unix_ms * 10_000 + 116444736000000000
        binary = r"C:\diagnostic\bridgestan-owned-worker-v1.exe"
        event = {
            "id": 1000,
            "record_id": 123,
            "message": (
                "Faulting application name: bridgestan-owned-worker-v1.exe\r\n"
                "Faulting module name: libwinpthread-1.dll, version: 1.0\r\n"
                "Exception code: 0xc0000374\r\n"
                "Faulting process id: 0x91B8\r\n"
                f"Faulting application start time: 0x{filetime:X}\r\n"
                f"Faulting application path: {binary}\r\n"
                "Report Id: 00000000-0000-0000-0000-000000000001\r\n"
            ),
        }
        record = {
            "child_pid": 0x91B8,
            "process_started_unix_ms": unix_ms + 10,
            "binary_path": binary,
        }
        parsed = run_stress.parse_event_1000(event)
        self.assertEqual(parsed["faulting_process_id"], 0x91B8)
        self.assertEqual(parsed["application_start_unix_ms"], unix_ms)
        self.assertEqual(parsed["faulting_module"], "libwinpthread-1.dll")
        self.assertEqual(len(run_stress.correlated_event_1000(record, [event])), 1)
        record["child_pid"] += 1
        self.assertEqual(run_stress.correlated_event_1000(record, [event]), [])

    def test_all_claimed_paired_invariants_are_compared(self) -> None:
        self.assertEqual(
            set(run_stress.CLAIMED_PARITY_FIELDS),
            {
                "sample_fingerprint_fnv1a64",
                "target_calls",
                "recoverable_failures",
                "algorithm_revision",
                "samples_observed",
            },
        )
        self.assertTrue(
            set(run_stress.CLAIMED_PARITY_FIELDS)
            <= set(run_stress.PAIRED_EQUAL_FIELDS)
        )
        baseline = {
            field: f"value-{index}"
            for index, field in enumerate(run_stress.PAIRED_EQUAL_FIELDS)
        }
        self.assertEqual(
            run_stress.paired_invariant_differences(baseline, dict(baseline)),
            {},
        )
        for field in run_stress.PAIRED_EQUAL_FIELDS:
            changed = dict(baseline)
            changed[field] = "different"
            self.assertEqual(
                set(run_stress.paired_invariant_differences(baseline, changed)),
                {field},
            )

    def test_owned_effective_replica_acceptance_requires_every_output(self) -> None:
        self.assertIsNone(
            run_stress.owned_effective_replica_violation(
                {"raw_result": {"effective_replicas": 1}}
            )
        )
        self.assertIsNotNone(
            run_stress.owned_effective_replica_violation(
                {"raw_result": {"effective_replicas": 4}}
            )
        )
        self.assertIsNotNone(run_stress.owned_effective_replica_violation({}))

    def test_comparator_effective_replica_acceptance_requires_four(self) -> None:
        faulted_after_raw = {
            "process_success": False,
            "raw_result": {"status": "ok", "effective_replicas": 4},
        }
        self.assertTrue(run_stress.has_successful_raw(faulted_after_raw))
        self.assertIsNone(
            run_stress.effective_replica_violation(
                faulted_after_raw, 4
            )
        )
        self.assertIsNotNone(
            run_stress.effective_replica_violation(
                {"raw_result": {"effective_replicas": 1}}, 4
            )
        )
        self.assertIsNotNone(run_stress.effective_replica_violation({}, 4))


if __name__ == "__main__":
    unittest.main()
