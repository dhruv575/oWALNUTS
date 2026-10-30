# GP jitter calibration checkpoint

Two fresh seeds, four amplitudes, four chains with1100 warmup and2000 retained draws. All prior all-functional qualification gates remain enforced. This is calibration, not independent validation.

| Amplitude | Qualified fits | Geometric mean calls/minimum bulk ESS |
|---|---|---|
| 0.0 | 2/2 | 507.326 |
| 0.25 | 2/2 | 526.285 |
| 0.5 | 2/2 | 593.349 |
| 0.75 | 2/2 | 595.408 |

Frozen selection: {'amplitude': 0.0, 'calls_per_min_bulk_ess_geomean': 507.32600966028735}

A selected nonzero amplitude must face the zero-jitter configuration and tuned native low-rank NUTS on the eight new seeds specified in GP-JITTER-CALIBRATION-PROTOCOL.md. If zero wins or no candidate is eligible, no validation advantage is asserted. Calibration selection alone does not establish improvement, application value, novelty or goal completion. The earlier dense warmup implementation failure remains in the preflight archive.
