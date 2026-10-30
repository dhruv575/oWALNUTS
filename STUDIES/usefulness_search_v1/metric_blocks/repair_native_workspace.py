import shutil
from pathlib import Path
study=Path(__file__).resolve().parent;local=study/'local_recovery';p=local/'native_pristine_source01';shutil.copytree(local/'native_source01/nuts-rs-0.18.3',p)
manifest=p/'Cargo.toml';manifest.write_text(manifest.read_text()+'\n[workspace]\n')
manifest=study/'native_pristine_runner/Cargo.toml';manifest.write_text(manifest.read_text().replace('../local_recovery/native_source01/nuts-rs-0.18.3','../local_recovery/native_pristine_source01'))
s=(study/'build_native_recycling.py').read_text().replace('native_recycling_build01','native_recycling_build02').replace('cache.mkdir(exist_ok=False)','cache.mkdir(exist_ok=True)')
(study/'build_native_recycling_retry.py').write_text(s)
