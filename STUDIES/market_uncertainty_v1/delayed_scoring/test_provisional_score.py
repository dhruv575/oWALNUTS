import json
import pytest
from test_score import case,write,HORIZON
from provisional_score import score,snapshot

def later(tmp_path,missing=False):
 i,c,_,_=case(tmp_path,missing=missing)
 if missing:
  # An unrelated later receipt establishes capture progress, not a quote.
  with (c/'receipts.jsonl').open('a') as f:f.write(json.dumps(dict(receipt_monotonic_ns=2*HORIZON,receipt_utc_ns=2*HORIZON+1000,connection=1,raw='{}'))+'\n')
 p=tmp_path/'later';snapshot.snapshot(c,p)
 return i,p

def test_provisional_score_is_distinct_and_original_unchanged(tmp_path):
 i,p=later(tmp_path);before=(i/'issuance.json').read_bytes();r=score(i,p)
 assert r['provisional'] and r['final_reconciliation_required']
 assert r['schema']!='issued-market-interval-score/v1'
 assert all(o['status']=='scored' for o in r['outcomes'])
 assert (i/'issuance.json').read_bytes()==before

def test_late_gap_withdraws_and_tamper_rejects(tmp_path):
 i,p=later(tmp_path);s=json.loads((p/'prefix-summary.json').read_text())
 s['gaps']=[dict(start_monotonic_ns=HORIZON-1,detected_monotonic_ns=HORIZON+10)]
 write(p/'prefix-summary.json',s)
 assert all(o['status']=='invalidated_receipt_coverage' for o in score(i,p)['outcomes'])
 with (p/'receipts.jsonl').open('ab') as f:f.write(b'\n')
 with pytest.raises(ValueError,match='identity'):score(i,p)

def test_missing_label_and_immature_prefix(tmp_path):
 i,p=later(tmp_path,missing=True)
 assert all(o['status']=='outcome_unavailable' for o in score(i,p)['outcomes'])
 s=json.loads((p/'prefix-summary.json').read_text());s['end_monotonic_ns']=HORIZON
 write(p/'prefix-summary.json',s)
 with pytest.raises(ValueError,match='horizon'):score(i,p)
