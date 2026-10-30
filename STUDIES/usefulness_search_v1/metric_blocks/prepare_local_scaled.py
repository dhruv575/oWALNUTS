"""Prepare an immutable local adaptation; never change policy implementation."""
import hashlib,json,shutil,sys
from pathlib import Path

study=Path(__file__).resolve().parent
chunk=int(sys.argv[1]);assert 1<=chunk<=8
local=study/'local_recovery';inputs=local/'inputs'
assert json.loads((local/'compat01/SUMMARY.json').read_text())['passed']
root=local/f'localscaled{chunk:02d}';root.mkdir(exist_ok=False)
models=inputs/'models';models.mkdir(exist_ok=True)
for p in (inputs/'dependencies').iterdir():
    dest=models/p.name.split('-',1)[1]
    if dest.exists():assert dest.read_bytes()==p.read_bytes()
    else:shutil.copy2(p,dest)
for name in ['scaled_worker.py','scaled_policy.py','hybrid_gate.py','fisher_high_precision.py','selector.py','selector_full_shape.py','SCALED-VALIDATION.md','LOCAL-SCALED-VALIDATION.md']:
    shutil.copy2(study/name,root/name)
shutil.copy2(inputs/'resource_monitor.py',root/'resource_monitor.py')
source=(study/'run_scaled.py').read_text()
replacements={
"binary=root.parent/'model01/source/STUDIES/metric_autoselect_confirmation_v1/target/release/online'":"binary=root.parent/'inputs/online-binary'",
"models=Path('/home/ubuntu/lanes/metric_autoselect_confirmation_v1/models')":"models=root.parent/'inputs/models'",
"durable=Path('/home/ubuntu/lanes/metric-blocks-recovery-20261030/evidence')/root.name":"durable=root.parent/'durable'/root.name",
"durable.mkdir(exist_ok=False)":"durable.mkdir(parents=True,exist_ok=False)",
"root.parent/'fisher04/mpmath-1.3.0-py3-none-any.whl'":"root.parent/'inputs/mpmath-1.3.0-py3-none-any.whl'",
"assert json.loads((root.parent/'model01/BUILD.json').read_text())['exit_code']==0":"record(root/'LOCAL-SCALED-VALIDATION.md');record(root/'resource_monitor.py')",
"root.parent/'scaledport01/SUMMARY.json'":"root.parent.parent/'scaledport01/SUMMARY.json'",
"info=pdb/'posteriors'/f'{model}.json'":"info=models/f'{model}.json'",
"refpath=pdb/'reference_posteriors/draws/draws'/(json.loads(info.read_text())['reference_posterior_name']+'.json.zip')":"refpath=models/(json.loads(info.read_text())['reference_posterior_name']+'.json.zip')",
"929500001":"929600001","929500003":"929600003",
}
for old,new in replacements.items():
    assert old in source,old
    source=source.replace(old,new)
(root/'run_scaled.py').write_text(source)
verify=(study/'verify_scaled.py').read_text().replace("Path('/home/ubuntu/lanes/metric-blocks-recovery-20261030/evidence')/root.name","root.parent/'durable'/root.name")
(root/'verify_scaled.py').write_text(verify)
receipt=dict(chunk=chunk,parent_runner_sha256=hashlib.sha256((study/'run_scaled.py').read_bytes()).hexdigest(),replacements=replacements,sources={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in root.iterdir()})
(root/'LOCAL-ADAPTATION.json').write_text(json.dumps(receipt,indent=2)+'\n')
print(root)
