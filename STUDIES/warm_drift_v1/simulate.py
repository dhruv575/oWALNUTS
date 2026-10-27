#!/usr/bin/env python3
"""WP96 data: two 2,250-return streams from the WP84 price-only SV model, sharing one innovation
stream (seed 96096), one with a REGIME CHANGE at return index 1250 and one without (the control).

Model (WP84 `simulate.py`, unchanged): y_i ~ t_5(beta, exp(h_i/2)), h_0 = mu + sigma z_0 / sqrt(1-rho^2),
h_i = mu + rho (h_{i-1} - mu) + sigma z_i, rho = 0.95, nu = 5, beta = 0.
Regime 1 (i < 1250): mu = 2 log(0.005) = -10.5966, sigma_h = 0.2 (the WP84 truth).
Regime 2 (i >= 1250, shift stream only): mu = 2 log(0.005) + 1.0 = -9.5966, sigma_h = 0.4; the AR(1)
recursion continues from h_1249 with the new parameters (the mean is pulled toward the new mu at rate
1 - rho per return). The control stream keeps regime 1 throughout.
Window: N = 250 returns; tick t conditions on returns [t, t + 250), so the first regime-2 return
(index 1250) enters at tick 1001 and the window is entirely regime 2 from tick 1250.
Both streams use the same z and t innovations, so the control differs from the shift stream only
through the parameter switch. 2,250 returns + the true h_2250 continuation (2,251 h values).
"""
import json, math
from pathlib import Path
import numpy as np

SEED, N_WINDOW, TICKS, RHO, NU = 96096, 250, 2000, 0.95, 5.0
TOTAL = N_WINDOW + TICKS  # 2,250 returns
SHIFT_INDEX = N_WINDOW + 1000  # first regime-2 return
MU1, SIGMA1, BETA = 2 * math.log(0.005), 0.2, 0.0
MU2, SIGMA2 = MU1 + 1.0, 0.4
PRIORS = dict(mu_mean=2 * math.log(0.005), mu_sd=1.0, log_sigma_mean=math.log(0.2), log_sigma_sd=0.5, beta_sd=0.002)

rng = np.random.default_rng(SEED)
z = rng.normal(size=TOTAL + 1)
t_innov = rng.standard_t(NU, size=TOTAL)


def stream(shift):
    h = np.empty(TOTAL + 1)
    h[0] = MU1 + SIGMA1 * z[0] / math.sqrt(1 - RHO**2)
    for i in range(1, TOTAL + 1):
        mu, sigma = (MU2, SIGMA2) if (shift and i >= SHIFT_INDEX) else (MU1, SIGMA1)
        h[i] = mu + RHO * (h[i - 1] - mu) + sigma * z[i]
    y = BETA + np.exp(h[:TOTAL] / 2) * t_innov
    return y, h


here = Path(__file__).resolve().parent
for name, shift in (("shift", True), ("control", False)):
    y, h = stream(shift)
    out = dict(seed=SEED, stream=name, rho=RHO, nu=NU, n_window=N_WINDOW, ticks=TICKS,
               shift_index=SHIFT_INDEX if shift else None,
               truth=dict(regime1=dict(mu=MU1, sigma=SIGMA1, beta=BETA),
                          regime2=dict(mu=MU2, sigma=SIGMA2, beta=BETA) if shift else None),
               priors=PRIORS, y=[float(v) for v in y], h=[float(v) for v in h])
    (here / "models" / f"data-{name}.json").write_text(json.dumps(out), encoding="utf-8")
    print(name, "sd(y) regime1 %.5f" % float(y[:SHIFT_INDEX].std()), "sd(y) after %.5f" % float(y[SHIFT_INDEX:].std()),
          "mean h after %.3f" % float(h[SHIFT_INDEX:].mean()))
