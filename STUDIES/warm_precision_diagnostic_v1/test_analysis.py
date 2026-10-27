"""Numerical/record fixtures; not study observations."""
import json
import tempfile
import unittest
from pathlib import Path

import numpy as np

import analyze as a


class AnalysisTest(unittest.TestCase):
    def test_analytic_gaussian_and_permutation(self):
        self.assertLess(a.fixtures()["single_gaussian_max_relative_error"], 1e-10)
        rng = np.random.default_rng(1)
        raw = rng.normal(size=(3, 200, 3))*.1
        raw[..., 0] -= 10
        raw[..., 1] -= 1.6
        raw[..., 2] -= 10
        q = a.analytic(raw)["quantiles"]
        qr = a.analytic(raw[::-1, ::-1])["quantiles"]
        np.testing.assert_allclose(q, qr, rtol=1e-12)

    def test_original_noise_chain_identity(self):
        rng = np.random.default_rng(2)
        raw = rng.normal(size=(3, 200, 3))*.1
        raw[..., 0] -= 10
        raw[..., 1] -= 1.6
        raw[..., 2] -= 10
        idx, tick = [0, 2, 3], 25
        result = a.compute(raw, idx, tick)
        eps = np.random.default_rng(9600000+tick).normal(size=(4, 20000))[idx, :200]
        h = raw[..., 0]+.95*(raw[..., 2]-raw[..., 0])+np.exp(raw[..., 1])*eps
        np.testing.assert_array_equal(result["noise"]["quantiles"], np.quantile(np.exp(h/2), [.5, .95]))

    def test_missing_and_duplicate_records(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/"ticks.jsonl"
            self.assertTrue(a.records(path)[1])
            path.write_text((json.dumps(dict(tick=25, status="ok"))+"\n")*2)
            self.assertTrue(a.records(path)[1])

    def test_missing_latency_not_silently_dropped(self):
        result = a.latency({1: dict(status="ok", wall_seconds=.1)})
        self.assertEqual(result["available"], 1)
        self.assertEqual(result["fraction_under_04"], 1/2000)
        self.assertIsNone(result["median_seconds"])


if __name__ == "__main__":
    unittest.main()
