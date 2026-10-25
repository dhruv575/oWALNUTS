import json
import unittest
from pathlib import Path

import run_root_cause as R

HERE = Path(__file__).resolve().parent


class ProtocolTests(unittest.TestCase):
    def test_return_code_forms(self):
        f = R.return_code_forms(3221226356)
        self.assertEqual(f["hex_32"], "0xC0000374")
        self.assertEqual(f["unsigned_32"], 3221226356)
        self.assertEqual(f["signed_32"], -1073740940)

    def test_child_list_counts(self):
        children = R.child_list()
        self.assertEqual(len(children), 300)
        by_arm = {}
        for c in children:
            by_arm[c["arm"]] = by_arm.get(c["arm"], 0) + 1
        self.assertEqual(by_arm["sampler_concurrent"], 60)
        self.assertEqual(by_arm["sampler_owned"], 120)
        # 2x fix ratio
        self.assertEqual(by_arm["sampler_owned"], 2 * by_arm["sampler_concurrent"])

    def test_no_forbidden_seeds(self):
        for c in R.child_list():
            self.assertNotIn(c["seed"], (90101, 90102, 90103))

    def test_binary_arm_mapping(self):
        arms = {a["arm"]: a for a in R.PROTOCOL["arms"]}
        self.assertEqual(arms["sampler_concurrent_threads"]["binary_arm"], "sampler_concurrent")
        self.assertTrue(arms["sampler_concurrent_threads"]["model"].endswith("sblrcT__blr_model.so"))


if __name__ == "__main__":
    unittest.main()
