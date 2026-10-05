"""Descriptive paired evaluation on an exact scheduled-origin denominator."""
import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import score as score_module
from score import MODELS

STATUSES = {'scored', 'not_issued', 'no_forecast', 'outcome_unavailable', 'invalidated_receipt_coverage'}


def summarize(origins, records):
    if not origins or any(type(t) is not int for t in origins) or origins != sorted(set(origins)):
        raise ValueError('Nonempty ordered distinct scheduled origins required')
    indexed = {}
    for record in records:
        origin = record['origin_receipt_ns']
        if type(origin) is not int or origin in indexed or origin not in origins:
            raise ValueError('Duplicate or unscheduled score origin')
        outcomes = record['outcomes']
        if len(outcomes) != 2 or {o['model'] for o in outcomes} != set(MODELS):
            raise ValueError('Exactly two baseline outcomes per scheduled origin required')
        for outcome in outcomes:
            if outcome['status'] not in STATUSES:
                raise ValueError('Unknown score outcome')
            if outcome['status'] == 'scored':
                if type(outcome['covered']) is not bool:
                    raise ValueError('Boolean coverage required')
                for key in ('width', 'interval_score', 'observed_return'):
                    if type(outcome[key]) not in (int, float) or not math.isfinite(outcome[key]):
                        raise ValueError('Finite score values required')
                if outcome['width'] < 0 or outcome['interval_score'] < outcome['width']:
                    raise ValueError('Invalid interval score/width')
        indexed[origin] = {o['model']: o for o in outcomes}
    if set(indexed) != set(origins):
        raise ValueError('Missing planned origins; partial reports are not complete evaluations')

    def stats(values):
        n = len(values)
        return dict(scored=n, coverage=sum(v['covered'] for v in values)/n if n else None,
                    mean_width=math.fsum(v['width'] for v in values)/n if n else None,
                    mean_interval_score=math.fsum(v['interval_score'] for v in values)/n if n else None)

    arms = {}
    for model in MODELS:
        values = [indexed[t][model] for t in origins]
        arms[model] = dict(scheduled=len(origins), status_counts=dict(Counter(v['status'] for v in values)),
                           scored_fraction=sum(v['status'] == 'scored' for v in values)/len(origins),
                           available_outcome_statistics=stats([v for v in values if v['status'] == 'scored']))
    paired = [t for t in origins if all(indexed[t][m]['status'] == 'scored' for m in MODELS)]
    for t in paired:
        if indexed[t][MODELS[0]]['observed_return'] != indexed[t][MODELS[1]]['observed_return']:
            raise ValueError('Paired models must score the identical realized outcome')
    differences = [indexed[t][MODELS[1]]['interval_score']-indexed[t][MODELS[0]]['interval_score'] for t in paired]
    return dict(schema='scheduled-market-interval-evaluation/v1', qualified=False, scheduled=len(origins),
                arms=arms, paired=dict(origins=paired, count=len(paired),
                statistics={m: stats([indexed[t][m] for t in paired]) for m in MODELS},
                flow_minus_price_interval_score=differences,
                mean_flow_minus_price_interval_score=math.fsum(differences)/len(paired) if paired else None,
                interpretation='Negative paired difference favors flow; common observed origins only'),
                uncertainty=dict(status='not_estimated', reason='Dependent chronological outcomes; no independent-binomial CI or unvalidated bootstrap'),
                scope='Descriptive summaries of supplied score records; producer identity, receipts and forecast publication are not independently revalidated')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--plan', required=True, type=Path)
    parser.add_argument('--scores', nargs='+', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    paths = [args.plan, *args.scores, Path(__file__), Path(score_module.__file__)]
    raw = {str(p.resolve()): p.read_bytes() for p in paths}
    plan = json.loads(raw[str(args.plan.resolve())])
    if plan.get('schema') != 'receipt-online-schedule-v1':
        raise ValueError('Actual scheduler plan required')
    records = [json.loads(raw[str(p.resolve())]) for p in args.scores]
    if any(r.get('schema') != 'issued-market-interval-score/v1' for r in records):
        raise ValueError('Identity-bound delayed score records required')
    result = summarize(plan['origins_ns'], records)
    result['input_and_source_sha256'] = {p: hashlib.sha256(b).hexdigest() for p, b in raw.items()}
    if any(Path(p).read_bytes() != b for p, b in raw.items()):
        raise ValueError('Aggregation input/source changed')
    with args.output.open('x') as stream:
        json.dump(result, stream, indent=2, allow_nan=False)


if __name__ == '__main__':
    main()
