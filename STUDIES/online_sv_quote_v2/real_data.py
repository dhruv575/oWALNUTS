#!/usr/bin/env python3
"""WP88 real-data variant: one continuous BTC-PERPETUAL 30-minute bar-close log-return series.

Source (archived in the repository, no network): the 72 rolling training windows of
`STUDIES/market_uncertainty_v1/artifacts/sv-historical-rolling-v1/evidence.zip`
(`prepared/originNN-neither.json`, NN = 00..71), each 256 next-half-hour bar-close log returns
of the Deribit BTC-PERPETUAL from the frozen September development acquisition
(`market-history-acquisition-v1`, protocol sha256 f708dbe9...), origins 3 hours (6 bars)
apart. Consecutive windows overlap by 250 bars exactly (verified here), so window 00 plus
the last 6 returns of each later window is one continuous series of 256 + 6 x 71 = 682 bars.

This is the bar-close return, not the receipt-time midpoint return: the only archived
midpoint series (`live-sv-production-smoke-v1/.../asof-features.json`) has 24 rows. WP88 uses
the same model and the same priors as the simulated stream (WP84 `ILLUSTRATIVE_PRIORS`,
rho = 0.95, nu = 5); the series needs no rescaling (sd 0.0029 against the prior centre 0.005:
log sd^2 = -11.7 against mu ~ N(-10.6, 1)). 682 bars support N = 250 + 100 ticks only.
No `h` truth exists, so truth coverage is not reported for this dataset.
"""
import json, math, zipfile
from pathlib import Path
import numpy as np

HERE = Path(__file__).resolve().parent
ZIP = HERE.parent / "market_uncertainty_v1" / "artifacts" / "sv-historical-rolling-v1" / "evidence.zip"

zf = zipfile.ZipFile(ZIP)
names = sorted(n for n in zf.namelist() if n.startswith("prepared/origin") and n.endswith("-neither.json"))
series, prev, origins = None, None, []
for name in names:
    d = json.loads(zf.read(name))
    y = np.asarray(d["data"]["y"], dtype=float)
    assert len(y) == 256 and np.isfinite(y).all() and all(d["data"]["observed"])
    origins.append(int(d["admission"]["origin_ms"]))
    if prev is None:
        series = y.copy()
    else:
        assert np.array_equal(prev[6:], y[:-6]), name
        series = np.append(series, y[-6:])
    prev = y
assert set(np.diff(origins).tolist()) == {6 * 1_800_000}
out = dict(source="sv-historical-rolling-v1/evidence.zip prepared/origin00..71-neither.json, bar-close log returns",
           first_origin_ms=origins[0], last_origin_ms=origins[-1], rho=0.95, nu=5.0,
           priors=dict(mu_mean=2 * math.log(0.005), mu_sd=1.0, log_sigma_mean=math.log(0.2), log_sigma_sd=0.5,
                       beta_sd=0.002),
           y=[float(v) for v in series])
HERE.joinpath("models", "data-real.json").write_text(json.dumps(out), encoding="utf-8")
print("wrote models/data-real.json", len(series), float(series.std()), float(np.abs(series).max()))
