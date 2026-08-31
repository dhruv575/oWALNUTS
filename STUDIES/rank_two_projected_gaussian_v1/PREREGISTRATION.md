# Preregistered rank-two Gaussian diagnostic

Frozen before execution on 2026-08-30.

* Dimension: 10 (six globals, four path coordinates), projected rank: 2.
* Seeds: 71001, 71002, 71003, 71004.
* Warmup: 180; retained diagnostic draws: 300; windows: 30/50/30.
* Baseline: the same initial block-arrowhead mass with no mass adaptation.
* Health gate, every paired run: no divergences and no maximum-depth stops.
* Objective gate: the geometric mean over seeds of both (a) normalized
  expected-squared-jump distance and (b) lag-one inefficiency must improve by
  at least 5% versus baseline. Lag-one inefficiency is `(1+rho)/(1-rho)`.
* Adaptation gate: every seed must install a rank-two candidate.
* Only after all gates pass, write a fresh `T=1000` paired pilot manifest
  containing exact preflight reports and `authorized_sampling=false`. Do not
  execute that pilot.
