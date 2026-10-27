"""Small integrity fixtures for the supplemental recovery audit; no study evidence."""
import json
import tempfile
import unittest
from pathlib import Path

import numpy as np

from audit_recovery import audit


class RecoveryAuditTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.proto = json.loads(Path(__file__).with_name("protocol.json").read_text())
        self.proto["cells"] = [self.proto["cells"][0]]
        self.proto["reference"]["ticks"] = [0]
        self.cell = self.root / self.proto["cells"][0]["id"]
        self.cell.mkdir()
        raw = np.random.default_rng(123).normal(size=(4, 1000, 3)).astype("<f4")
        raw[0, :, 0] += 8  # A discordant chain must be visible if retained.
        raw.tofile(self.cell / "tick-0000-a0.f32")
        self.rec = dict(tick=0, status="ok", file="tick-0000-a0.f32", chains=4,
                        draws=1000, kept=[0, 1, 2, 3], attempt=0,
                        rhat_h_next=1.0, attempts=[{"divergences": [7, 0, 0, 0]}])
        self.write_record()
        (self.cell / "DONE").write_text('{"returncode":0}')

    def write_record(self, copies=1):
        (self.cell / "ticks.jsonl").write_text((json.dumps(self.rec) + "\n") * copies)

    def test_global_disagreement_and_dropped_chain_identity(self):
        result = audit(self.root, self.proto)
        self.assertTrue(result["all_planned_cells_terminal_and_files_valid"])
        self.assertTrue(any(x["coordinate"] == "mu" for x in result["reference_coordinate_flags"]))
        self.assertEqual(result["reference_ticks"][0]["retained_divergences_kept"], 7)
        self.rec["kept"] = [1, 2, 3]
        self.write_record()
        result = audit(self.root, self.proto)
        self.assertTrue(result["all_planned_cells_terminal_and_files_valid"])
        self.assertLess(result["reference_ticks"][0]["coordinates"]["mu"]["rhat"], 1.01)
        self.assertEqual(result["reference_ticks"][0]["retained_divergences_kept"], 0)
        self.assertEqual(len(result["evidence_inventory"][0]["sha256"]), 64)

    def test_duplicate_tick(self):
        self.write_record(copies=2)
        self.assertFalse(audit(self.root, self.proto)["all_planned_cells_terminal_and_files_valid"])

    def test_truncated_draws(self):
        (self.cell / "tick-0000-a0.f32").write_bytes(b"bad")
        self.assertFalse(audit(self.root, self.proto)["all_planned_cells_terminal_and_files_valid"])

    def test_missing_tick_and_missing_completion(self):
        (self.cell / "ticks.jsonl").write_text("")
        (self.cell / "DONE").unlink()
        result = audit(self.root, self.proto)
        self.assertFalse(result["all_planned_cells_terminal_and_files_valid"])
        self.assertEqual(result["cells"][0]["missing_ticks"], [0])


if __name__ == "__main__":
    unittest.main()
