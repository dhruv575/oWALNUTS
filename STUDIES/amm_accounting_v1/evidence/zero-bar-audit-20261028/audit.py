import json,sys,hashlib
from pathlib import Path
base=Path('/home/ubuntu/lanes/rolling-market-nutpie-20261028')
sys.path.insert(0,str(base/'source'))
from rolling_market_worker import validate
_,parent=validate(base/'run01/PLAN.json')
sys.path.insert(0,str(Path(parent['worker_path']).parent));sys.path.append(parent['e62_root'])
import data_contract
for m in parent['months']:
 data_contract.configure(m['month']);data_contract.load_sealed(parent['acquisition'],m['month'])
p=Path(parent['acquisition']['directory'])/'bars.json'
bars=json.loads(p.read_bytes())
zero=[]
for i in range(1,len(bars)):
 if bars[i]['close']==bars[i-1]['close']:
  zero.append(dict(index=i,previous=bars[i-1],current=bars[i]))
result=dict(scope='Existing sealed 96-day panel; exact equal adjacent closes, not a new acquisition',bars_sha256=hashlib.sha256(p.read_bytes()).hexdigest(),bars=len(bars),zero_volume_bars=sum(b['volume']==0 for b in bars),equal_close_pairs=len(zero),equal_close_zero_volume=sum(r['current']['volume']==0 for r in zero),pairs=zero,source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
out=Path('/home/ubuntu/lanes/zero-bar-audit-20261028.json')
with out.open('x') as f:json.dump(result,f,indent=2);f.write('\n')
print(json.dumps({k:v for k,v in result.items() if k!='pairs'}))
