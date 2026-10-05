"""Provisionally score immutable issued intervals against a later immutable prefix.

No fitting, interval replacement, or removal of unavailable scheduled records.
Local file hashes establish identity, not external timestamp certification.
"""
import argparse
import hashlib
import importlib.util
import json
import math
import score as final_scoring
from score import interval_score
from pathlib import Path

STUDY = Path(__file__).resolve().parents[1]


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


features = load_module('scoring_features', STUDY / 'receipt_features/features.py')
snapshot = load_module('scoring_snapshot', STUDY / 'live_snapshot/snapshot.py')
MODELS = ('price_history_only', 'price_plus_pooled_flow')
HORIZON = 1_800_000_000_000


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def reconcile_prefix(original, later, root):
    checks = {}
    for name,key in [('receipts.jsonl','receipt_prefix'),('lifecycle.jsonl','lifecycle_prefix')]:
        proof=original[key]
        checks[name]=snapshot.sha_prefix(root/name,proof['bytes'])==proof['sha256']
    checks['selection.json']=digest((root/'selection.json').read_bytes())==original['files_sha256']['selection.json']
    gaps=[]
    for g in later['gaps']:
        a=g['start_monotonic_ns'];b=g.get('resubscribed_monotonic_ns',later['end_monotonic_ns'])
        if any(a<v['end_monotonic_ns'] and b>v['start_monotonic_ns'] for v in original['coverage_intervals']):gaps.append(g)
    return dict(prefix_bytes_match=all(checks.values()),checks=checks,late_gaps=gaps,
                requires_rebuild=bool(gaps) or not all(checks.values()),provisional=True)


def score(issued_dir, capture):
    issued_dir, capture = Path(issued_dir), Path(capture)
    tracked = {}

    def read(path, expected=None):
        path = Path(path).resolve()
        raw = path.read_bytes()
        actual = digest(raw)
        if expected is not None and actual != expected:
            raise ValueError(f'File identity differs: {path.name}')
        tracked[str(path)] = actual
        return raw

    for path in (Path(__file__), Path(final_scoring.__file__), Path(features.__file__), Path(snapshot.__file__)):
        read(path)
    issuance_raw = read(issued_dir / 'issuance.json')
    issuance = json.loads(issuance_raw)
    origin = issuance.get('origin_receipt_ns')
    result = dict(schema='provisional-issued-market-interval-score/v1', qualified=False, provisional=True, final_reconciliation_required=True,
                  issuance_sha256=digest(issuance_raw), origin_receipt_ns=origin,
                  issuance_status=issuance['status'], outcomes=[],
                  scope='PROVISIONAL prefix scoring only; late gaps can withdraw scores. Final scoring is a separate immutable record, never replacement of issuance or this provisional record')
    if type(origin) is not int:
        raise ValueError('Scheduled origin required even for nonissuance')
    if issuance['status'] not in ('issued','issued_no_forecast','not_issued'):
        raise ValueError('Unknown issuance status')
    if issuance['status'] == 'not_issued':
        result['outcomes'] = [dict(model=m, status='not_issued') for m in MODELS]
    else:
        issued = issuance.get('issued_monotonic_ns')
        lag = issuance.get('maximum_lag_seconds')
        if (type(issued) is not int or type(lag) not in (int, float)
                or not 0 < lag <= 10 or not origin <= issued <= origin + int(lag * 1e9)
                or issuance.get('horizon_end_receipt_ns') != origin + HORIZON):
            raise ValueError('Invalid issuance clock/horizon contract')
        summary = json.loads(read(capture / 'prefix-summary.json'))
        if summary.get('schema') != 'public-receipt-prefix-snapshot-v1' or summary.get('status') != 'prefix_snapshot_not_terminal':
            raise ValueError('Immutable prefix summary required')
        if summary['end_monotonic_ns'] < origin + HORIZON:
            raise ValueError('Later prefix has not reached the forecast horizon')
        if summary.get('receipt_prefix', {}).get('cap_clipped'):
            raise ValueError('Clipped later prefix is not admitted')
        raw = read(capture / 'receipts.jsonl', summary['files_sha256']['receipts.jsonl'])
        for name in ('lifecycle.jsonl', 'selection.json'):
            read(capture / name, summary['files_sha256'][name])
        prefix_path = issued_dir / 'snapshot/prefix-summary.json'
        prefix = json.loads(read(prefix_path, issuance['snapshot_summary_sha256']))
        for name, expected in prefix['files_sha256'].items():
            if name not in ('receipts.jsonl', 'lifecycle.jsonl', 'selection.json'):
                raise ValueError('Unexpected prefix member')
            read(issued_dir / 'snapshot' / name, expected)
        asof = json.loads(read(issued_dir / 'asof-features.json', issuance['asof_features_sha256']))
        reconciliation = reconcile_prefix(prefix, summary, capture)
        result['reconciliation'] = reconciliation
        forecasts = issuance.get('forecasts', [])
        if len(forecasts) != 2 or {f['model'] for f in forecasts} != set(MODELS):
            raise ValueError('Exactly two distinct baseline records required')
        if any(f.get('origin_receipt_ns') != origin or f.get('horizon_ns') != HORIZON for f in forecasts):
            raise ValueError('Forecast origin/horizon differs')
        if any(f.get('status') not in ('forecast','no_forecast') for f in forecasts):
            raise ValueError('Unknown forecast status')
        if (issuance['status']=='issued_no_forecast') != all(f['status']=='no_forecast' for f in forecasts):
            raise ValueError('Issuance/forecast status contradiction')
        if not asof['rows'] or asof['rows'][-1]['features']['origin_receipt_ns'] != origin:
            raise ValueError('As-of origin differs')
        if asof['rows'][-1]['label']['observed']:
            raise ValueError('Current label was already present at issuance')
        rows = [json.loads(line) for line in raw.splitlines()]
        context = features.collector_context(summary)
        # Final gap notices can retract training data as well as current features.
        # Conservatively withhold the entire forecast if any prefix coverage changed.
        invalidated = reconciliation['requires_rebuild']
        label = None
        if not invalidated:
            rebuilt = features.build(rows, origins_ns=[origin], **context)['rows'][0]
            if rebuilt['features'] != asof['rows'][-1]['features']:
                invalidated = True
            label = rebuilt['label']
        for forecast in forecasts:
            record = dict(model=forecast['model'], forecast_status=forecast['status'])
            if forecast['status'] == 'no_forecast':
                record.update(status='no_forecast', reason=forecast.get('reason'),receipt_coverage_invalidated=invalidated)
            elif invalidated:
                record['status'] = 'invalidated_receipt_coverage'
            elif forecast['status'] != 'forecast':
                raise ValueError('Unknown forecast status')
            elif not label['observed']:
                record.update(status='outcome_unavailable', reason=label['future_quote'].get('reason'))
            else:
                interval = forecast['distribution']['predictive_interval_90']
                y = label['log_midpoint_return']
                value = interval_score(y, interval)
                record.update(status='scored', observed_return=y, nominal_coverage=.9,
                              interval=interval, covered=interval[0] <= y <= interval[1],
                              width=interval[1] - interval[0], interval_score=value)
            result['outcomes'].append(record)
    for name, expected in tracked.items():
        if digest(Path(name).read_bytes()) != expected:
            raise ValueError('Scoring input/source changed')
    result['input_and_source_sha256'] = tracked
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--issued-dir', required=True, type=Path)
    parser.add_argument('--capture', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    result = score(args.issued_dir, args.capture)
    with args.output.open('x') as stream:
        json.dump(result, stream, indent=2, allow_nan=False)


if __name__ == '__main__':
    main()

