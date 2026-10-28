import hashlib,json,time,urllib.request,urllib.error,sys
from pathlib import Path
sys.path.insert(0,'STUDIES/amm_accounting_v1')
from liquidity_probe import START,PAIR,ENDPOINT,topic
root=Path('target/amm-liquidity-filter-diagnostic-20261028');root.mkdir(exist_ok=False)
filters=[None,[[topic('Mint(address,uint256,uint256)'),topic('Burn(address,uint256,uint256,address)')]],[topic('Mint(address,uint256,uint256)')],[topic('Burn(address,uint256,uint256,address)')]]
plan=dict(scope='Four fixed transport diagnostics; not independent scientific replications',start=START,end=START+255,filters=filters,max_requests=4,timeout_seconds=10,max_response_bytes=2097152,minimum_interval_seconds=.25,retries=0,source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
(root/'PLAN.json').write_text(json.dumps(plan,indent=2));rows=[]
class NoRedirect(urllib.request.HTTPRedirectHandler):
 def redirect_request(self,*args,**kwargs):return None
for i,topics in enumerate(filters):
 params=dict(address=PAIR,fromBlock=hex(START),toBlock=hex(START+255))
 if topics is not None:params['topics']=topics
 call=dict(jsonrpc='2.0',id=i+1,method='eth_getLogs',params=[params]);raw=json.dumps(call).encode();(root/f'{i}-request.json').write_bytes(raw)
 try:
  req=urllib.request.Request(ENDPOINT,data=raw,headers={'Content-Type':'application/json'})
  try:
   with urllib.request.build_opener(NoRedirect).open(req,timeout=10) as r:body=r.read(2097153);status=r.status
  except urllib.error.HTTPError as e:body=e.read(2097153);status=e.code
  (root/f'{i}-response.bin').write_bytes(body)
  if len(body)>2097152:raise ValueError('Response cap')
  data=json.loads(body);assert data.get('id')==i+1
  rows.append(dict(index=i,http=status,error=data.get('error'),logs=len(data['result']) if isinstance(data.get('result'),list) else None))
 except Exception as e:rows.append(dict(index=i,error=repr(e)))
 time.sleep(.25)
(root/'FINAL.json').write_text(json.dumps(rows,indent=2));print(json.dumps(rows))
