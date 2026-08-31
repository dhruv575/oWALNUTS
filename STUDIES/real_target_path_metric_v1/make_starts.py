#!/usr/bin/env python3
"""Generate the shared chain starts (innovation coordinates) for every arm.

Mirrors `canonical::Data::initial_innovations` from the Polyscope processor:
data-informed globals and innovations, then per-chain `mu` offsets
[-0.03, -0.01, 0.01, 0.03] with zero `log sigma_x` offsets (regular rule).
The sspd-11 "cold" initialization factor is deliberately not applied
(see PREREGISTRATION.md).
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
FIXTURES = {
    "sspd-11": "sspd-11-n1000-mixed-regular-moderate-h1-none-none-cold.json",
    "sspd-10": "sspd-10-n1000-strong-near_funnel_zero-moderate-h1-blocks-contaminated-regular.json",
    "sspd-05": "sspd-05-n100-mixed-regular-moderate-h0-blocks-contaminated-regular.json",
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
    residual_mean = residuals.mean()
    residual_sd = max(float(np.sqrt(np.mean((residuals - residual_mean) ** 2))), 0.01)
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
        starts = [base.copy() for _ in MU_OFFSETS]
        for start, offset in zip(starts, MU_OFFSETS):
            start[0] += offset
        payload = {
            "fixture_id": raw["fixture_id"],
            "fixture_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "coordinates": "innovations (a=0)",
            "mu_offsets": MU_OFFSETS,
            "sigma_offsets": [0.0] * len(MU_OFFSETS),
            "starts": [s.tolist() for s in starts],
        }
        (out_dir / f"{key}.json").write_text(json.dumps(payload), encoding="utf-8")
        print(key, len(base), "globals", np.round(base[:7], 4).tolist())


if __name__ == "__main__":
    main()
