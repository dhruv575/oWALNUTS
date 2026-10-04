from pathlib import Path
import json,hashlib,time,subprocess,sys
ROOT=Path(__file__).resolve().parents[5]; OUT=Path(__file__).resolve().parent; CAM=OUT.parent
read=lambda p:json.loads(Path(p).read_text())
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()
def save(p,x):
 with Path(p).open('x') as f:json.dump(x,f,indent=2,allow_nan=False)
tick=time.perf_counter();protocol=read(CAM/'protocol.json');plan=read(protocol['plan']);intent=read(protocol['decision_intent']);bindings={}
for mapping in [protocol['bindings'],plan['sources'],plan['bindings'],intent['sources'],intent['bindings']]:
 for path,h in mapping.items():
  if sha(path)!=h:raise ValueError('Frozen input drift: '+path)
  bindings[path]=h
cells={}
for c in plan['cells']:
 paths=[c[k] for k in ('fixture','controller_status','bank_plan','pilot_plan','analysis_intent','report','hardware')]
 paths+=list(Path(c['worker_directory']).glob('draws-*/*.json'))+list(Path(c['worker_directory']).glob('draws-*.json'))
 cells[c['id']]={str(Path(p).resolve()):sha(p) for p in paths if Path(p).is_file()};bindings.update(cells[c['id']])
manifest=OUT/'artifact-manifest.json';save(manifest,dict(plan_sha256=sha(protocol['plan']),cells=cells))
pin={k:intent[k] for k in ('pair_map','counts','bank_indices','bank_pin','target_sha256')}
pin.update(plan=protocol['plan'],terminal=str(CAM/'run-v1/terminal.json'),terminal_cost=str(CAM/'run-v1/terminal-cost.json'),artifact_manifest=str(manifest),study_directory=str(ROOT/'STUDIES/options_flow_v1'),adapter_paths=dict(public=str(ROOT/'target/posterior-bank-candidate-adapter/candidate_adapter.py'),reference=str(ROOT/'target/posterior-bank-candidate-controller/reference_adapter.py')))
for k in ('plan','terminal','terminal_cost','artifact_manifest','pair_map','counts','bank_indices','bank_pin'):bindings[pin[k]]=sha(pin[k])
for p in pin['adapter_paths'].values():
 if p not in bindings:raise ValueError('Adapter not preregistered: '+p)
for p in (CAM/'protocol.json',Path(protocol['decision_intent']),Path(__file__).resolve()):bindings[str(p)]=sha(p)
pin['bindings']=bindings;save(OUT/'analysis-pin.json',pin)
command=[plan['python'],str(ROOT/'target/posterior-bank-candidate-comparison/controller_transport.py'),'--pin',str(OUT/'analysis-pin.json'),'--out',str(OUT/'decision-result.json')]
save(OUT/'analysis-started.json',dict(command=command,pin_sha256=sha(OUT/'analysis-pin.json'),preparation_seconds=time.perf_counter()-tick))
with (OUT/'stdout.txt').open('x') as log:r=subprocess.run(command,stdout=log,stderr=subprocess.STDOUT)
save(OUT/'execution.json',dict(returncode=r.returncode,total_postfit_seconds=time.perf_counter()-tick,command=command,source_sha256=sha(__file__)))
sys.exit(r.returncode)
