"""Exploratory marginal coverage from existing sealed prior-predictive draws.

No inference, random numbers, exclusions or calibration pass/fail test.
"""
import argparse
import hashlib
import io
import json
from pathlib import Path
import numpy as np

NAMES = ('mu', 'log_sigma', 'beta', 'h_last')
LEVELS = (.5, .9, .95)


def marginal(draws, truth):
    draws = np.asarray(draws)
    if draws.shape != (4, 400, 4) or not np.isfinite(draws).all():
        raise ValueError('Expected finite 4-chain 400-draw compact array')
    truth = np.asarray(truth)
    if truth.shape != (4,) or not np.isfinite(truth).all():
        raise ValueError('Invalid generating truth')
    result = []
    for k, name in enumerate(NAMES):
        values = draws[:, :, k].ravel()
        intervals = {}
        for level in LEVELS:
            lo, hi = np.quantile(values, [(1-level)/2, (1+level)/2], method='linear')
            intervals[str(level)] = dict(lower=float(lo), upper=float(hi),
                                         covered=bool(lo <= truth[k] <= hi))
        result.append(dict(parameter=name, truth=float(truth[k]),
                           posterior_mean=float(values.mean()),
                           fraction_below_truth=float(np.mean(values < truth[k])),
                           ties=int(np.count_nonzero(values == truth[k])), intervals=intervals))
    return result


def run(root):
    root = Path(root)
    seals = {}
    for line in (root/'CHECKSUMS.sha256').read_text().splitlines():
        digest, name = line.split(maxsplit=1)
        seals[name.removeprefix('./')] = digest

    def checked(name):
        raw = (root/name).read_bytes()
        if hashlib.sha256(raw).hexdigest() != seals.get(name):
            raise ValueError('Sealed evidence mismatch: '+name)
        return raw

    rows = []
    for stream in range(32):
        prefix = f'campaign01/campaign/stream-{stream:02d}/'
        data = json.loads(checked(prefix+'data.json'))
        candidate = json.loads(checked(prefix+'candidate.json'))
        if data['stream'] != stream or candidate['stream'] != stream:
            raise ValueError('Stream identity mismatch')
        hraw = checked(prefix+data['files']['h']['file'])
        if hashlib.sha256(hraw).hexdigest() != data['files']['h']['sha256']:
            raise ValueError('Latent record mismatch')
        h = np.load(io.BytesIO(hraw), allow_pickle=False)
        if h.shape != (283,):
            raise ValueError('Latent shape mismatch')
        by_tick = {r['tick']: r for r in candidate['rows']}
        if len(by_tick) != len(candidate['rows']):
            raise ValueError('Duplicate tick')
        for tick in range(1, 33):
            record = by_tick.get(tick)
            if record is None or record.get('candidate_status') != 'ok':
                rows.extend(dict(stream=stream, tick=tick, parameter=name, status='unavailable') for name in NAMES)
                continue
            if record['current_index'] != 249+tick:
                raise ValueError('Current latent indexing mismatch')
            raw = checked(prefix+record['compact']['file'])
            if hashlib.sha256(raw).hexdigest() != record['compact']['sha256']:
                raise ValueError('Compact record mismatch')
            draws = np.load(io.BytesIO(raw), allow_pickle=False)
            truth = [data['parameters'][name] for name in NAMES[:3]]+[h[249+tick]]
            rows.extend(dict(stream=stream, tick=tick, status='available', **r) for r in marginal(draws, truth))
    summaries = []
    for tick in range(1, 33):
        for name in NAMES:
            available = [r for r in rows if r['tick'] == tick and r['parameter'] == name and r['status'] == 'available']
            summaries.append(dict(tick=tick, parameter=name, planned=32, available=len(available),
                                  covered_counts={str(level): sum(r['intervals'][str(level)]['covered'] for r in available) for level in LEVELS},
                                  mean_fraction_below_truth=float(np.mean([r['fraction_below_truth'] for r in available])) if available else None))
    return dict(scope='Exploratory reuse, empirical marginal intervals; no SBC null test or qualification',
                limitations='32 independent histories per tick; ticks within histories dependent; MCMC quantile error unadjusted; marginal coverage alone cannot detect ignored data',
                numpy=np.__version__, seal_sha256=hashlib.sha256((root/'CHECKSUMS.sha256').read_bytes()).hexdigest(),
                planned_parameter_slots=4096, available_parameter_slots=sum(r['status']=='available' for r in rows),
                summaries=summaries, rows=rows)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('root')
    parser.add_argument('out')
    args = parser.parse_args()
    result = run(args.root)
    with Path(args.out).open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(result, stream, indent=2, allow_nan=False)
    print(json.dumps({k: v for k, v in result.items() if k not in ('rows', 'summaries')}))
