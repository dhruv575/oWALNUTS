import json,sys
from pathlib import Path
import numpy as np
ROOT=Path('/dev/shm/bounded-init-20261030');MODELS=Path('/home/ubuntu/lanes/metric_autoselect_confirmation_v1/models');sys.path.insert(0,'/home/ubuntu/lanes/pharma-ode-logforecast-20261029/source');from resource_monitor import execute
assert all(r['exit_code']==0 for r in json.loads((ROOT/'BUILD.json').read_text())['steps']);out=ROOT/'preflight01';out.mkdir(exist_ok=False);rows=[]
for kind,arms in [('pdb',['defaults','custom_noop','gradinit','bounded']),('funnel',['gradinit','bounded'])]:
 for arm in arms:
  folder=out/(kind+'-'+arm);folder.mkdir();result=folder/'RESULT.json'
  if kind=='pdb':cmd=[str(ROOT/'target/release/pdb-cell'),str(MODELS/'earnings-logearn_interaction_model.so'),str(MODELS/'earnings-logearn_interaction.data.json'),arm,'939990001',str(result),'4']
  else:cmd=[str(ROOT/'target/release/funnel'),arm,'200','400','939990002',str(result)]
  r=execute(['taskset','-c','0-3',*cmd],str(ROOT),120,folder,2*1024**3,64*1024**2,folder/'worker.log',output_scan_interval=2);(folder/'SUPERVISION.json').write_text(json.dumps(r,indent=2)+'\n');assert r['exit_code']==0 and r['group_drained'];rows.append(dict(kind=kind,arm=arm))
def read(kind,arm):return json.loads((out/(kind+'-'+arm)/'RESULT.json').read_text())
a=read('pdb','defaults');b=read('pdb','custom_noop');assert a['starts']==b['starts'] and a['draw_hash']==b['draw_hash'] and a['target_calls_total']==b['target_calls_total'];assert [c['samples'] for c in a['chains_data']]==[c['samples'] for c in b['chains_data']]
checks=[]
for kind in ['pdb','funnel']:
 a=read(kind,'gradinit');b=read(kind,'bounded');key='chains_data' if kind=='pdb' else 'chains'
 for i,(u,v) in enumerate(zip(a[key],b[key])):
  actual=np.array(v['initial_mass_diagonal']);expected=np.clip(u['initial_mass_diagonal'],.1,1000.);assert np.array_equal(actual,expected);checks.append(dict(kind=kind,chain=i,min=float(actual.min()),max=float(actual.max())))
(ROOT/'PREFLIGHT.json').write_text(json.dumps(dict(passed=True,default_noop_exact=True,mass_checks=checks,jobs=rows),indent=2)+'\n');print('Preflight passed')
