import unittest

import run_stress


class StressProtocolTests(unittest.TestCase):
    def test_frozen_matrix_is_exact_and_diagnostic(self) -> None:
        cases = run_stress.cases()
        self.assertEqual(len(cases), 180)
        self.assertEqual(
            [case["shape"] for case in cases].count("sblrc"),
            100,
        )
        self.assertEqual(
            [case["shape"] for case in cases].count("diamonds"),
            40,
        )
        self.assertEqual(
            [case["shape"] for case in cases].count("mesquite"),
            40,
        )
        self.assertEqual([case["seed"] for case in cases], list(range(991001, 991181)))
        self.assertNotIn(90101, [case["seed"] for case in cases])

    def test_return_codes_preserve_windows_forms(self) -> None:
        forms = run_stress.return_code_forms(0xC0000374)
        self.assertEqual(forms["unsigned_32"], 3221226356)
        self.assertEqual(forms["signed_32"], -1073740940)
        self.assertEqual(forms["hex_32"], "0xC0000374")

    def test_required_heartbeats_end_after_drop(self) -> None:
        expected = run_stress.expected_heartbeats()
        self.assertEqual(expected[-3:], [("drop", "before"), ("drop", "after"), ("process", "complete")])


if __name__ == "__main__":
    unittest.main()
