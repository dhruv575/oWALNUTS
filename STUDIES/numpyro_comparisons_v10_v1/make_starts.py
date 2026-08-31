#!/usr/bin/env python3
"""Shared chain starts (innovation coordinates) for every state-space arm.

Same rule as WP4b/WP12 (`canonical::Data::initial_innovations` + per-chain
`mu` offsets [-0.03, -0.01, 0.01, 0.03], zero `log sigma_x` offsets). The
Rust runner re-derives the rule and asserts equality before sampling; the
NumPyro cells load these files and map them to their coordinates.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
FIXTURES = {
    "sspd-05": "sspd-05-n100-mixed-regular-moderate-h0-blocks-contaminated-regular.json",
    "rm48": "real_market_48h.json",
}
MU_OFFSETS = [-0.03, -0.01, 0.01, 0.03]


def initial_innovations(y: np.ndarray) -> np.ndarray:
    logit_y = np.log(y / (1.0 - y))
    t = len(logit_y)
    diffs = np.diff(logit_y)
    mean = diffs.mean() if len(diffs) else 0.0
    variance = np.sum((diffs - mean) ** 2) / max(len(diffs) - 1, 1)
    q = np.zeros(t + 6)
    q[0] = float(np.clip(mean, -0.05, 0.05))
    q[1] = float(np.log(np.clip(np.sqrt(variance), 0.001, 1.0)))
    latent = logit_y[0] + np.arange(t) * mean
    residuals = latent - logit_y
    residual_sd = max(float(np.sqrt(np.mean((residuals - residuals.mean()) ** 2))), 0.01)
    q[2] = float(np.log(np.clip(residual_sd, 0.001, 1.0)))
    q[3] = -2.0
    q[4] = float(np.log(np.clip(residual_sd, 0.001, 1.0)))
    q[5] = 0.0
    q[6] = logit_y[0]
    q[7:] = diffs
    return q


def main() -> None:
    out_dir = HERE / "starts"
    out_dir.mkdir(exist_ok=True)
    for key, name in FIXTURES.items():
        path = HERE / "fixtures" / name
        raw = json.loads(path.read_text())
        y = np.asarray(raw["data"]["y"], dtype=np.float64)
        base = initial_innovations(y)
        starts = []
        for offset in MU_OFFSETS:
            s = base.copy()
            s[0] += offset
            starts.append(s.tolist())
        payload = {
            "fixture_id": raw["fixture_id"],
            "fixture_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "coordinates": "innovations (a=0)",
            "mu_offsets": MU_OFFSETS,
            "sigma_offsets": [0.0] * 4,
            "starts": starts,
        }
        (out_dir / f"{key}.json").write_text(json.dumps(payload))
        print(key, "dim", len(base))


if __name__ == "__main__":
    main()
