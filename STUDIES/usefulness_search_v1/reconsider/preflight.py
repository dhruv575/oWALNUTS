import json,subprocess,os,sys
from pathlib import Path
root=Path('/dev/shm/reconsider-20261029');models=Path('/home/ubuntu/lanes/metric_autoselect_confirmation_v1/models')
sys.path.insert(0,'/home/ubuntu/lanes/pharma-ode-logforecast-20261029/source')
from resource_monitor import execute
out=root/'preflight';out.mkdir(exist_ok=False);results={}
for arm,window in [('auto2',2),('auto3',3),('reconsider',2)]:
 folder=out/arm;folder.mkdir();cmd=['env',f'STUDY_SELECT_WINDOW={window}','taskset','-c','0-3',str(root/'STUDIES/metric_autoselect_confirmation_v1/target/release/pdb'),str(models/'kidiq-kidscore_momhsiq_model.so'),str(models/'kidiq-kidscore_momhsiq.data.json'),'auto' if arm.startswith('auto') else arm,'926200002',str(folder/'RESULT.json'),'4']
 r=execute(cmd,str(root),120,folder,2*1024**3,64*1024**2,folder/'worker.log');(folder/'SUPERVISION.json').write_text(json.dumps(r,indent=2));assert r['exit_code']==0 and r['group_drained']
 results[arm]=json.loads((folder/'RESULT.json').read_text())
def decision(a):return results[a]['chains_data'][0]['dense_auto_select']
assert not decision('auto2')['chose_dense']
assert decision('auto3')['chose_dense'] and decision('auto3')['window_index']==3
assert decision('reconsider')==decision('auto3')
assert results['auto3']['target_calls_total']==results['reconsider']['target_calls_total']
for a,b in zip(results['auto3']['chains_data'],results['reconsider']['chains_data']):
 for key in ['samples','retained_work','warmup_work','metric_updates','draws_fnv']:assert a[key]==b[key],key
(out/'VERIFIED.json').write_text(json.dumps(dict(late_dense_matches_window3=True,early_rejected=True,excluded_from_evidence=True),indent=2)+'\n')
print('Late-dense path matches unconditional window 3 exactly')
