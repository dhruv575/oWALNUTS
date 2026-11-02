"""Summarize frozen runs without dropping failed or censored repetitions."""
import json
import statistics
import sys
from pathlib import Path

def summarize(root):
    rows = [json.loads(p.read_text()) for p in root.rglob('artifact/SUMMARY.json')]
    cells, ladders = [], []
    for case, engine in sorted({(r['case'], r['engine']) for r in rows}):
        subset = [r for r in rows if (r['case'], r['engine']) == (case, engine)]
        for draws in sorted({r['draws'] for r in subset}):
            values = [r for r in subset if r['draws'] == draws]
            cells.append(dict(case=case, engine=engine, draws=draws, runs=len(values),
                              passed=sum(r['summary']['passed'] for r in values),
                              divergences=sum(r['divergences'] for r in values),
                              median_kernel_seconds=statistics.median(r['kernel_seconds'] for r in values),
                              median_worker_seconds=statistics.median(r['worker_seconds'] for r in values)))
        for seed in sorted({r['seed'] for r in subset}):
            values = sorted([r for r in subset if r['seed'] == seed], key=lambda r: r['draws'])
            kernel = worker = 0.
            passed_budget = None
            for r in values:
                kernel += r['kernel_seconds']
                worker += r['worker_seconds']
                if r['summary']['passed']:
                    passed_budget = r['draws']
                    break
            ladders.append(dict(case=case, engine=engine, seed=seed,
                                first_passing_draws=passed_budget,
                                cumulative_kernel_seconds=kernel,
                                cumulative_worker_seconds=worker,
                                censored=passed_budget is None))
    return dict(fits=len(rows), cells=cells, ladders=ladders)

if __name__ == '__main__':
    root = Path(sys.argv[1])
    result = summarize(root)
    (root.parent / (root.name + '-ANALYSIS.json')).write_text(json.dumps(result, indent=2))
    print(json.dumps(result['cells'], indent=2))
