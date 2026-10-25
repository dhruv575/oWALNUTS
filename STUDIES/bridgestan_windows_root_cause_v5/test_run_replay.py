import unittest

import run_replay as R


class Tests(unittest.TestCase):
    def test_order(self):
        cells = R.cells()
        self.assertEqual(len(cells), 11)
        self.assertEqual(sum(c["gating"] for c in cells), 6)
        self.assertEqual([c["arm"][0] for c in cells], list("ABCBACABCDE"))
        self.assertEqual(R.PROTOCOL["seed"], 50801734)

    def test_reproduced_rule(self):
        raw = {"status": "sampler_error", "error": {
            "kind": "Numerical", "chain": 2, "transition": 9,
            "display": "kernel attempted a nonfinite target position (chain 2, transition 9); ..."}}
        self.assertTrue(R.reproduced_v5(raw))
        for key, value in (("chain", 1), ("transition", 8), ("kind", "Target")):
            bad = {**raw, "error": {**raw["error"], key: value}}
            self.assertFalse(R.reproduced_v5(bad))
        self.assertFalse(R.reproduced_v5({"status": "ok"}))
        self.assertFalse(R.reproduced_v5(None))

    def test_commands_use_arm_exes(self):
        for c in R.cells():
            cmd = R.command_for(c)
            self.assertIn(str(R.exe_for(c)), cmd[-1])
            if c["exe"] == "wp50d":
                self.assertIn("'50801734'", cmd[-1])


if __name__ == "__main__":
    unittest.main()
