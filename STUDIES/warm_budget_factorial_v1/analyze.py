"""Descriptive E72 paired-budget report, retaining all planned slots.

Requires terminal structural inventory. Does not alter the sampling campaign.
"""
import argparse
import hashlib
import io
import json
from pathlib import Path
import numpy as np
from inventory import inventory


def precision(logs, pits, k):
    import arviz as az
    logs, pits = np.asarray(logs), np.asarray(pits)
    if k not in (400, 1600) or logs.shape != (4, k) or pits.shape != logs.shape:
        raise ValueError('Unexpected score dimensions')
    if not np.isfinite(logs).all() or not np.isfinite(pits).all() or np.any((pits < 0) | (pits > 1)):
        raise ValueError('Nonfinite or invalid score values')
    shift = float(logs.max())
    scaled = np.exp(logs-shift)
    def mcse(a):
        return 0. if np.ptp(a) == 0 else float(np.asarray(az.mcse(a, method='mean')).item())
    result = dict(logpdf=shift+float(np.log(scaled.mean())), pit=float(pits.mean()),
                  logpdf_mcse=mcse(scaled)/float(scaled.mean()), pit_mcse=mcse(pits))
    if not all(np.isfinite(v) for v in result.values()):
        raise ValueError('Unavailable MCSE')
    return result


def summarize(rows):
    summaries = []
    for job in range(12):
        all_rows = [r for r in rows if r['job'] == job]
        for subset in ('all_references', 'passing_references'):
            planned = [r for r in all_rows if subset == 'all_references' or r['reference_pass']]
            valid = [r for r in planned if r.get('metrics_status') == 'available']
            summary = dict(job=job, subset=subset, planned=len(planned), available=len(valid),
                           full_panel_available=len(valid) == len(planned))
            for metric in ('logpdf', 'pit'):
                summary['available_max_abs_'+metric+'_difference'] = max((abs(r['difference'][metric]) for r in valid), default=None)
                summary['available_median_candidate_'+metric+'_mcse'] = float(np.median([r['candidate'][metric+'_mcse'] for r in valid])) if valid else None
            summaries.append(summary)
    lookup = {(r['job'], r['tick']): r for r in rows}
    pairs = []
    for low in rows:
        if low['job'] % 2:
            continue
        high = lookup[low['job']+1, low['tick']]
        available = all(r.get('metrics_status') == 'available' for r in (low, high))
        pair = dict(low_job=low['job'], high_job=high['job'], month=low['month'], tick=low['tick'],
                    reference_pass=low['reference_pass'], available=available)
        if available:
            pair['high_minus_low_absolute_discrepancy'] = {m: abs(high['difference'][m])-abs(low['difference'][m]) for m in ('logpdf', 'pit')}
            pair['high_minus_low_candidate_mcse'] = {m: high['candidate'][m+'_mcse']-low['candidate'][m+'_mcse'] for m in ('logpdf', 'pit')}
        pairs.append(pair)
    return summaries, pairs


def run(root, reference):
    root = Path(root)
    audit = inventory(root, reference)
    refs = {(r['month'], r['tick']): r['extended'] for r in json.loads(Path(reference).read_bytes())['rows']}
    rows = []
    for slot in audit['spots']:
        row = dict(slot, metrics_status='unavailable')
        row['reference'] = refs[slot['month'], slot['tick']]
        if slot['available']:
            candidate = root/'campaign01'/f"job-{slot['job']:02d}"/'candidate'
            raw = (candidate/'records'/f"{slot['tick']:06d}.json").read_bytes()
            if hashlib.sha256(raw).hexdigest() != slot['record_sha256']:
                raise ValueError('Record changed during analysis')
            record = json.loads(raw)
            raw_arrays = (candidate/record['arrays']['file']).read_bytes()
            if hashlib.sha256(raw_arrays).hexdigest() != record['arrays']['sha256']:
                raise ValueError('Arrays changed during analysis')
            try:
                with np.load(io.BytesIO(raw_arrays), allow_pickle=False) as arrays:
                    metrics = precision(arrays['score__logpdf_by_chain_draw'], arrays['score__pit_by_chain_draw'], (400,1600)[slot['job']%2])
            except (ValueError, KeyError) as exc:
                row['metrics_error'] = repr(exc)
            else:
                if any(abs(metrics[m]-record['score'][m]) > 1e-12 for m in ('logpdf', 'pit')):
                    raise ValueError('Score reconstruction mismatch')
                row.update(metrics_status='available', candidate=metrics,
                           difference={m: metrics[m]-row['reference'][m] for m in ('logpdf', 'pit')})
        rows.append(row)
    summaries, pairs = summarize(rows)
    import arviz as az
    return dict(scope='Descriptive paired budgets; no qualification, selected seed or whole-path posterior claim',
                numpy=np.__version__, arviz=az.__version__, inventory=audit,
                rows=rows, summaries=summaries, pairs=pairs,
                paired_uncertainty='Shared schedules and reference estimates induce dependence; no independence-based combined MCSE or p-value is reported.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('root')
    parser.add_argument('reference')
    parser.add_argument('out')
    args = parser.parse_args()
    result = run(args.root, args.reference)
    with Path(args.out).open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(result, stream, indent=2, allow_nan=False)
    print(json.dumps(dict(planned_spots=len(result['rows']), planned_pairs=len(result['pairs']), available_pairs=sum(p['available'] for p in result['pairs']))))
