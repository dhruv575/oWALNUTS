import unittest

import run_gate as R


def event(pid, app, when, code="c0000374", record=1):
    props = [""] * 12
    props[3], props[6], props[7], props[8], props[10] = "ntdll.dll", code, "0x1", str(pid), str(app)
    return {"id": 1000, "properties": props, "record_id": record, "time_utc": when}


class Tests(unittest.TestCase):
    def test_matrix(self):
        cells = R.cells()
        self.assertEqual(len(cells), 1600)
        counts = {}
        for c in cells:
            counts[c["arm"]] = counts.get(c["arm"], 0) + 1
        self.assertEqual(counts, {"static_unserialised": 1000, "dynamic_unserialised": 300,
                                  "dynamic_owned": 300})
        seeds = [c["seed"] for c in cells]
        self.assertEqual(len(set(seeds)), 1600)
        self.assertFalse(set(seeds) & {90101, 90102, 90103})
        for name, arm in R.PROTOCOL["arms"].items():
            got = sorted(c["seed"] for c in cells if c["arm"] == name)
            self.assertEqual(got, list(range(arm["first_seed"], arm["last_seed"] + 1)))

    def test_blocks_of_ten_and_interleaved(self):
        cells = R.cells()
        for i in range(0, 1600, 10):
            self.assertEqual(len({c["arm"] for c in cells[i:i + 10]}), 1)
        order = R.block_order()
        self.assertEqual(len(order), 160)
        # each control block is separated by static blocks; every quarter of
        # the run holds a quarter of each arm (+-1 block)
        for q in range(4):
            part = order[q * 40:(q + 1) * 40]
            self.assertAlmostEqual(part.count("static_unserialised"), 25, delta=1)
            self.assertAlmostEqual(part.count("dynamic_unserialised"), 7.5, delta=1)
            self.assertAlmostEqual(part.count("dynamic_owned"), 7.5, delta=1)

    def test_correlate_requires_pid_path_and_lifetime(self):
        exe = R.exe_for("static_unserialised")
        rec = {"case_id": "s", "arm": "static_unserialised", "child_pid": 26612,
               "started_unix_ms": 1_800_000_000_000, "ended_unix_ms": 1_800_000_010_000}
        reuse = {"case_id": "t", "arm": "static_unserialised", "child_pid": 26612,
                 "started_unix_ms": 1_800_000_900_000, "ended_unix_ms": 1_800_000_903_000}
        inside = "2027-01-15T08:00:05.0000000Z"   # 1_800_000_005 s
        by, un = R.correlate([rec, reuse], {"events": [event(26612, exe, inside)]})
        self.assertEqual(list(by), ["s"])
        self.assertEqual(un, [])
        late = "2027-01-15T08:01:00.0000000Z"     # 50 s after rec ended, before reuse started
        by, un = R.correlate([rec, reuse], {"events": [event(26612, exe, late)]})
        self.assertEqual(by, {})
        self.assertEqual(len(un), 1)
        other = R.exe_for("dynamic_owned")
        by, un = R.correlate([rec], {"events": [event(26612, other, inside)]})
        self.assertEqual(by, {})
        self.assertEqual(un[0]["app_arm"], "dynamic_owned")

    def test_stats(self):
        self.assertAlmostEqual(R.upper95(0, 1000), 1 - 0.05 ** (1 / 1000), places=6)
        self.assertGreater(R.upper95(1, 1000), R.upper95(0, 1000))
        self.assertAlmostEqual(R.fisher(1, 300, 0, 1000)["one_sided_control_greater"],
                               300 / 1300, places=9)
        self.assertEqual(R.fisher(0, 300, 0, 1000)["one_sided_control_greater"], 1.0)

    def test_manipulation(self):
        exp = R.PROTOCOL["runtime_expectations"]["static"]
        good = {"libwinpthread-1.dll": None, "libgcc_s_seh-1.dll": None, "libstdc++-6.dll": None,
                "tbb.dll": {"path": exp["tbb.dll"]}}
        self.assertTrue(R.manipulation_ok(good, "static"))
        self.assertFalse(R.manipulation_ok({**good, "libstdc++-6.dll": {"path": "x"}}, "static"))
        self.assertIsNone(R.manipulation_ok(None, "static"))


if __name__ == "__main__":
    unittest.main()
