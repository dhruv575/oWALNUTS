#!/usr/bin/env python3
"""WP84 data: one simulated return stream from the market_uncertainty_v1 price-only SV model.

Model (STUDIES/market_uncertainty_v1/sv_prototype/target.py with P = 1 intercept, K = 0 flow
columns): y_i ~ t_5(beta, exp(h_i/2)), h_0 = mu + sigma z_0 / sqrt(1-rho^2),
h_i = mu + rho (h_{i-1} - mu) + sigma z_i, rho = 0.95 fixed, nu = 5 fixed.
True values: mu = 2 log(0.005) (0.5 % per-period scale), sigma = 0.2, beta = 0.
Seed 84084 (numpy default_rng). 1,100 returns + the true h_1100 continuation.
The repo's real Deribit receipts are not reused (no reuse licence recorded).
"""
import json, math
from pathlib import Path
import numpy as np

SEED, TOTAL, RHO, NU = 84084, 1100, 0.95, 5.0
MU, SIGMA, BETA = 2 * math.log(0.005), 0.2, 0.0
rng = np.random.default_rng(SEED)
z = rng.normal(size=TOTAL + 1)
h = np.empty(TOTAL + 1)
h[0] = MU + SIGMA * z[0] / math.sqrt(1 - RHO**2)
for i in range(1, TOTAL + 1):
    h[i] = MU + RHO * (h[i - 1] - MU) + SIGMA * z[i]
y = BETA + np.exp(h[:TOTAL] / 2) * rng.standard_t(NU, size=TOTAL)
out = dict(seed=SEED, rho=RHO, nu=NU, truth=dict(mu=MU, sigma=SIGMA, beta=BETA),
           priors=dict(mu_mean=2 * math.log(0.005), mu_sd=1.0, log_sigma_mean=math.log(0.2), log_sigma_sd=0.5,
                       beta_sd=0.002),
           y=[float(v) for v in y], h=[float(v) for v in h])
Path(__file__).resolve().parent.joinpath("models", "data.json").write_text(json.dumps(out), encoding="utf-8")
print("wrote models/data.json", float(y.std()), float(h.mean()))
