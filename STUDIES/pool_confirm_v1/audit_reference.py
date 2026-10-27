#!/usr/bin/env python3
"""Supplemental reference audit; never changes WP97's frozen gate or verdict.

Run with the study's pinned NumPy/ArviZ environment:
  python audit_reference.py [cells-dir] [--out output.json]
Checks selected reference chains for mixing in all four stored coordinates.
"""
import hashlib
import json
import sys
from pathlib import Path

import arviz as az
import numpy as np


def finite(value):
    value = float(value)
    return value if np.isfinite(value) else None


def diagnostics(arr):
    result = {}
    for column, name in enumerate(("mu", "log_sigma", "beta", "h_last")):
        values = arr[..., column]
        result[name] = {
            "rhat_rank": finite(az.rhat(values, method="rank")),
            "ess_bulk": finite(az.ess(values, method="bulk")),
            "ess_tail": finite(az.ess(values, method="tail")),
            "mcse_mean": finite(az.mcse(values, method="mean")),
        }
    return result


def audit(here, cells):
    protocol_bytes = (here / "protocol.json").read_bytes()
    protocol = json.loads(protocol_bytes)
    rows = []
    for spec in protocol["cells"]:
        if spec["arm"] != "ref":
            continue
        folder = cells / spec["id"]
        log = folder / "ticks.jsonl"
        records = {r["tick"]: r for r in map(json.loads, log.read_text().splitlines())} if log.exists() else {}
        for tick in spec["ticks"]:
            record = records.get(tick)
            row = {"cell": spec["id"], "dataset": spec["dataset"], "tick": tick,
                   "original_status": record.get("status") if record else "missing"}
            rows.append(row)
            if not record or record.get("status") != "ok":
                continue
            raw = np.fromfile(folder / record["file"], dtype="<f4").astype(float)
            all_arr = raw.reshape(record["chains"], record["draws"], 4)
            arr = all_arr[record["kept"]]
            row["kept"] = record["kept"]
            row["original_rhat_h_next"] = record["rhat_h_next"]
            attempt = next(a for a in record["attempts"] if a["attempt"] == record["attempt"])
            divergences = attempt.get("divergences")
            row["selected_attempt_divergences_all_chains"] = divergences
            row["selected_attempt_divergences_kept"] = (
                [divergences[c] for c in record["kept"]] if divergences is not None else None
            )
            row["diagnostics"] = diagnostics(arr)
            row["all_chain_diagnostics"] = (
                row["diagnostics"] if len(record["kept"]) == record["chains"] else diagnostics(all_arr)
            )
            row["supplemental_all_rhat_le_1_01"] = all(
                d["rhat_rank"] is not None and d["rhat_rank"] <= 1.01 for d in row["diagnostics"].values()
            )
            row["supplemental_all_ess_ge_400"] = all(
                d[k] is not None and d[k] >= 400
                for d in row["diagnostics"].values() for k in ("ess_bulk", "ess_tail")
            )
    return {
        "purpose": "Supplemental diagnostics only; original h_next reference gate and qualification verdict unchanged.",
        "protocol_sha256": hashlib.sha256(protocol_bytes).hexdigest(),
        "versions": {"numpy": np.__version__, "arviz": az.__version__},
        "planned_ticks": len(rows),
        "recorded_ok_ticks": sum(r["original_status"] == "ok" for r in rows),
        "supplemental_rhat_fail_ticks": [
            [r["dataset"], r["tick"]] for r in rows if r.get("supplemental_all_rhat_le_1_01") is False
        ],
        "supplemental_ess_fail_ticks": [
            [r["dataset"], r["tick"]] for r in rows if r.get("supplemental_all_ess_ge_400") is False
        ],
        "rows": rows,
    }


if __name__ == "__main__":
    here = Path(__file__).resolve().parent
    args = sys.argv[1:]
    out = None
    if "--out" in args:
        index = args.index("--out")
        out = Path(args[index + 1])
        del args[index:index + 2]
    cells = Path(args[0]) if args else here / "artifacts" / "cells"
    result = json.dumps(audit(here, cells), indent=2, allow_nan=False)
    if out:
        out.parent.mkdir(parents=True, exist_ok=True)
        if out.exists():
            raise SystemExit(f"refusing to overwrite {out}")
        out.write_text(result + "\n", encoding="utf-8")
    else:
        print(result)
