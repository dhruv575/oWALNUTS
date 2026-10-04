"""Small predeclared access diagnosis, not a replacement market panel."""
import hashlib
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(ROOT))
from acquire_deribit_panel import Client, millis, write_new

protocol = json.loads((ROOT / 'DERIBIT_ACCESS_PROTOCOL.json').read_text())
protocol['limits'] = dict(requests_including_retries=18, raw_response_bytes=1000000,
                          requests_per_second=2, attempts_per_request=2, timeout_seconds=15)
queries = []
for day in ['2026-09-25', '2026-09-30', '2026-10-02', '2026-10-03']:
    lo = millis(day + 'T00:00:00+00:00')
    queries.append(dict(method='public/get_last_trades_by_currency_and_time',
                        params=dict(currency='BTC', kind='option', start_timestamp=lo,
                                    end_timestamp=lo+86400000-1, count=1, sorting='asc')))
# Same known instrument as the archived recent-access probe, selected without
# inspecting outcomes of these diagnostic requests.
for day in ['2026-09-25', '2026-10-03']:
    lo = millis(day + 'T00:00:00+00:00')
    queries.append(dict(method='public/get_last_trades_by_instrument',
                        params=dict(instrument_name='BTC-30OCT26-84000-P',
                                    start_timestamp=lo, end_timestamp=lo+86400000-1,
                                    count=1, sorting='asc')))
plan = dict(phase='access-diagnosis-only', qualified=False, queries=queries,
            collector_sha256=hashlib.sha256((ROOT/'acquire_deribit_panel.py').read_bytes()).hexdigest(),
            runner_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            scope='Six fixed probes; no fitting, universe selection, or completeness claim.')
write_new(HERE/'plan.json', plan)
write_new(HERE/'protocol.json', protocol)
client = Client(protocol, HERE)
rows = []
for i, query in enumerate(queries):
    try:
        result = client.request(query['method'], query['params'])
        trades = result.get('trades', [])
        rows.append(dict(index=i, status='completed', count=len(trades),
                         has_more=result.get('has_more'),
                         timestamps=[t.get('timestamp') for t in trades]))
    except Exception as exc:
        rows.append(dict(index=i, status='failed', error=f'{type(exc).__name__}: {exc}'))
write_new(HERE/'summary.json', dict(qualified=False, fit_ready=False, rows=rows,
                                    requests=client.requests, raw_bytes=client.bytes))
print(json.dumps(rows))
