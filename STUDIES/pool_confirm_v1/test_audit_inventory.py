"""Recovery integrity checks on temporary fixtures, never study evidence."""
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from audit_inventory import audit


class InventoryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.here = Path(self.temp.name)
        data = b'{"y": [0.0]}'
        (self.here / "data.json").write_bytes(data)
        protocol = {
            "datasets": {"sim": {"file": "data.json", "sha256": hashlib.sha256(data).hexdigest()}},
            "cells": [{"id": "ref-sim-lo", "arm": "ref", "ticks": [0, 1]}],
        }
        (self.here / "protocol.json").write_text(json.dumps(protocol))
        self.cells = self.here / "cells"
        self.folder = self.cells / "ref-sim-lo"

    def records(self, rows):
        self.folder.mkdir(parents=True, exist_ok=True)
        (self.folder / "ticks.jsonl").write_text("\n".join(json.dumps(r) for r in rows) + "\n")

    def result(self):
        return audit(self.here, self.cells, hash_draws=True)

    def test_missing_output_and_empty_directory_are_incomplete(self):
        self.assertEqual(self.result()["existing_cells"], 0)
        self.folder.mkdir(parents=True)
        result = self.result()
        self.assertEqual(result["existing_cells"], 1)
        self.assertEqual(result["complete_record_sets"], 0)
        self.assertEqual(result["cells"][0]["missing_ticks"], [0, 1])

    def test_failed_records_are_complete_without_claiming_success(self):
        self.records([{"tick": 0, "status": "gate_failed"}, {"tick": 1, "status": "failed"}])
        result = self.result()
        self.assertEqual(result["complete_record_sets"], 1)
        self.assertEqual(result["cells"][0]["status_counts"], {"gate_failed": 1, "failed": 1})

    def test_truncated_draw_file_is_detected(self):
        self.records([{"tick": 0, "status": "ok", "file": "tick-000.f32", "chains": 4, "draws": 2},
                      {"tick": 1, "status": "failed"}])
        path = self.folder / "tick-000.f32"
        path.write_bytes(bytes(127))
        result = self.result()
        self.assertEqual(result["complete_record_sets"], 0)
        self.assertIn("expected 128", result["cells"][0]["errors"][0])
        path.write_bytes(bytes(128))
        result = self.result()
        self.assertEqual(result["complete_record_sets"], 1)
        self.assertEqual(result["cells"][0]["files"][0]["sha256"], hashlib.sha256(bytes(128)).hexdigest())

    def test_partial_jsonl_is_reported(self):
        self.records([{"tick": 0, "status": "failed"}])
        with (self.folder / "ticks.jsonl").open("a") as stream:
            stream.write('{"tick": 1, "status":')
        result = self.result()
        self.assertEqual(result["complete_record_sets"], 0)
        self.assertEqual(result["cells"][0]["missing_ticks"], [1])
        self.assertTrue(result["cells"][0]["errors"])

    def test_duplicate_and_out_of_range_ticks_are_reported(self):
        self.records([{"tick": t, "status": "failed"} for t in (0, 0, 1, 2)])
        result = self.result()
        self.assertEqual(result["complete_record_sets"], 0)
        self.assertEqual(result["cells"][0]["duplicate_ticks"], [0])
        self.assertEqual(result["cells"][0]["unexpected_ticks"], [2])

    def test_malformed_records_do_not_crash(self):
        self.records([None, {"tick": "0"}, {"tick": 0},
                      {"tick": 1, "status": "ok", "file": "tick-001.f32"}])
        result = self.result()
        self.assertEqual(result["complete_record_sets"], 0)
        self.assertEqual(len(result["cells"][0]["errors"]), 4)


if __name__ == "__main__":
    unittest.main()
