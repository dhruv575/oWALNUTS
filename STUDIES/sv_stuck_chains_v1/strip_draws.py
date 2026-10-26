#!/usr/bin/env python3
"""Move the retained draws out of the cell JSONs (artifacts/cells, committed) into artifacts/draws/<id>.npz
(hashed, out of git), leaving per-chain summaries (medians, SD, mean of log_sigma, h_last, mu) and the rank
R-hat / bulk ESS of mu, log_sigma, h_last in the cell. Idempotent; run before `run_study.py analyze`."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import run_study as rs  # noqa: E402

DRAWS = rs.ART / "draws"


def main() -> None:
    DRAWS.mkdir(parents=True, exist_ok=True)
    n = 0
    for p in sorted(rs.CELLS.glob("*.json")):
        c = json.loads(p.read_text(encoding="utf-8"))
        if c.get("status") != "ok":
            continue
        if c.get("kind") in ("sv-cmdstan", "sv-nutpie") and "retained_draws_mu_logsigma_hlast" in c:
            arr = np.asarray(c.pop("retained_draws_mu_logsigma_hlast"), dtype=np.float32)
        elif c.get("schema") == "sv-stuck-chains-v1-sv-cell" and "draws_mu_logsigma_hlast" in c["chains_data"][0]:
            arr = np.asarray([ch.pop("draws_mu_logsigma_hlast") for ch in c["chains_data"]], dtype=np.float64)
            mu, ls, hl = arr[:, :, 0], arr[:, :, 1], arr[:, :, 2]
            for ch, s in zip(c["chains_data"], rs.chain_summary(mu, ls, hl)):
                ch.update(s)
                ch["step_at_checkpoints"] = {k: ch["step_at_transition"].get(str(t)) for k, t in rs.CHECKPOINTS.items()}
            c["rhat"] = rs.rhat_stats(mu, ls, hl)
        else:
            continue
        np.savez_compressed(DRAWS / f"{p.stem}.npz", draws=arr.astype(np.float32))
        p.write_text(json.dumps(c) + "\n", encoding="utf-8")
        n += 1
    print(f"stripped {n} cells")


if __name__ == "__main__":
    main()
