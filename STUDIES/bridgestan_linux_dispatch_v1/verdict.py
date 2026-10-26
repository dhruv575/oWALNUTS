#!/usr/bin/env python3
"""WP65 frozen decision rule over the three part summaries -> artifacts/verdict.json + verdict.md.

    python verdict.py

Reads artifacts/latency/summary.json, artifacts/stress/summary.json and artifacts/bench/summary.json
(written by each driver's `analyze`) and evaluates protocol.json["decision_rule"] mechanically.
"""
from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ART = HERE / "artifacts"
PROTOCOL = json.loads((HERE / "protocol.json").read_text(encoding="utf-8"))


def load(name: str) -> dict:
    p = ART / name / "summary.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


def main() -> None:
    lat, st, be = load("latency"), load("stress"), load("bench")
    models = PROTOCOL["part_a_latency"]["models"]
    n_children = PROTOCOL["part_b_fault_rate"]["children_per_path"]
    n16 = len(PROTOCOL["fixed_non_arma_models"])
    ratios = lat.get("ratios", {})
    arm = st.get("per_arm", {})
    cells = be.get("pass_counts", {})
    wall = be.get("wall_per_gradient", {})

    def lat_all(key: str, thr: float) -> dict:
        vals = {m: ratios.get(m, {}).get(key) for m in models}
        return {"values": vals, "held": bool(vals) and all(v is not None and v >= thr for v in vals.values()) and not lat.get("failures")}

    def faults_zero(a: str) -> dict:
        e = arm.get(a, {})
        return {"faults": e.get("faults"), "children": e.get("children_counted"),
                "held": e.get("faults") == 0 and e.get("children_counted") == n_children}

    par = st.get("parity", {}).get("serialised_vs_replicated", {})
    c4 = be.get("bit_identity_serialised", {})
    ser_over_rep = wall.get("owalnuts-serialised_over_owalnuts", {})
    thr_over_rep = wall.get("owalnuts-threaded_over_owalnuts", {})
    q = {
        "Q1_replicated_zero_faults": faults_zero("replicated"),
        "Q2_bit_identity": {"stress": par, "bench": {k: c4.get(k) for k in ("comparable", "identical")},
                            "held": par.get("identical") == n_children and c4.get("identical") == n16},
        "Q3a_replicated4_over_direct4_ge_2": lat_all("A2_replicated4_over_direct4_throughput_nothreads", 2.0),
        "Q3b_serialised_over_replicated_wall_per_gradient_ge_1_5": {
            "value": ser_over_rep.get("value"), "n_models": ser_over_rep.get("n_models"),
            "held": ser_over_rep.get("n_models") == n16 and (ser_over_rep.get("value") or 0) >= 1.5},
        "Q4_replicated_arm_all_ok": {"ok": cells.get("owalnuts", {}).get("ok"), "held": cells.get("owalnuts", {}).get("ok") == n16},
    }
    t = {
        "T1_threaded_direct_zero_faults": faults_zero("threaded_direct"),
        "T2_threads_direct4_over_nothreads_direct4_ge_2": lat_all("A3_threads_direct4_over_nothreads_direct4_throughput", 2.0),
        "T3_threaded_arm_all_ok_and_wall_le_1_25": {
            "ok": cells.get("owalnuts-threaded", {}).get("ok"), "value": thr_over_rep.get("value"),
            "held": cells.get("owalnuts-threaded", {}).get("ok") == n16 and thr_over_rep.get("n_models") == n16
            and (thr_over_rep.get("value") or float("inf")) <= 1.25},
    }
    replicated = all(v["held"] for v in q.values())
    threaded = all(v["held"] for v in t.values())
    out = {"schema": "bridgestan-linux-dispatch-v1-verdict",
           "replicated_concurrent_qualified_on_linux": replicated, "replicated_clauses": q,
           "direct_concurrent_threads_qualified_on_linux": threaded, "threaded_clauses": t,
           "failed_replicated_clauses": [k for k, v in q.items() if not v["held"]],
           "failed_threaded_clauses": [k for k, v in t.items() if not v["held"]],
           "inputs_present": {"latency": bool(lat), "stress": bool(st), "bench": bool(be)},
           "protocol_sha256": hashlib.sha256((HERE / "protocol.json").read_bytes()).hexdigest(),
           "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    (ART / "verdict.json").write_text(json.dumps(out, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    lines = ["# WP65 frozen decision rule", "",
             f"ReplicatedConcurrent qualified on Linux: **{replicated}**; failed clauses: {out['failed_replicated_clauses'] or 'none'}",
             f"DirectConcurrent (STAN_THREADS) qualified on Linux: **{threaded}**; failed clauses: {out['failed_threaded_clauses'] or 'none'}", "",
             "| clause | held | detail |", "|---|---|---|"]
    for k, v in {**q, **t}.items():
        detail = {kk: vv for kk, vv in v.items() if kk != "held"}
        lines.append(f"| {k} | {v['held']} | `{json.dumps(detail, default=str)[:300]}` |")
    (ART / "verdict.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
