#!/usr/bin/env python3
"""Post-hoc confirmation (NOT evidence for the WP58 rule): the 12 lotka_volterra
Python cells (py-default / py-delta2 / py-levels1 / py-nutpiemetric x 3 seeds)
rerun with the package's new default start rule, init=None = "best_of"
(Init::best_of(16)), on fresh seeds 5858201-5858203.

A nutpie cell per seed runs first, only to supply the transplanted metric of
py-nutpiemetric; it is not part of the 12. Cells go to
artifacts/posthoc-bestof/ through run_gap.py's child mode (GAP_ART).

    python posthoc_bestof.py
"""
import json
import os
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / "artifacts" / "posthoc-bestof"
SEEDS = [5858201, 5858202, 5858203]
ARMS = ["nutpie", "py-default", "py-delta2", "py-levels1", "py-nutpiemetric"]
PROTOCOL = json.loads((HERE / "protocol.json").read_text(encoding="utf-8"))


def main() -> None:
    env = dict(os.environ, GAP_ART=str(OUT), PYTHONIOENCODING="utf-8",
               PYTENSOR_FLAGS=f"compiledir={PROTOCOL['pytensor_compiledir']}")
    rows = []
    for seed in SEEDS:
        for arm in ARMS:
            out = OUT / "cells" / f"lotka_volterra-{arm}-{seed}.json"
            if not out.exists():
                t = time.perf_counter()
                subprocess.run([sys.executable, str(HERE / "run_gap.py"), "cell", "lotka_volterra", arm, str(seed)],
                               env=env, timeout=PROTOCOL["cell_timeout_seconds"])
                print(f"{arm} {seed} ({time.perf_counter() - t:.0f}s)", flush=True)
            r = json.loads(out.read_text(encoding="utf-8"))
            rows.append({k: r.get(k) for k in ("arm", "seed", "status", "error", "init", "passed", "min_bulk_ess",
                                               "min_tail_ess", "max_rhat", "divergences", "ess_per_gradient",
                                               "gradients_total", "gradients_start_selection")})
    twelve = [r for r in rows if r["arm"] != "nutpie"]
    summary = {
        "declared": "post-hoc confirmation of the init=None -> best_of fix; not evidence for the WP58 rule",
        "seeds": SEEDS, "cells": rows,
        "twelve_ok": sum(r["status"] == "ok" for r in twelve),
        "twelve_passed": sum(bool(r.get("passed")) for r in twelve),
    }
    (OUT / "summary.json").write_text(json.dumps(summary, indent=1, default=float), encoding="utf-8")
    print(json.dumps({k: summary[k] for k in ("twelve_ok", "twelve_passed")}))
    for r in rows:
        print(r)


if __name__ == "__main__":
    main()
