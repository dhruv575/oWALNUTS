import unittest

import run_final_qualification as final


class FinalQualificationTests(unittest.TestCase):
    def test_matrix_is_exact_fresh_and_ordered(self) -> None:
        cases = final.cases()
        self.assertEqual(len(cases), 720)
        self.assertEqual(
            [case["mode"] for case in cases].count("ordinary"), 540
        )
        self.assertEqual(
            [case["mode"] for case in cases].count("concurrent"), 180
        )
        self.assertEqual(
            (cases[0]["mode"], cases[0]["shape"], cases[0]["seed"]),
            ("ordinary", "sblrc", 4_940_001),
        )
        self.assertEqual(
            (cases[-1]["mode"], cases[-1]["shape"], cases[-1]["seed"]),
            ("concurrent", "mesquite", 4_940_860),
        )
        self.assertFalse(
            any(992_000 <= case["seed"] < 994_000 for case in cases)
        )
        final.validate_matrix()

    def test_heartbeats_cover_both_sample_drops_and_concurrent_join(self) -> None:
        ordinary = final.expected_heartbeats("ordinary")
        self.assertIn(("ordinary-a-drop", "after"), ordinary)
        self.assertIn(("ordinary-b-drop", "after"), ordinary)
        self.assertEqual(ordinary[-1], ("process", "complete"))
        concurrent = final.expected_heartbeats("concurrent")
        self.assertIn(("multi-target", "after"), concurrent)
        self.assertEqual(concurrent[-1], ("process", "complete"))

    @staticmethod
    def case(mode: str) -> dict:
        case = next(case for case in final.cases() if case["mode"] == mode)
        return case

    @staticmethod
    def sample_observation(case: dict) -> dict:
        return {
            "settings": final.expected_settings(case),
            "sample_fingerprint_fnv1a64": "0123456789abcdef",
            "diagnostic_checksum": 1.25,
            "samples_observed": 16,
            "all_retained_values_finite": True,
            "algorithm_revision": final.ALGORITHM_REVISION,
            "target_calls": 123,
            "recoverable_failures": 2,
            "dimension": 3,
            "parameter_names": ["a", "b", "c"],
            "model_info": "fake",
            "compiled_threading": "Serialised",
            "threading": "Serialised",
            "execution": "OwnedSerialised",
            "requested_replicas": 4,
            "effective_replicas": 1,
        }

    @staticmethod
    def concurrent_observation(case: dict) -> dict:
        return {
            "settings": final.expected_settings(case),
            "probe_count": 16,
            "position_fingerprint_fnv1a64": "1111111111111111",
            "value_gradient_fingerprint_fnv1a64": "2222222222222222",
            "diagnostic_checksum": 2.5,
            "all_values_finite": True,
            "target_calls": 16,
            "recoverable_failures": 0,
            "dimension": 3,
            "parameter_names": ["a", "b", "c"],
            "model_info": "fake",
            "compiled_threading": "Serialised",
            "threading": "Serialised",
            "execution": "OwnedSerialised",
            "requested_replicas": 4,
            "effective_replicas": 1,
        }

    def test_ordinary_raw_requires_exact_repeat_and_metadata(self) -> None:
        case = self.case("ordinary")
        observation = self.sample_observation(case)
        raw = {
            "schema": "bridgestan-owned-worker-final-qualification-child",
            "status": "ok",
            "diagnostic_only": True,
            "mode": "ordinary",
            "shape": case["shape"],
            "seed": case["seed"],
            "requested_replicas": 4,
            "effective_replicas": 1,
            "threads": 4,
            "chains": 4,
            "warmup_per_chain": 4,
            "retained_per_chain": 4,
            "expected_samples_per_run": 16,
            "parity_exact": True,
            "run_a": observation,
            "run_b": dict(observation),
        }
        self.assertEqual(final.validate_raw(raw, case), [])
        raw["run_b"] = {**observation, "target_calls": 124}
        errors = final.validate_raw(raw, case)
        self.assertTrue(any("run_a and run_b differ" in error for error in errors))

    def test_concurrent_raw_requires_four_serialized_instances(self) -> None:
        case = self.case("concurrent")
        observation = self.concurrent_observation(case)
        raw = {
            "schema": "bridgestan-owned-worker-final-qualification-child",
            "status": "ok",
            "diagnostic_only": True,
            "mode": "concurrent",
            "shape": case["shape"],
            "seed": case["seed"],
            "requested_replicas": 4,
            "effective_replicas": [1, 1, 1, 1],
            "threads": 4,
            "target_instances": 4,
            "probes_per_instance": 16,
            "expected_calls_per_instance": 16,
            "expected_calls_total": 64,
            "calls_per_instance": [16, 16, 16, 16],
            "calls_total": 64,
            "parity_exact": True,
            "instances": [dict(observation) for _ in range(4)],
        }
        self.assertEqual(final.validate_raw(raw, case), [])
        raw["instances"][3]["effective_replicas"] = 4
        errors = final.validate_raw(raw, case)
        self.assertTrue(
            any("effective_replicas=4, expected 1" in error for error in errors)
        )

    def test_zero_failure_bounds_match_protocol(self) -> None:
        self.assertEqual(
            final.zero_failure_upper_bound(540), 0.005532292551836959
        )
        self.assertEqual(
            final.zero_failure_upper_bound(180), 0.01650522819566269
        )
        self.assertEqual(
            final.zero_failure_upper_bound(720), 0.0041520953856636345
        )

    def test_event_1000_correlation_uses_path_pid_and_start(self) -> None:
        unix_ms = 1_788_522_458_425
        filetime = unix_ms * 10_000 + 116444736000000000
        binary = r"C:\diagnostic\final-qualification.exe"
        event = {
            "id": 1000,
            "message": (
                "Faulting application name: final-qualification.exe\r\n"
                "Faulting module name: ntdll.dll, version: 1\r\n"
                "Exception code: 0xc0000374\r\n"
                "Faulting process id: 0x91B8\r\n"
                f"Faulting application start time: 0x{filetime:X}\r\n"
                f"Faulting application path: {binary}\r\n"
                "Report Id: 00000000-0000-0000-0000-000000000001\r\n"
            ),
        }
        record = {
            "binary_path": binary,
            "child_pid": 0x91B8,
            "process_started_unix_ms": unix_ms + 5,
        }
        self.assertEqual(len(final.correlated_event_1000(record, [event])), 1)
        record["child_pid"] += 1
        self.assertEqual(final.correlated_event_1000(record, [event]), [])


if __name__ == "__main__":
    unittest.main()
