"""WP38 driver: prepare (manifest), execute (one-shot cells), analyze (gates), checksums."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROTOCOL = json.loads((HERE / "protocol.json").read_text(encoding="utf-8"))
EVIDENCE = HERE / "evidence"
BINARY = HERE / "target" / "release" / "nonfinite-position-policy-v1.exe"
TARGET_ORDER = ["sspd_repaired", "neal_funnel_10d", "gaussian_100d"]


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def atomic_write(path: Path, data: bytes) -> None:
    tmp = path.with_name(path.name + ".tmp-write")
    tmp.write_bytes(data)
    os.replace(tmp, path)


def canonical_json(obj) -> bytes:
    return (json.dumps(obj, indent=2, sort_keys=True) + "\n").encode()


def prepare() -> None:
    cells = []
    for target in TARGET_ORDER:
        spec = PROTOCOL["targets"][target]
        for seed in spec["seeds"]:
            for arm in PROTOCOL["arms_order"]:
                cells.append(
                    {
                        "ordinal": len(cells),
                        "id": f"{target}/{seed}/{arm}",
                        "target": target,
                        "seed": seed,
                        "arm": arm,
                        "warmup": PROTOCOL["common_config"]["warmup"],
                        "retained": PROTOCOL["common_config"]["retained"],
                        "initial_step": spec["initial_step"],
                        "monitored_coordinates": spec["monitored_coordinates"],
                    }
                )
    assert len(cells) == PROTOCOL["run_plan"]["cells"], len(cells)
    atomic_write(HERE / "manifest.json", canonical_json({"schema": "owalnuts-wp38-manifest-v1", "cells": cells}))
    print(f"manifest: {len(cells)} cells")


def execute() -> None:
    manifest = json.loads((HERE / "manifest.json").read_text())
    for sub in ("records", "process", "logs"):
        (EVIDENCE / sub).mkdir(parents=True, exist_ok=True)
    provenance = {
        "binary_sha256": sha256_file(BINARY),
        "manifest_sha256": sha256_file(HERE / "manifest.json"),
        "protocol_sha256": sha256_file(HERE / "protocol.json"),
        "started_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    atomic_write(EVIDENCE / "PROVENANCE.json", canonical_json(provenance))
    timeout = PROTOCOL["run_plan"]["timeout_seconds"]
    for cell in manifest["cells"]:
        stem = f"{cell['ordinal']:03d}-{cell['id'].replace('/', '-')}"
        marker = EVIDENCE / "process" / f"{stem}.launch.json"
        if marker.exists():
            print(f"skip {stem}: already launched (one-shot)")
            continue
        record = EVIDENCE / "records" / f"{stem}.json"
        atomic_write(marker, canonical_json({"ordinal": cell["ordinal"], "id": cell["id"], "launched_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}))
        started = time.time()
        try:
            proc = subprocess.run(
                [str(BINARY), str(HERE / "manifest.json"), str(cell["ordinal"]), str(record)],
                capture_output=True, text=True, timeout=timeout, cwd=str(HERE),
            )
            exit_code, timed_out, out, err = proc.returncode, False, proc.stdout, proc.stderr
        except subprocess.TimeoutExpired as e:
            exit_code, timed_out = None, True
            out = e.stdout.decode() if isinstance(e.stdout, bytes) else (e.stdout or "")
            err = e.stderr.decode() if isinstance(e.stderr, bytes) else (e.stderr or "")
        (EVIDENCE / "logs" / f"{stem}.stdout.txt").write_text(out or "")
        (EVIDENCE / "logs" / f"{stem}.stderr.txt").write_text(err or "")
        atomic_write(
            EVIDENCE / "process" / f"{stem}.process.json",
            canonical_json(
                {
                    "ordinal": cell["ordinal"], "id": cell["id"], "exit_code": exit_code, "timed_out": timed_out,
                    "duration_seconds": time.time() - started, "record_present": record.exists(),
                    "record_sha256": sha256_file(record) if record.exists() else None,
                }
            ),
        )
        status = "?"
        if record.exists():
            status = json.loads(record.read_text())["status"]
        print(f"{stem}: exit={exit_code} timeout={timed_out} status={status} {time.time() - started:.1f}s", flush=True)
    atomic_write(EVIDENCE / "RUN-COMPLETE.json", canonical_json({"finished_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}))


def load_records():
    manifest = json.loads((HERE / "manifest.json").read_text())
    records = {}
    for cell in manifest["cells"]:
        stem = f"{cell['ordinal']:03d}-{cell['id'].replace('/', '-')}"
        path = EVIDENCE / "records" / f"{stem}.json"
        proc = EVIDENCE / "process" / f"{stem}.process.json"
        records[cell["id"]] = {
            "cell": cell,
            "record": json.loads(path.read_text()) if path.exists() else None,
            "process": json.loads(proc.read_text()) if proc.exists() else None,
        }
    return manifest, records


def complete(entry) -> bool:
    r, p = entry["record"], entry["process"]
    return bool(r) and bool(p) and p["exit_code"] == 0 and not p["timed_out"] and r["status"] == "complete"


def analyze() -> None:
    manifest, records = load_records()
    by = lambda target, seed, arm: records[f"{target}/{seed}/{arm}"]
    gates, notes = {}, {}

    # G1 identity on controls
    g1 = True
    control_rows = []
    for target in ("neal_funnel_10d", "gaussian_100d"):
        for seed in PROTOCOL["targets"][target]["seeds"]:
            a, r = by(target, seed, "abort"), by(target, seed, "reject")
            ok = (
                complete(a) and complete(r)
                and a["record"]["draw_hash_sha256"] == r["record"]["draw_hash_sha256"]
                and a["record"]["total_target_calls"] == r["record"]["total_target_calls"]
                and r["record"]["nonfinite_position_rejections_discarded"] == 0
                and r["record"]["nonfinite_position_rejections_retained"] == 0
            )
            g1 = g1 and ok
            control_rows.append({"target": target, "seed": seed, "identical": ok,
                                 "funnel_tail_mass": r["record"]["funnel_tail_mass"] if complete(r) else None})
    gates["G1_identity_controls"] = g1

    ss = PROTOCOL["targets"]["sspd_repaired"]
    seeds = ss["seeds"]
    reject_complete = [complete(by("sspd_repaired", s, "reject")) for s in seeds]
    gates["G2_completion"] = all(reject_complete)

    abort_fail = []
    for s in seeds:
        a = by("sspd_repaired", s, "abort")
        rec = a["record"]
        numerical = bool(rec) and rec["status"] == "sampler_error" and rec["error_kind"] == "Numerical" \
            and "nonfinite target position" in (rec["error_message"] or "")
        abort_fail.append({"seed": s, "complete": complete(a), "numerical_nonfinite": numerical,
                           "error": (rec or {}).get("error_message")})
    gates["G3_informativeness"] = any(x["numerical_nonfinite"] for x in abort_fail)

    g4, g5, g6 = True, True, True
    rows = []
    for s in seeds:
        a, r = by("sspd_repaired", s, "abort"), by("sspd_repaired", s, "reject")
        row = {"seed": s, "abort_complete": complete(a), "reject_complete": complete(r)}
        if complete(r):
            rr = r["record"]
            health = all(f["rhat"] <= 1.01 and f["ess_bulk"] >= 400 and f["ess_tail"] >= 400 for f in rr["functionals"])
            row.update(
                health=health,
                min_ess_bulk=min(f["ess_bulk"] for f in rr["functionals"]),
                min_ess_tail=min(f["ess_tail"] for f in rr["functionals"]),
                max_rhat=max(f["rhat"] for f in rr["functionals"]),
                rejections_discarded=rr["nonfinite_position_rejections_discarded"],
                rejections_retained=rr["nonfinite_position_rejections_retained"],
                rejections_by_phase=rr["nonfinite_position_rejections_by_phase"],
                retained_divergences=rr["retained_divergences"],
                wall_seconds=rr["wall_seconds"],
            )
            g4 = g4 and health
            g5 = g5 and rr["nonfinite_position_rejections_retained"] == 0
            if complete(a):
                consistent = (
                    rr["nonfinite_position_rejections_discarded"] == 0
                    and a["record"]["draw_hash_sha256"] == rr["draw_hash_sha256"]
                    and a["record"]["total_target_calls"] == rr["total_target_calls"]
                )
                row["consistent_with_abort"] = consistent
                g6 = g6 and consistent
        else:
            g4 = g5 = False
        rows.append(row)
    gates["G4_health"] = g4
    gates["G5_confinement"] = g5
    gates["G6_consistency"] = g6

    all_pass = all(gates.values())
    if all_pass:
        decision = "QUALIFIED_OPT_IN"
    elif (not gates["G3_informativeness"]) and all(v for k, v in gates.items() if k != "G3_informativeness"):
        decision = "UNINFORMATIVE"
    else:
        decision = "NOT_QUALIFIED"

    abort_failures = sum(1 for x in abort_fail if x["numerical_nonfinite"])
    predictions = {
        "P1": gates["G1_identity_controls"],
        "P2": 1 <= abort_failures <= 8,
        "P3": gates["G2_completion"],
        "P4": gates["G4_health"],
        "P5": all((row.get("rejections_by_phase") or [0, 0, 0])[1:] == [0, 0] for row in rows if row["reject_complete"]),
        "P5_note": "evaluated as: every rejection in the initial fast phase (first 75 warmup transitions), stricter than the registered 100",
        "P6": decision == "QUALIFIED_OPT_IN",
    }
    n_records = sum(1 for e in records.values() if e["record"] is not None)
    summary = {
        "schema": "owalnuts-wp38-analysis-v1",
        "cells_planned": len(manifest["cells"]),
        "records_present": n_records,
        "gates": gates,
        "decision": decision,
        "default_change": False,
        "abort_failures": abort_failures,
        "abort_cells": abort_fail,
        "sspd_rows": rows,
        "control_rows": control_rows,
        "predictions": predictions,
    }
    atomic_write(EVIDENCE / "analysis.json", canonical_json(summary))
    print(json.dumps({"gates": gates, "decision": decision, "abort_failures": abort_failures}, indent=2))


def checksums() -> None:
    exclusions = {"CHECKSUMS.sha256", "target", "__pycache__"}
    rows = []
    for path in sorted(
        (p for p in HERE.rglob("*") if p.is_file() and not any(part in exclusions for part in p.relative_to(HERE).parts)),
        key=lambda p: p.relative_to(HERE).as_posix().encode(),
    ):
        rows.append(f"{sha256_file(path)}  {path.relative_to(HERE).as_posix()}\n")
    atomic_write(HERE / "CHECKSUMS.sha256", "".join(rows).encode())
    print(f"{len(rows)} files")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["prepare", "execute", "analyze", "checksums"])
    args = parser.parse_args()
    {"prepare": prepare, "execute": execute, "analyze": analyze, "checksums": checksums}[args.command]()


if __name__ == "__main__":
    main()
