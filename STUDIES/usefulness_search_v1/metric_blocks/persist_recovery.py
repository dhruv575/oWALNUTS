import json,shutil
from pathlib import Path
base=Path('/home/ubuntu/lanes/metric-blocks-recovery-20261030');root=base/'work/audit';dest=base/'evidence/recovered-artifacts';dest.mkdir(exist_ok=False)
for name in ['analysis01','analysis02','curvature01']:shutil.copytree(root/name,dest/name)
for p in root.glob('*.json'):shutil.copy2(p,dest/p.name)
print(json.dumps(dict(persisted=str(dest),bytes=sum(p.stat().st_size for p in dest.rglob('*') if p.is_file()))))
