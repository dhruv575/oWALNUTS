#!/usr/bin/env python3
"""Post-hoc descriptions of WP96 failures; no altered gate and no new samples.

Usage: python diagnose_existing.py ARTIFACTS_DIR OUTPUT_JSON
"""
import json
import sys
from pathlib import Path

import numpy as np

artifacts, output = map(Path, sys.argv[1:3])
summary = json.loads((artifacts / "summary.json").read_text())
per_tick = json.loads((artifacts / "per-tick.json").read_text())
groups = []
for policy in ("frozen", "m100", "m500", "trig"):
    for stream in ("shift", "control"):
        for label, lo, hi in (("half1", 1, 1000), ("half2", 1001, 2000),
                              ("transition", 1001, 1250), ("after_window_replaced", 1251, 2000)):
            ticks = [t for row in summary["rows"] if row["policy"] == policy and row["stream"] == stream
                     for half in ("half1", "half2") for t in per_tick[f"{row['id']}:{half}"]
                     if lo <= t["tick"] <= hi]
            ok = [t for t in ticks if t["ok"]]
            entry = dict(policy=policy, stream=stream, period=label, planned_scored_ticks=len(ticks),
                         available_scored_ticks=len(ok), failures=sum(not t["accurate"] for t in ticks),
                         p50_failures=sum(abs(t["e50"]) > .02 for t in ok),
                         p95_failures=sum(abs(t["e95"]) > .05 for t in ok),
                         both_quantiles_fail=sum(abs(t["e50"]) > .02 and abs(t["e95"]) > .05 for t in ok),
                         stuck_ticks=sum(bool(t["stuck"]) for t in ok),
                         divergence_ticks=sum(t["div"] > 0 for t in ok))
            for q in (50, 95):
                e = np.array([t[f"e{q}"] for t in ok])
                mcse = np.array([t[f"mcse_rel_p{q}"] for t in ok])
                entry[f"p{q}"] = dict(signed_error_mean=float(e.mean()),
                                       signed_error_quantiles=np.quantile(e, [.05, .5, .95]).tolist(),
                                       abs_error_median=float(np.median(abs(e))),
                                       own_relative_mcse_median=float(np.median(mcse)),
                                       own_relative_mcse_p95=float(np.quantile(mcse, .95)))
            groups.append(entry)
output.parent.mkdir(parents=True, exist_ok=True)
output.write_text(json.dumps(dict(purpose="Post-hoc descriptive failure decomposition, not independent evidence or a changed decision rule",
                                  groups=groups), indent=2) + "\n")
for r in groups:
    if r["period"] in ("half1", "half2"):
        print(r["policy"], r["stream"], r["period"], "fail",r["failures"], "P50/P95/both", r["p50_failures"],r["p95_failures"],r["both_quantiles_fail"],
              "MCSE med",r["p50"]["own_relative_mcse_median"],r["p95"]["own_relative_mcse_median"],
              "signed means",r["p50"]["signed_error_mean"],r["p95"]["signed_error_mean"])
