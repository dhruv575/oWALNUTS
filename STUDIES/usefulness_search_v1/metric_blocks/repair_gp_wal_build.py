import shutil
from pathlib import Path
p=Path(__file__).resolve().parent;r=p/'local_recovery/gp_wal_build01'
for name in ['gp_wal_pristine_runner','gp_wal_tuned_runner']:
    f=p/name/'Cargo.toml';shutil.copy2(f,r/(name+'-Cargo-original.toml'));f.write_text(f.read_text().replace('owalnuts = { path = "../../../.." }','owalnuts = { path = "../../../..", features = ["research"] }'))
f=p/'build_gp_wal.py';shutil.copy2(f,r/'build-original.py');f.write_text(f.read_text().replace('gp_wal_build01','gp_wal_build02'))
