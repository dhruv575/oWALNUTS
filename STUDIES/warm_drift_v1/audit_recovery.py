#!/usr/bin/env python3
"""Post-hoc recovery audit; does not modify raw cells or the frozen WP96 decision.

Check every planned cell and saved draw shape, and report reference diagnostics
for the saved latent/global coordinates before predictive innovation is added.
Usage: python audit_recovery.py CELLS_DIR OUTPUT_JSON
"""
import hashlib
import json
import platform
import sys
from pathlib import Path

import arviz as az
import numpy as np


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def audit(cells, protocol):
    rows = []
    refs = []
    for spec in protocol["cells"]:
        cell = cells / spec["id"]
        expected = (protocol["reference"]["ticks"] if spec["arm"] == "ref"
                    else list(range(spec["ticks"] + 1)))
        errors = []
        records = {}
        log = cell / "ticks.jsonl"
        if log.exists():
            for line_no, line in enumerate(log.read_text().splitlines(), 1):
                try:
                    rec = json.loads(line)
                    tick = rec["tick"]
                except (ValueError, KeyError) as exc:
                    errors.append(f"line {line_no}: {exc}")
                    continue
                if tick in records:
                    errors.append(f"duplicate tick {tick}")
                records[tick] = rec
        missing = sorted(set(expected) - records.keys())
        unexpected = sorted(records.keys() - set(expected))
        non_ok = {str(t): r.get("status") for t, r in records.items() if r.get("status") != "ok"}
        expected_draw_files = 0
        for tick, rec in records.items():
            if rec.get("status") != "ok":
                continue
            if spec["arm"] == "ref":
                name = rec["file"]
            elif tick == 0 or tick % protocol["reference"]["every"] == 0:
                name = f"tick-{tick:04}.f32"
            else:
                continue
            expected_draw_files += 1
            path = cell / name
            wanted = rec["chains"] * rec["draws"] * 3 * 4
            if not path.exists() or path.stat().st_size != wanted:
                errors.append(f"{name}: missing or wrong size (expected {wanted})")
                continue
            raw = np.fromfile(path, dtype="<f4").reshape(rec["chains"], rec["draws"], 3)
            if not np.isfinite(raw).all():
                errors.append(f"{name}: non-finite draws")
                continue
            if spec["arm"] != "ref":
                continue
            kept = rec["kept"]
            if len(set(kept)) != len(kept) or any(c < 0 or c >= rec["chains"] for c in kept):
                errors.append(f"{name}: invalid kept chain identities")
                continue
            if len(kept) < protocol["reference"]["min_chains"]:
                errors.append(f"{name}: recorded ok with fewer chains than the reference gate requires")
                continue
            draws = raw[kept].astype(float)
            coord = {}
            for idx, label in enumerate(("mu", "log_sigma", "h_last")):
                x = draws[..., idx]
                coord[label] = dict(rhat=float(az.rhat(x)),
                                    bulk_ess=float(az.ess(x, method="bulk")),
                                    tail_ess=float(az.ess(x, method="tail")))
            att = rec["attempts"][rec["attempt"]]
            div = att.get("divergences")
            eps = np.random.default_rng(protocol["quantities"]["eps_seed_base"] + tick).normal(size=(4, 20000))[kept, :draws.shape[1]]
            hn = draws[..., 0] + protocol["model"]["rho"] * (draws[..., 2] - draws[..., 0]) + np.exp(draws[..., 1]) * eps
            sigma = np.exp(hn / 2)
            mcse = {str(p): float(az.mcse(sigma, method="quantile", prob=p)) / float(np.quantile(sigma, p))
                    for p in (0.5, 0.95)}
            refs.append(dict(cell=spec["id"], tick=tick, kept=kept,
                             predictive_rhat_recorded=rec["rhat_h_next"], coordinates=coord,
                             sigma_quantile_relative_mcse=mcse,
                             retained_divergences_kept=(sum(div[c] for c in kept) if div is not None else None)))
        done = cell / "DONE"
        try:
            done_record = json.loads(done.read_text()) if done.exists() else None
        except ValueError as exc:
            done_record = None
            errors.append(f"invalid DONE: {exc}")
        rows.append(dict(cell=spec["id"], expected_ticks=len(expected), recorded_ticks=len(records),
                         missing_ticks=missing, unexpected_ticks=unexpected, non_ok_ticks=non_ok,
                         expected_draw_files_for_ok_ticks=expected_draw_files,
                         done=done_record, incomplete_marker=(cell / "INCOMPLETE").exists(),
                         errors=errors))
    complete = all(not r["missing_ticks"] and not r["unexpected_ticks"] and not r["errors"]
                   and r["done"] is not None and r["done"].get("returncode") == 0 for r in rows)
    flags = [dict(cell=r["cell"], tick=r["tick"], coordinate=k, **v)
             for r in refs for k, v in r["coordinates"].items()
             if not np.isfinite(v["rhat"]) or v["rhat"] > 1.01
             or v["bulk_ess"] < 400 or v["tail_ess"] < 400]
    inventory = [dict(path=p.relative_to(cells).as_posix(), bytes=p.stat().st_size, sha256=sha256(p))
                 for p in sorted(cells.rglob("*")) if p.is_file()]
    return dict(purpose="Post-hoc integrity and reference diagnostic audit, not the frozen decision rule",
                all_planned_cells_terminal_and_files_valid=complete, cells=rows,
                reference_coordinate_flags=flags, reference_ticks=refs,
                evidence_inventory=inventory, evidence_total_bytes=sum(p["bytes"] for p in inventory),
                environment=dict(python=platform.python_version(), numpy=np.__version__, arviz=az.__version__))


def finite_json(value):
    if isinstance(value, dict):
        return {k: finite_json(v) for k, v in value.items()}
    if isinstance(value, list):
        return [finite_json(v) for v in value]
    if isinstance(value, float) and not np.isfinite(value):
        return None
    return value


if __name__ == "__main__":
    cells, output = map(Path, sys.argv[1:3])
    protocol_path = Path(__file__).with_name("protocol.json")
    result = audit(cells, json.loads(protocol_path.read_text()))
    result["protocol_sha256"] = hashlib.sha256(protocol_path.read_bytes()).hexdigest()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(finite_json(result), indent=2, allow_nan=False) + "\n")
    print(json.dumps({k: result[k] for k in ("all_planned_cells_terminal_and_files_valid", "environment")}))
    print(f"Reference coordinate flags: {len(result['reference_coordinate_flags'])}")
