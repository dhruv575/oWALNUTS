import hashlib,json,sys
from pathlib import Path
import numpy as np
import bridgestan as bs
from scaled_policy import prepare
root=Path(__file__).resolve().parent;work=root.parent;parent=work/'hybrid02';prefix='sblrc-blr-929300005'
sys.path.insert(0,'/home/ubuntu/lanes/pharma-ode-logforecast-20261029/source')
from resource_monitor import execute
pilot=parent/'runs'/(prefix+'-pilot')/'RESULT.json';x=np.asarray(json.loads(pilot.read_text())['draws'])
args=json.loads((parent/'runs'/(prefix+'-v4')/'INPUT.json').read_text())
binary=work/'model01/source/STUDIES/metric_autoselect_confirmation_v1/target/release/online'
target=bs.StanModel(args['model'],data=Path(args['data']).read_text(),seed=1)
class Counted:
    def __init__(self):self.calls=0
    def log_density_gradient(self,q):self.calls+=1;return target.log_density_gradient(q)
rows=[]
for policy,original in [('hybrid',parent/'runs'/(prefix+'-hybrid')/'RESULT.json'),('scaled',work/'scalerepair01/runs/929300005/RESULT.json')]:
    counted=Counted();detail=prepare(x,counted,policy);assert counted.calls==detail['calls']==784
    folder=root/policy;folder.mkdir(exist_ok=False)
    inp=dict(policy=policy,pilot=str(pilot),sampler=args,binary=str(binary))
    (folder/'INPUT.json').write_text(json.dumps(inp,indent=2)+'\n')
    sup=execute([sys.executable,str(root/'scaled_worker.py'),str(folder/'INPUT.json'),str(folder/'RESULT.json')],str(root),180,
        folder,2*1024**3,64*1024**2,folder/'worker.log',output_scan_interval=2)
    (folder/'SUPERVISION.json').write_text(json.dumps(sup,indent=2)+'\n');assert sup['exit_code']==0 and sup['group_drained']
    a=json.loads((folder/'RESULT.json').read_text());b=json.loads(original.read_text())
    same={k:v for k,v in a.items() if k!='seconds'}=={k:v for k,v in b.items() if k!='seconds'}
    rows.append(dict(policy=policy,passed=same,actual_extra_calls=counted.calls,original=str(original),original_sha256=hashlib.sha256(original.read_bytes()).hexdigest(),supervised_invocation_seconds=sup['elapsed_seconds']))
result=dict(passed=all(r['passed'] for r in rows),rows=rows,sources={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in root.glob('*.py')})
(root/'SUMMARY.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result));assert result['passed']
