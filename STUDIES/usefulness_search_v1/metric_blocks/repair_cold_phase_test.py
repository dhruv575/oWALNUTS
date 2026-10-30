import shutil
from pathlib import Path
p=Path(__file__).resolve().parent;failed=p/'local_recovery/cold_recycling_build02'
for name,ns in [('cold_wal_original_runner','measurement'),('cold_wal_recycling_runner','owalnuts')]:
    source=p/name/'src/main.rs';(failed/name).mkdir(exist_ok=True);shutil.copy2(source,failed/name/'FAILED-main.rs');text=source.read_text();a='reset(true);set_dense_lower(&[2.,0.,1.,3.]);';assert a in text;text=text.replace(a,'reset(true);assert!(features(&[0.,-6.]).is_empty());'+ns+'::recycling::set_retained_phase(true);set_dense_lower(&[2.,0.,1.,3.]);');source.write_text(text)
    binary=Path('/home/dhruv/.cache/owalnuts/native-recycling01/release')/name.replace('_','-')
    if binary.exists():shutil.copy2(binary,failed/name/'FAILED-runner')
(p/'build_cold_recycling_phase_retry.py').write_text((p/'build_cold_recycling_retry.py').read_text().replace('cold_recycling_build02','cold_recycling_build03'))
