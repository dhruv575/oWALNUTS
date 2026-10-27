#!/usr/bin/env python3
"""Read-only recovery inventory; does not run, repair, or replace study cells.

Usage: python audit_inventory.py [cells-dir] [--hash-draws]
Prints JSON to stdout. Run against the original study source/protocol.
"""
import hashlib
import json
import sys
from pathlib import Path


def digest(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def audit(here, cells, hash_draws=False):
    protocol = json.loads((here / "protocol.json").read_text())
    report = {
        "protocol_sha256": digest(here / "protocol.json"),
        "datasets": {},
        "cells": [],
    }
    for name, spec in protocol["datasets"].items():
        actual = digest(here / spec["file"])
        report["datasets"][name] = {
            "sha256": actual,
            "matches_protocol": actual == spec["sha256"],
        }
    for spec in protocol["cells"]:
        folder = cells / spec["id"]
        expected = spec["ticks"] if spec["arm"] == "ref" else list(range(spec["ticks"] + 1))
        item = {
            "id": spec["id"],
            "arm": spec["arm"],
            "exists": folder.exists(),
            "expected_records": len(expected),
            "records": 0,
            "status_counts": {},
            "missing_ticks": list(expected),
            "duplicate_ticks": [],
            "unexpected_ticks": [],
            "errors": [],
            "files": [],
        }
        log = folder / "ticks.jsonl"
        seen = set()
        if log.exists():
            item["ticks_sha256"] = digest(log)
            for line_number, line in enumerate(log.read_text().splitlines(), 1):
                try:
                    record = json.loads(line)
                except json.JSONDecodeError as exc:
                    item["errors"].append(f"line {line_number}: {exc}")
                    continue
                if not isinstance(record, dict):
                    item["errors"].append(f"line {line_number}: record is not an object")
                    continue
                tick = record.get("tick")
                if not isinstance(tick, int) or isinstance(tick, bool):
                    item["errors"].append(f"line {line_number}: invalid tick {tick!r}")
                    continue
                if tick < 0:
                    continue
                item["records"] += 1
                if tick in seen:
                    item["duplicate_ticks"].append(tick)
                seen.add(tick)
                if tick not in expected:
                    item["unexpected_ticks"].append(tick)
                status = record.get("status", "missing_status")
                if not isinstance(status, str):
                    item["errors"].append(f"tick {tick}: invalid status {status!r}")
                    status = "invalid_status"
                if status == "missing_status":
                    item["errors"].append(f"tick {tick}: missing status")
                item["status_counts"][status] = item["status_counts"].get(status, 0) + 1
                if status != "ok":
                    continue
                name = record.get("file") if spec["arm"] == "ref" else f"tick-{tick:03}.f32"
                if not name:
                    item["errors"].append(f"tick {tick}: missing draw filename")
                    continue
                path = folder / name
                shape = [record.get(k) for k in ("chains", "draws")]
                if any(not isinstance(x, int) or isinstance(x, bool) or x <= 0 for x in shape):
                    item["errors"].append(f"tick {tick}: invalid draw shape {shape}")
                    continue
                expected_bytes = shape[0] * shape[1] * 4 * 4
                size = path.stat().st_size if path.exists() else None
                entry = {"name": name, "bytes": size, "expected_bytes": expected_bytes}
                if size != expected_bytes:
                    item["errors"].append(f"tick {tick}: draw size {size}, expected {expected_bytes}")
                elif hash_draws:
                    entry["sha256"] = digest(path)
                item["files"].append(entry)
        item["missing_ticks"] = sorted(set(expected) - seen)
        item["complete_record_set"] = not (
            item["missing_ticks"] or item["duplicate_ticks"] or item["unexpected_ticks"] or item["errors"]
        )
        report["cells"].append(item)
    report["expected_cells"] = len(report["cells"])
    report["existing_cells"] = sum(c["exists"] for c in report["cells"])
    report["complete_record_sets"] = sum(c["complete_record_set"] for c in report["cells"])
    report["note"] = "Completeness is not a statistical pass. Failed cells remain evidence; missing ticks are not rerun permission."
    return report


if __name__ == "__main__":
    here = Path(__file__).resolve().parent
    positional = [a for a in sys.argv[1:] if not a.startswith("--")]
    cells = Path(positional[0]) if positional else here / "artifacts" / "cells"
    print(json.dumps(audit(here, cells, "--hash-draws" in sys.argv), indent=2))
