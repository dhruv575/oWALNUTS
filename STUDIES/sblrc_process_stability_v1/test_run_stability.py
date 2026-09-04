import unittest

import run_stability as study


class ReturnCodeTests(unittest.TestCase):
    def test_access_violation_forms(self):
        forms = study.return_code_forms(0xC0000005)
        self.assertEqual(forms["unsigned_32"], 3221225477)
        self.assertEqual(forms["signed_32"], -1073741819)
        self.assertEqual(forms["hex_32"], "0xC0000005")

    def test_negative_return_code_normalizes_to_windows_dword(self):
        forms = study.return_code_forms(-1073741819)
        self.assertEqual(forms["unsigned_32"], 3221225477)
        self.assertEqual(forms["signed_32"], -1073741819)
        self.assertEqual(forms["hex_32"], "0xC0000005")


class ProtocolTests(unittest.TestCase):
    def test_forbidden_seed_is_absent_and_matrix_has_expected_size(self):
        seeds = [seed for _, seed in study.all_cases()]
        self.assertNotIn(study.FORBIDDEN_SEED, seeds)
        self.assertEqual(
            len(seeds), study.PROTOCOL["execution"]["expected_child_count"]
        )
        self.assertEqual(len(seeds), len(set(seeds)))

    def test_sample_heartbeat_sequence_contains_required_stage_pairs(self):
        row = next(
            row for row in study.PROTOCOL["matrix"] if row["id"] == "sample-r4-t4"
        )
        sequence = study.expected_heartbeat_sequence(row)
        self.assertIn(("load", "before", None), sequence)
        self.assertIn(("load", "after", None), sequence)
        self.assertIn(("initialization", "before", None), sequence)
        self.assertIn(("initialization", "after", None), sequence)
        self.assertIn(("sampling", "before", None), sequence)
        self.assertIn(("sampling", "after", None), sequence)
        self.assertIn(("result_write", "before", None), sequence)
        self.assertIn(("result_write", "after", None), sequence)
        self.assertIn(("drop", "before", None), sequence)
        self.assertIn(("drop", "after", None), sequence)

    def test_repeated_load_drop_has_every_cycle(self):
        row = next(
            row
            for row in study.PROTOCOL["matrix"]
            if row["id"] == "repeat-load-r4-t4"
        )
        sequence = study.expected_heartbeat_sequence(row)
        for cycle in range(row["load_drop_cycles"]):
            self.assertIn(("load", "before", cycle), sequence)
            self.assertIn(("load", "after", cycle), sequence)
            self.assertIn(("drop", "before", cycle), sequence)
            self.assertIn(("drop", "after", cycle), sequence)


if __name__ == "__main__":
    unittest.main()
