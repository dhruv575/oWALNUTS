import json,hashlib
from pathlib import Path
root=Path('target/equal-close-trades-20261028');report=json.loads((root/'REPORT.json').read_bytes());rows=[]
for j,old in enumerate(report['rows']):
 raw=(root/f'response-{j:02d}.json').read_bytes();assert hashlib.sha256(raw).hexdigest()==old['sha256']
 r=json.loads(raw)['result'];t=r['trades'];seq=[x['trade_seq'] for x in t]
 assert len(seq)==len(set(seq))
 assert all(old['start_ms']<=x['timestamp']<=old['end_ms'] and x['instrument_name']=='BTC-PERPETUAL' for x in t)
 ordered=sorted(t,key=lambda x:(x['timestamp'],x['trade_seq']))
 rows.append(dict(index=old['index'],count=len(t),has_more=r['has_more'],strict_sequence_descending=seq==sorted(seq,reverse=True),timestamps_descending=[x['timestamp'] for x in t]==sorted([x['timestamp'] for x in t],reverse=True),max_time_price=None if not t else ordered[-1]['price'],bar_close=old['bar_close'],close_match=None if not t else ordered[-1]['price']==old['bar_close'],bar_volume=old['bar_volume'],source_sha256=old['sha256']))
out=dict(scope='Read-only reanalysis of saved responses; incomplete intervals are not promoted to complete',rows=rows)
(root/'REANALYSIS.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out))
