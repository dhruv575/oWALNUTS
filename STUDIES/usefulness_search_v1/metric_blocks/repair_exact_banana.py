from pathlib import Path
import shutil
p=Path(__file__).resolve().parent;old=p/'exact_banana_runner/Cargo.toml';shutil.copy2(old,p/'local_recovery/exact_banana_build01/FAILED-Cargo.toml');old.write_text(old.read_text().replace('rand = "0.10"','rand = { version = "0.10", features = ["chacha"] }'));(p/'build_exact_banana_retry.py').write_text((p/'build_exact_banana.py').read_text().replace('exact_banana_build01','exact_banana_build02'))
