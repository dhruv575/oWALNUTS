from pathlib import Path
import shutil
p=Path(__file__).resolve().parent;failed=p/'local_recovery/cold_recycling_build01'
for name in ['cold_wal_original_runner','cold_wal_recycling_runner']:
    source=p/name/'src/main.rs';(failed/name).mkdir(exist_ok=True);shutil.copy2(source,failed/name/'FAILED-main.rs');text=source.read_text();assert 'unwrap_or(.9)' in text;source.write_text(text.replace('unwrap_or(.9)','unwrap_or(0.9)'))
(p/'build_cold_recycling_retry.py').write_text((p/'build_cold_recycling.py').read_text().replace('cold_recycling_build01','cold_recycling_build02'))
