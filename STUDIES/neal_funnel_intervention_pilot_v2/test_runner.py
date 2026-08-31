import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import analyze
import runner


class RunnerSafetyTests(unittest.TestCase):
    def test_hard_deadline_records_create_only_failure_and_stops(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "results"
            authorization = Path(temporary) / "authorization.json"
            authorization.write_text("{}")
            with (
                patch.object(runner, "validate_authorization"),
                patch.object(
                    runner.subprocess,
                    "run",
                    side_effect=subprocess.TimeoutExpired("cell", runner.WALL_SECONDS),
                ) as invoked,
            ):
                with self.assertRaises(RuntimeError):
                    runner.run_grid(authorization, output)
            self.assertEqual(invoked.call_args.kwargs["timeout"], 300)
            self.assertTrue((output / "cell-00.deadline.json").is_file())
            self.assertFalse((output / "cell-01.json").exists())

    def test_preexisting_output_directory_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "results"
            output.mkdir()
            with patch.object(runner, "validate_authorization"):
                with self.assertRaises(FileExistsError):
                    runner.run_grid(Path(temporary) / "authorization.json", output)

    def test_analyzer_rejects_partial_grid_without_output(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            output = directory / "summary.json"
            with self.assertRaises(RuntimeError):
                analyze.atomic_create(output, analyze.analyze(directory))
            self.assertFalse(output.exists())

    def test_analyzer_create_is_atomic_and_non_reusable(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "summary.json"
            analyze.atomic_create(output, {"complete": True})
            with self.assertRaises(FileExistsError):
                analyze.atomic_create(output, {"complete": False})
            self.assertEqual(output.read_text(), "{\n  \"complete\": true\n}")


if __name__ == "__main__":
    unittest.main()
