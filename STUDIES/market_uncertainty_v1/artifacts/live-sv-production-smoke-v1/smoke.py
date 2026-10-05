"""Prepared synthetic integration only. No imports of numerical packages at admission."""
import argparse,hashlib,importlib.util,json,math,shutil,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
STUDY=ROOT/'STUDIES/market_uncertainty_v1'
H=1800_000_000_000; W=900_000_000_000
CHANNELS=['trades.option.BTC.100ms','ticker.BTC-PERPETUAL.agg2']
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(p,x):
 with Path(p).open('x',encoding='utf8') as f:json.dump(x,f,indent=2,allow_nan=False)
def load_module(name,path):
 s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
def envelope(t,message):return dict(receipt_monotonic_ns=t,receipt_utc_ns=1700000000000000000+t,connection=1,raw=json.dumps(message))
def quote(t,p):return envelope(t,dict(params=dict(channel=CHANNELS[1],data=dict(instrument_name='BTC-PERPETUAL',state='open',best_bid_price=p*.999999,best_ask_price=p*1.000001))))
def receipts():
 rows=[envelope(1,dict(id=1,result=CHANNELS))];price=100.
 for j in range(24):
  t=1+W+j*H
  price*=math.exp(.002*math.sin(j*1.37)+.001*math.cos(j*.71))
  trade=dict(trade_id=f'synthetic-{j}',instrument_name='BTC-30OCT26-100000-C',amount=1.+j%5,direction='buy' if j%3 else 'sell')
  rows.append(envelope(t-1_000_000_000,dict(params=dict(channel=CHANNELS[0],data=[trade]))));rows.append(quote(t,price))
 return rows

def prepare(out):
 out.mkdir(parents=True,exist_ok=False);capture=out/'capture';capture.mkdir();rows=receipts()
 (capture/'receipts.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in rows),encoding='utf8')
 (capture/'lifecycle.jsonl').write_text(json.dumps(dict(kind='subscribed',receipt_monotonic_ns=2,receipt_utc_ns=1700000000000000002,connection=1))+'\n',encoding='utf8')
 save(capture/'selection.json',dict(channels=CHANNELS,synthetic=True))
 package=(ROOT/'target/parallel-continuation-route-v1-worktree/integrations/python/python').resolve()
 python=(ROOT/'target/python-workflow-env/Scripts/python.exe').resolve()
 paths=list(STUDY.rglob('*.py'))+list((ROOT/'STUDIES/options_flow_v1').glob('*.py'))+[Path(__file__),python]+list(capture.iterdir())
 runtime={str(p.resolve()):sha(p) for p in (package/'owalnuts/__init__.py',package/'owalnuts/_owalnuts.pyd')}
 config=dict(schema='synthetic-sv-production-smoke-v1',status='prepared_not_authorized',synthetic_replay=True,maximum_attempts=1,maximum_lag_seconds=60,worker_cleanup_reserve_seconds=5,origin=rows[-1]['receipt_monotonic_ns'],capture=str(capture.resolve()),python=str(python),package=str(package),initialization_seed=1,sampler_seed=2,predictive_seed=3,runtime_bindings=runtime,bindings={str(p.resolve()):sha(p) for p in paths})
 save(out/'config.json',config)
 return config

def verify(c):
 if c['schema']!='synthetic-sv-production-smoke-v1' or c['maximum_attempts']!=1 or c['maximum_lag_seconds']!=60 or c['worker_cleanup_reserve_seconds']!=5:raise ValueError('Scope mismatch')
 for p,h in {**c['bindings'],**c['runtime_bindings']}.items():
  if sha(p)!=h:raise ValueError('Changed binding: '+p)
 if c['origin']!=1+W+23*H:raise ValueError('Origin mismatch')

def run(config_path,out):
 c=json.loads(config_path.read_text());verify(c);identity=sha(config_path);out.mkdir(parents=True,exist_ok=False)
 start=time.monotonic();result=dict(synthetic_replay=True,real_market_issuance=False,config_sha256=identity,status='started')
 try:
  issuer=load_module('production_smoke_issuer',STUDY/'sv_online_issuance/issue.py')
  scorer=load_module('production_smoke_scorer',STUDY/'sv_online_scoring/score.py')
  # Imports precede simulated arrival; actual issuance latency includes snapshot,
  # fixture generation, subprocess compile/warmup/draws/diagnostics and publish.
  base=time.monotonic_ns();origin=c['origin']
  clock=lambda:origin+time.monotonic_ns()-base
  utc=lambda:1700000000000000000+clock()
  issued=out/'issued';r=issuer.issue(Path(c['capture']),issued,origin,c,clock=clock,utc=utc)
  result['issuance']=r;result['issuance_elapsed_seconds']=(time.monotonic_ns()-base)/1e9
  # Separate later synthetic capture; original input prefix never mutated.
  later_capture=out/'later-capture';shutil.copytree(c['capture'],later_capture)
  last=json.loads(receipts()[-1]['raw'])['params']['data'];price=(last['best_bid_price']+last['best_ask_price'])/2
  with (later_capture/'receipts.jsonl').open('a',encoding='utf8') as f:f.write(json.dumps(quote(origin+H,price*math.exp(.0017)))+'\n')
  later=out/'later-prefix';prefix=issuer.snapshot.snapshot(later_capture,later)
  ih=sha(issued/'issuance.json');result['provisional']=scorer.score(issued,later,expected_issuance_sha256=ih,provisional=True)
  terminal=dict(prefix,schema='public-receipt-collector-v2',status='duration_complete',synthetic_terminal=True)
  save(later/'summary.json',terminal)
  result['terminal']=scorer.score(issued,later,expected_issuance_sha256=ih)
  result['status']='completed';result['integration_pass']=r['status']=='issued' and result['provisional']['scored'] and result['terminal']['scored'] and result['provisional']['observed_return']==result['terminal']['observed_return']
 except Exception as e:result.update(status='failed',error=repr(e),integration_pass=False)
 finally:
  try:
   verify(c)
   if sha(config_path)!=identity:raise ValueError('Config changed')
  except Exception as e:result.update(status='provenance_failed',error=repr(e),integration_pass=False)
  result['outer_elapsed_seconds']=time.monotonic()-start;save(out/'result.json',result)
 return result
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('action',choices=['prepare','admit','run']);p.add_argument('--config',type=Path);p.add_argument('--out',type=Path);a=p.parse_args()
 if a.action=='prepare':prepare(a.out)
 elif a.action=='admit':verify(json.loads(a.config.read_text()))
 else:run(a.config,a.out)
