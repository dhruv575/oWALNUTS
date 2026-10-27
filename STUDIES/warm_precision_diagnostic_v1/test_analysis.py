"""Numerical/record fixtures; not study observations."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

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

    def test_invalid_reference_hash_cannot_score_warm_ticks(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            art, refs, out = root/"artifacts", root/"references", root/"out"
            art.mkdir()
            (art/"DONE.json").write_text('{"cells":[]}')
            raw = np.random.default_rng(3).normal(size=(4, 200, 3))*.1
            raw[..., 0] -= 10
            raw[..., 1] -= 1.6
            raw[..., 2] -= 10
            rec = dict(tick=25, status="ok", chains=4, draws=200, kept=[0, 1, 2, 3],
                       file="tick-0025-a0.f32", wall_seconds=.1, divergences=[0]*4)
            ref_cell = refs/"cells/ref-shift"
            ref_cell.mkdir(parents=True)
            ref_path = ref_cell/rec["file"]
            raw.astype("<f4").tofile(ref_path)
            (ref_cell/"ticks.jsonl").write_text(json.dumps(rec)+"\n")
            for cell in a.PROTO["cells"]:
                if cell["stream"] != "shift":
                    continue
                path = art/"cells"/cell["id"]
                path.mkdir(parents=True)
                (path/"ticks.jsonl").write_text(json.dumps(rec)+"\n")
                raw.astype("<f4").tofile(path/"tick-0025.f32")
            actual_identity = a.identity
            calls = 0

            def identity_with_failed_recheck(path):
                nonlocal calls
                if path == ref_path:
                    calls += 1
                    if calls == 2:
                        raise OSError("fixture post-compute input recheck failed")
                return actual_identity(path)

            argv = ["analyze.py", "--artifacts", str(art), "--references", str(refs), "--out", str(out)]
            reference_hashes = {"ref-shift/"+ref_path.name: actual_identity(ref_path)["sha256"],
                                "ref-shift/ticks.jsonl": actual_identity(ref_cell/"ticks.jsonl")["sha256"]}
            with mock.patch("sys.argv", argv), mock.patch.object(a, "REFERENCE_HASHES", reference_hashes), mock.patch.object(a, "identity", side_effect=identity_with_failed_recheck):
                a.main()
            result = json.loads((out/"results.json").read_text())
            self.assertEqual(len(result["rows"]), 480)
            self.assertFalse(any(r["status"] == "ok" for r in result["rows"]))
            self.assertTrue(all(g["estimators"]["cdf_vs_cdf"]["within_bands_no_stuck"] == 0 for g in result["groups"]))

    def test_malformed_reference_chain_indices(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/"raw.f32"
            np.ones((3, 2, 3), dtype="<f4").tofile(path)
            with self.assertRaises(ValueError):
                a.load(path, dict(chains=3, draws=2, kept=[0, 1, 3]), True)


if __name__ == "__main__":
    unittest.main()
