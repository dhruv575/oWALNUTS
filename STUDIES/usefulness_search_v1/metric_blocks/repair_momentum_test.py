import shutil,re
from pathlib import Path
p=Path(__file__).resolve().parent;repo=p.parents[2];s=p/'local_recovery/momentum_pool_source01';failed=p/'local_recovery/momentum_pool_test01'
shutil.copy2(s/'Cargo.toml',failed/'Cargo-original.toml');shutil.copy2(p/'test_momentum_pool.py',failed/'test-original.py')
with (s/'Cargo.toml').open('a') as f:f.write('\n[dev-dependencies]\nserde_json = "1"\n')
for code in (s/'src').rglob('*.rs'):
    for relative in re.findall(r'include_str!\("([^"]+)"\)',code.read_text()):
        dest=(code.parent/relative).resolve()
        if not dest.exists():
            origin=repo/dest.relative_to(s.resolve());dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(origin,dest)
q=p/'test_momentum_pool.py';q.write_text(q.read_text().replace("r=l/'momentum_pool_test01'","r=l/'momentum_pool_test02'"))
