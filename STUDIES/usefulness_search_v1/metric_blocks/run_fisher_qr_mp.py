import json,sys
from pathlib import Path
study=Path(__file__).resolve().parent;local=study/'local_recovery';root=local/'fisherqr01'
# The numerical timing experiment must not overlap the frozen sampler queue.
assert json.loads((local/'localscaled08_archive/VERIFICATION.json').read_text())['passed']
sys.path.insert(0,str(local/'inputs'))
from resource_monitor import execute
for script,label in [('test_fisher_qr_mp.py','ALGEBRA'),('test_fisher_qr_mp_models.py','MODELS')]:
    r=execute([sys.executable,str(root/script)],str(root),180,root,2*1024**3,64*1024**2,root/(label+'.log'),output_scan_interval=2)
    (root/(label+'-SUPERVISION.json')).write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(dict(stage=label,**r)),flush=True)
    if r['exit_code']!=0 or not r['group_drained']:break
