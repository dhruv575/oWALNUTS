import bisect,hashlib,importlib.util,json,math,time
from pathlib import Path
root=Path(__file__).resolve().parents[2];source=root/'STUDIES/market_uncertainty_v1/marked_flow/features.py';spec=importlib.util.spec_from_file_location('marked',source);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
a=root/'target/market-history-acquisition-v1/september-development-v1';f=root/'target/historical-baseline-evaluation-v1/run-v1/features.json';out=Path(__file__).resolve().parent/'conservation-v2.json'
paths=[source,f,a/'trades.jsonl',a/'completed-trade-leaves.json',a/'terminal.json'];sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest();pins={str(p):sha(p) for p in paths};start=time.perf_counter()
frozen=root/'target/sv-historical-rolling-v1/prepared/config-frozen.json'
assert sha(frozen)=='157099f8d444247b42b6ddc8b96a69115f6a6f9f8d31eb79a975ff373b55b75c'
bound={str(Path(k).resolve()).lower():v for k,v in json.loads(frozen.read_text())['bindings'].items()}
assert all(bound[str(p.resolve()).lower()]==sha(p) for p in paths if p!=source)
pins[str(frozen)]=sha(frozen)
terminal=json.loads((a/'terminal.json').read_text());assert terminal['complete'] and terminal['status']=='completed'
trades=[json.loads(x) for x in (a/'trades.jsonl').read_text().splitlines()];trades.sort(key=lambda x:x['timestamp']);ts=[x['timestamp'] for x in trades]
# Collector leaf endpoints are inclusive; convert to the builder's half-open contract.
coverage=[(x['start_ms'],x['end_ms']+1) for x in json.loads((a/'completed-trade-leaves.json').read_text())]
rows=json.loads(f.read_text())['rows'];errors=[];maximum={'amount':0.,'signed_amount':0.};exact=0
for r in rows:
 o=r['origin_ms'];batch=trades[bisect.bisect_left(ts,o-900000):bisect.bisect_left(ts,o)];v=m.build(batch,o,coverage_intervals=coverage)
 diffs={k:abs(v[k]-r[old]) for k,old in [('amount','total_amount'),('signed_amount','signed_amount')]}
 for k,d in diffs.items():maximum[k]=max(maximum[k],d)
 exact+=all(d==0 for d in diffs.values())
 if v['count']!=r['flow_count'] or not r['flow_known'] or any(not math.isclose(v[k],r[old],rel_tol=1e-12,abs_tol=1e-12) for k,old in [('amount','total_amount'),('signed_amount','signed_amount')]):errors.append(dict(origin_ms=o,differences=diffs))
assert all(sha(Path(p))==h for p,h in pins.items())
result=dict(windows=len(rows),passed=not errors,errors=errors,exact_amount_pairs=exact,max_absolute_difference=maximum,source_input_sha256=pins,script_sha256=sha(Path(__file__)),seconds=time.perf_counter()-start,scope='Audit only, no fitting. Coverage from previously verified complete inclusive acquisition leaves, explicitly converted to half-open endpoints. Bucketwise fsum can differ from direct pooled fsum by floating-point regrouping; tolerance1e-12 absolute/relative.')
with out.open('x') as stream:json.dump(result,stream,indent=2)
print(json.dumps({k:v for k,v in result.items() if k not in ('source_input_sha256',)}))
