import json,hashlib,statistics,collections
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];OUT=Path(__file__).resolve().parent;RUN=ROOT/'STUDIES/options_flow_v1/artifacts/fresh-paired-comparison-v1/run-v1'
read=lambda p:json.loads(p.read_text());sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
terminal=read(RUN/'terminal.json');rows=[];bindings={str(RUN/'terminal.json'):sha(RUN/'terminal.json')}
for entry in terminal['outcomes']:
 cid=entry['controller']['id'];arm=cid.split('-')[-1];folder=RUN/cid;report_path=folder/('python-pymc-flow-report.json' if arm=='public' else 'report.json');report=read(report_path);events_path=folder/'phase-events.jsonl';events=[json.loads(x) for x in events_path.read_text().splitlines()];stages=collections.defaultdict(float);starts={}
 for e in events:
  key=(e['stage'],e['draws'])
  if e['event']=='start':assert key not in starts;starts[key]=e['seconds']
  elif e['event']=='end':stages[e['stage']]+=e['seconds']-starts.pop(key)
 assert not starts
 raw=list(folder.glob('draws-*/*raw.json'))+list(folder.glob('draws-*-raw.json'))
 row=dict(id=cid,arm=arm,draws=report['draws'],full_seconds=entry['full_cell_seconds'],worker_seconds=report['end_to_end_seconds'],controller_postprocessing_seconds=entry['postprocessing_seconds'],stages=dict(stages),raw_bytes=sum(p.stat().st_size for p in raw),raw_files=len(raw),tiers=[a['draws'] for a in report['attempts']]);row['other_seconds']=row['full_seconds']-sum(stages.values());rows.append(row)
 for p in [report_path,events_path]:bindings[str(p)]=sha(p)
summary={}
for arm in ['public','reference']:
 a=[r for r in rows if r['arm']==arm];keys=set(k for r in a for k in r['stages']);summary[arm]=dict(count=len(a),draw_counts=dict(collections.Counter(r['draws'] for r in a)),full_seconds=sum(r['full_seconds'] for r in a),stage_seconds={k:sum(r['stages'].get(k,0) for r in a) for k in sorted(keys)},other_seconds=sum(r['other_seconds'] for r in a),controller_postprocessing_seconds=sum(r['controller_postprocessing_seconds'] for r in a),raw_bytes=sum(r['raw_bytes'] for r in a),raw_files=sum(r['raw_files'] for r in a))
result=dict(scope='Posthoc saved-report phase attribution, not a new controlled benchmark',summary=summary,rows=rows,bindings=bindings)
with (OUT/'phase-summary.json').open('x') as f:json.dump(result,f,indent=2)
print(json.dumps(summary,indent=2))
