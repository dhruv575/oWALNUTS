"""Admission-only tests; no numerical imports or sampler execution."""
import json
import pytest
import smoke

def test_synthetic_clock_grid_and_small_returns():
 rows=smoke.receipts();quotes=[r for r in rows if json.loads(r['raw']).get('params',{}).get('channel')==smoke.CHANNELS[1]]
 assert len(quotes)==24
 assert [r['receipt_monotonic_ns'] for r in quotes]==[1+smoke.W+i*smoke.H for i in range(24)]
 assert all(a['receipt_monotonic_ns']<b['receipt_monotonic_ns'] for a,b in zip(rows,rows[1:]))
 prices=[json.loads(r['raw'])['params']['data']['best_bid_price'] for r in quotes]
 assert all(abs(smoke.math.log(b/a))<.004 for a,b in zip(prices,prices[1:]))

def test_binding_mutation_and_scope_fail_closed(tmp_path):
 f=tmp_path/'source';f.write_text('original')
 c=dict(schema='synthetic-sv-production-smoke-v1',maximum_attempts=1,maximum_lag_seconds=60,worker_cleanup_reserve_seconds=5,origin=1+smoke.W+23*smoke.H,bindings={str(f):smoke.sha(f)},runtime_bindings={})
 smoke.verify(c);f.write_text('changed')
 with pytest.raises(ValueError,match='Changed binding'):smoke.verify(c)
 c['maximum_attempts']=2
 with pytest.raises(ValueError,match='Scope'):smoke.verify(c)

def test_actual_receipt_feature_and_reconciliation_contract(tmp_path):
 # Production stdlib snapshot/features only; never import issuer or a sampler.
 snapshot=smoke.load_module('smoke_snapshot_admission',smoke.STUDY/'live_snapshot/snapshot.py')
 features=smoke.load_module('smoke_features_admission',smoke.STUDY/'receipt_features/features.py')
 capture=tmp_path/'capture';capture.mkdir();rows=smoke.receipts()
 (capture/'receipts.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in rows))
 (capture/'lifecycle.jsonl').write_text(json.dumps(dict(kind='subscribed',receipt_monotonic_ns=2,receipt_utc_ns=1700000000000000002,connection=1))+'\n')
 smoke.save(capture/'selection.json',dict(channels=smoke.CHANNELS))
 prefix=snapshot.snapshot(capture,tmp_path/'prefix')
 origin=rows[-1]['receipt_monotonic_ns'];origins=[1+smoke.W+j*smoke.H for j in range(24)]
 data=features.build(rows,origins_ns=origins,**features.collector_context(prefix))
 assert len(data['rows'])==24 and all(r['features']['flow_known'] for r in data['rows'])
 assert all(r['features']['observed_trade_count']==1 and r['features']['anchor']['available'] for r in data['rows'])
 assert sum(r['label']['observed'] for r in data['rows'])==23
 assert data['rows'][-1]['label']['observed'] is False
 # First row lacks lag; remaining 22 mature rows exceed minimum history 20.
 assert sum(r['label']['observed'] for r in data['rows'][1:-1])==22
 with (capture/'receipts.jsonl').open('a') as f:f.write(json.dumps(smoke.quote(origin+smoke.H,101.))+'\n')
 later=snapshot.snapshot(capture,tmp_path/'later')
 smoke.save(tmp_path/'later/summary.json',dict(later,schema='public-receipt-collector-v2',status='duration_complete',synthetic_terminal=True))
 assert not snapshot.reconcile(tmp_path/'prefix/prefix-summary.json',tmp_path/'later/summary.json')['requires_rebuild']
 later_rows=[json.loads(line) for line in (capture/'receipts.jsonl').read_text().splitlines()]
 rebuilt=features.build(later_rows,origins_ns=[origin],**features.collector_context(later))['rows'][0]
 assert rebuilt['features']==data['rows'][-1]['features'] and rebuilt['label']['observed']
