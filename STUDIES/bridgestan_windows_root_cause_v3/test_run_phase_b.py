import unittest

import run_phase_b as R


class Tests(unittest.TestCase):
    def test_matrix(self):
        cells = R.cells()
        self.assertEqual(len(cells), 480)
        counts = {}
        for c in cells:
            counts[c["arm"]] = counts.get(c["arm"], 0) + 1
        self.assertEqual(counts, {"static_long": 300, "control_long": 60,
                                  "static_short": 60, "control_short": 60})
        self.assertEqual(len({c["case_id"] for c in cells}), 480)
        seeds = [c["seed"] for c in cells]
        self.assertEqual(len(set(seeds)), 480)
        self.assertFalse(set(seeds) & {90101, 90102, 90103})
        static = sorted(c["seed"] for c in cells if c["arm"] == "static_long")
        self.assertEqual(static, list(range(50700001, 50700301)))

    def test_rotation_balances_positions(self):
        cells = R.cells()
        position = {}
        for i in range(0, 480, 8):
            for j, c in enumerate(cells[i:i + 8]):
                position.setdefault(c["arm"], [0] * 8)[j] += 1
        for arm in ("control_long", "static_short", "control_short"):
            self.assertEqual(sorted(position[arm]), [7, 7, 7, 7, 8, 8, 8, 8])
        self.assertEqual(sum(position["static_long"]), 300)

    def test_manipulation(self):
        static = R.PB["runtime_expectations"]["static"]
        good = {"expect_runtime": "static", "loaded_runtime_modules": {
            "libwinpthread-1.dll": None, "libgcc_s_seh-1.dll": None, "libstdc++-6.dll": None,
            "tbb.dll": {"path": static["tbb.dll"].upper()}}}
        self.assertTrue(R.manipulation_ok(good))
        bad = {**good, "loaded_runtime_modules": {**good["loaded_runtime_modules"],
                                                   "libwinpthread-1.dll": {"path": r"C:\x.dll"}}}
        self.assertFalse(R.manipulation_ok(bad))

    def test_correlate_decimal_pid(self):
        rec = {"case_id": "static_long-50700001", "child_pid": 4660}
        props = [""] * 11
        props[3], props[6], props[7], props[8], props[10] = "m.dll", "c0000374", "0x1", "4660", str(R.EXE)
        got = R.correlate([rec], {"events": [{"id": 1000, "properties": props, "record_id": 1}]})
        self.assertEqual(got["static_long-50700001"]["exception_code"], "c0000374")

    def test_correlate_rejects_reused_pid_outside_lifetime(self):
        props = [""] * 11
        props[3], props[6], props[7], props[8], props[10] = "ntdll.dll", "c0000374", "0x1", "26612", str(R.EXE)
        event = {"id": 1000, "properties": props, "record_id": 30065,
                 "time_utc": "2026-10-25T01:56:27.5528917Z"}
        early = {"case_id": "a", "child_pid": 26612, "started_unix_ms": 1792893384757,
                 "duration_seconds": 45.2}
        late = {"case_id": "b", "child_pid": 26612, "started_unix_ms": 1792894305646,
                "duration_seconds": 2.2}
        got = R.correlate([early, late], {"events": [event]})
        self.assertEqual(sorted(got), ["a"])

    def test_rc_forms(self):
        self.assertEqual(R.rc_forms(3221226356)["hex_32"], "0xC0000374")


if __name__ == "__main__":
    unittest.main()
