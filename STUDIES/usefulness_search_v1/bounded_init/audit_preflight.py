import json,sys
from pathlib import Path
import numpy as np
ROOT=Path('/dev/shm/bounded-init-20261030');MODELS=Path('/home/ubuntu/lanes/metric_autoselect_confirmation_v1/models');sys.path.insert(0,'/home/ubuntu/lanes/pharma-ode-logforecast-20261029/source');from resource_monitor import execute
out=ROOT/'preflight01';rows=[dict(kind=kind,arm=arm) for kind,arms in [('pdb',['defaults','custom_noop','gradinit','bounded']),('funnel',['gradinit','bounded'])] for arm in arms]
for row in rows:
 r=json.loads((out/(row['kind']+'-'+row['arm'])/'SUPERVISION.json').read_text());assert r['exit_code']==0 and r['group_drained']
def read(kind,arm):return json.loads((out/(kind+'-'+arm)/'RESULT.json').read_text())
a=read('pdb','defaults');b=read('pdb','custom_noop');assert a['starts']==b['starts'] and a['draw_hash']==b['draw_hash'] and a['target_calls_total']==b['target_calls_total'];assert [c['samples'] for c in a['chains_data']]==[c['samples'] for c in b['chains_data']]
checks=[]
for kind in ['pdb','funnel']:
 a=read(kind,'gradinit');b=read(kind,'bounded');key='chains_data'
 for i,(u,v) in enumerate(zip(a[key],b[key])):
  actual=np.array(v['initial_mass_diagonal']);expected=np.clip(u['initial_mass_diagonal'],.1,1000.);assert np.array_equal(actual,expected);checks.append(dict(kind=kind,chain=i,min=float(actual.min()),max=float(actual.max())))
(ROOT/'PREFLIGHT.json').write_text(json.dumps(dict(passed=True,default_noop_exact=True,mass_checks=checks,jobs=rows),indent=2)+'\n');print('Preflight passed')
