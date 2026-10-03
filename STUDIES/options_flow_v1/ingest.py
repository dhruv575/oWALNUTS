"""Strict balanced-panel CSV adapter; does not infer trade direction or fill gaps.

Rows: origin,group,feature_available,target_end,target_available,x,y (ISO timestamps with timezone).
Each row describes one forecast from information available at origin. Metadata
must document source, rights, units, feature construction and flow classification.
"""
from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

import numpy as np


def timestamp(value):
    result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if result.tzinfo is None:
        raise ValueError("timestamps must include an explicit timezone")
    return result.astimezone(timezone.utc)


def ingest(source, metadata, train_periods):
    required = ["source", "rights", "x_units", "y_units", "feature_construction",
                "flow_classification", "universe_selection"]
    if any(not isinstance(metadata.get(k), str) or not metadata[k].strip() for k in required):
        raise ValueError("metadata requires nonempty strings: " + ", ".join(required))
    raw = Path(source).read_bytes()
    rows = list(csv.DictReader(raw.decode("utf-8-sig").splitlines()))
    if not rows:
        raise ValueError("empty panel")
    panel = {}
    horizon = None
    for row in rows:
        origin, available, end, target_available = map(timestamp, [row['origin'], row['feature_available'], row['target_end'],row['target_available']])
        if available > origin or end <= origin or target_available<end:
            raise ValueError("feature leakage or nonpositive forecast horizon")
        duration = end - origin
        if horizon is not None and duration != horizon:
            raise ValueError("all rows must use the same forecast horizon")
        horizon = duration
        group = row['group'].strip()
        if not group:
            raise ValueError("empty group")
        key = (origin, group)
        if key in panel:
            raise ValueError("duplicate origin/group")
        x, y = float(row['x']), float(row['y'])
        if not np.isfinite([x, y]).all():
            raise ValueError("nonfinite panel value; missingness requires an explicit model")
        panel[key] = (x, y, end, target_available)
    origins = sorted({key[0] for key in panel})
    groups = sorted({key[1] for key in panel})
    if not 2 <= train_periods < len(origins):
        raise ValueError("need at least two training periods and a nonempty holdout")
    if len(panel) != len(origins) * len(groups):
        raise ValueError("unbalanced panel; no silent imputation or universe selection")
    if any(origins[i+1] - origins[i] < horizon for i in range(len(origins)-1)):
        raise ValueError("overlapping forecast outcomes require a separate dependence-aware protocol")
    cutoff = origins[train_periods]
    if any(panel[(o,g)][3] > cutoff for o in origins[:train_periods] for g in groups):
        raise ValueError("training outcomes unavailable at holdout cutoff")
    x = np.array([[panel[(o,g)][0] for g in groups] for o in origins])
    y = np.array([[panel[(o,g)][1] for g in groups] for o in origins])
    # Shared scale keeps the target's shared volatility interpretation coherent.
    xm, xs = x[:train_periods].mean(axis=0), x[:train_periods].std(axis=0)
    ym, ys = float(y[:train_periods].mean()), float(y[:train_periods].std())
    if np.any(xs <= 0) or ys <= 0:
        raise ValueError("constant training features or outcomes cannot be standardized")
    x, y = (x-xm)/xs, (y-ym)/ys
    def block(start, stop):
        return {'x': x[start:stop].tolist(), 'y': y[start:stop].tolist()}
    return {
        'data': dict(block(0,train_periods), rho=.95, nu=5.),
        'holdout': block(train_periods,None), 'source': 'real',
        'prior_predictive': False, 'source_verification':'User-declared historical panel; authenticity not independently verified',
        'forecast_contract': 'Fixed training posterior; horizon-specific latent forecasts; each x available at its recorded origin. No held-out y conditions inference.',
        'provenance': dict(metadata, sha256=hashlib.sha256(raw).hexdigest(),
                           groups=groups, origins=[o.isoformat() for o in origins],
                           train_periods=train_periods, horizon_seconds=horizon.total_seconds(),
                           latent_time='one AR transition per panel row; market closures are compressed'),
        'scaling': {'fit_on':'training_only', 'x_mean':xm.tolist(), 'x_sd':xs.tolist(),
                    'y_mean':ym, 'y_sd':ys},
    }


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('csv'); parser.add_argument('metadata'); parser.add_argument('output')
    parser.add_argument('--train-periods',type=int,required=True)
    args=parser.parse_args()
    fixture=ingest(args.csv,json.loads(Path(args.metadata).read_text()),args.train_periods)
    destination=Path(args.output)
    with destination.open('x',encoding='utf-8') as handle:
        json.dump(fixture,handle,indent=2,allow_nan=False)
