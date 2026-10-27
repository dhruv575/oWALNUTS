#!/usr/bin/env python3
"""Reconcile the four shared tick-2 snapshots against the completed WP97 archive.

Usage: python reconcile_snapshots.py <snapshot-parent> <final-cells-dir> <out.json>
The snapshot parent holds recovery-origin-real-{,warm-}tick002-20261027.
"""
import hashlib
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
RUN_COMMIT = "a355bae52233b9e5ede69953bb23fb899a43859f"


def sha(data):
    return hashlib.sha256(data).hexdigest()


def reconcile(snapshot_parent, cells):
    comparisons = []
    for name in ("recovery-origin-real-tick002-20261027", "recovery-origin-real-warm-tick002-20261027"):
        snapshot = snapshot_parent / name
        provenance = json.loads((snapshot / "provenance.json").read_text())
        comparisons.append({"snapshot": name, "kind": "run_commit",
                            "matches": provenance["source_git_head"] == RUN_COMMIT})
        for line in (snapshot / "files.sha256").read_text().splitlines():
            expected, relative = line.split("  ", 1)
            actual = sha((snapshot / relative).read_bytes())
            comparisons.append({"snapshot": name, "kind": "snapshot_manifest", "file": relative,
                                "expected_sha256": expected, "actual_sha256": actual, "matches": actual == expected})
        for relative in ("protocol.json", "models/data-real.json"):
            original = (snapshot / relative).read_bytes()
            frozen = subprocess.check_output(
                ["git", "show", f"{RUN_COMMIT}:STUDIES/pool_confirm_v1/{relative}"], cwd=HERE)
            comparisons.append({"snapshot": name, "kind": "frozen_source_blob", "file": relative,
                                "snapshot_sha256": sha(original), "frozen_sha256": sha(frozen), "matches": original == frozen})
        for source_cell in sorted((snapshot / "cells").iterdir()):
            final_cell = cells / source_cell.name
            final_lines = (final_cell / "ticks.jsonl").read_bytes().splitlines(keepends=True)
            for path in sorted(source_cell.iterdir()):
                original = path.read_bytes()
                if path.name == "ticks.jsonl":
                    for line in original.splitlines(keepends=True):
                        tick = json.loads(line)["tick"]
                        matching = [candidate for candidate in final_lines if json.loads(candidate).get("tick") == tick]
                        actual = matching[0] if len(matching) == 1 else b""
                        comparisons.append({"snapshot": name, "kind": "exact_record", "cell": source_cell.name,
                                            "tick": tick, "matches": len(matching) == 1 and actual == line,
                                            "snapshot_sha256": sha(line), "final_sha256": sha(actual)})
                else:
                    actual = (final_cell / path.name).read_bytes()
                    comparisons.append({"snapshot": name, "kind": "exact_file", "cell": source_cell.name,
                                        "file": path.name, "matches": original == actual,
                                        "snapshot_sha256": sha(original), "final_sha256": sha(actual)})
        for spec in provenance.get("cells", []):
            actual = sha((cells / spec["cell"] / "ticks.jsonl").read_bytes())
            comparisons.append({"snapshot": name, "kind": "completed_warm_log", "cell": spec["cell"],
                                "snapshot_sha256": spec["source_log_sha256"], "final_sha256": actual,
                                "matches": spec["source_log_sha256"] == actual})
    return {
        "run_commit": RUN_COMMIT,
        "purpose": "Verify exact artifact provenance for independently reported one-origin numerical diagnostics.",
        "note": "The reference log was still growing at snapshot time; exact selected records and files must match, not the final whole-log hash.",
        "comparisons": comparisons,
        "all_match": all(c["matches"] for c in comparisons),
    }


if __name__ == "__main__":
    result = reconcile(Path(sys.argv[1]), Path(sys.argv[2]))
    output = Path(sys.argv[3])
    if output.exists():
        raise SystemExit(f"refusing to overwrite {output}")
    output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"all_match": result["all_match"], "comparisons": len(result["comparisons"])}))
    raise SystemExit(0 if result["all_match"] else 1)
