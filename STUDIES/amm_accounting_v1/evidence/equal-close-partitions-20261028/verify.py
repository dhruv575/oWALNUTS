import json,hashlib
from decimal import Decimal
from pathlib import Path
r=Path('target/equal-close-partitions-20261028');old=Path('STUDIES/amm_accounting_v1/evidence/equal-close-trades-20261028')
report=json.loads((r/'REPORT.json').read_bytes());bars=json.loads((old/'INPUT.json').read_bytes())['pairs'];rows=[]
for idx in [2289,4114]:
 parts=[x for x in report['rows'] if x['index']==idx];assert len(parts)==6
 trades=[]
 for p in parts:
  assert p['status']=='observed' and not p['has_more']
  raw=(r/f"{idx}-{p['part']}-response.json").read_bytes();assert hashlib.sha256(raw).hexdigest()==p['sha256']
  trades.extend(json.loads(raw,parse_float=Decimal)['result']['trades'])
 assert len({t['trade_seq'] for t in trades})==len(trades)
 pair=next(x for x in bars if x['index']==idx);bar=pair['current']
 t=sorted(trades,key=lambda x:(x['timestamp'],x['trade_seq']));prices=[x['price'] for x in t]
 ohlc=dict(open=prices[0],close=prices[-1],high=max(prices),low=min(prices))
 volume=sum(Decimal(x['amount'])/Decimal(x['price']) for x in t)
 original=json.loads((old/f"response-{0 if idx==2289 else 7:02d}.json").read_bytes(),parse_float=Decimal)['result']['trades']
 lookup={x['trade_seq']:x for x in t};assert all(lookup[x['trade_seq']]==x for x in original)
 rows.append(dict(index=idx,trades=len(t),original_1000_exact_subset=True,ohlc={k:str(v) for k,v in ohlc.items()},matches={k:v==Decimal(str(bar[k])) for k,v in ohlc.items()},volume=str(volume),volume_residual=str(volume-Decimal(str(bar['volume'])))))
out=dict(scope='Twelve fixed partitions all service-reported complete; original full-interval responses exact subsets',rows=rows)
(r/'RECONCILIATION.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out))
