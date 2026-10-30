import shutil
from pathlib import Path
p=Path(__file__).resolve().parent;r=p/'local_recovery/gp_wal_driver_test01';f=p/'test_gp_wal_driver.py';shutil.copy2(f,r/'test-original.py');f.write_text(f.read_text().replace('gp_wal_driver_test01','gp_wal_driver_test02').replace('warmup=100,draws=100','warmup=1100,draws=100'))
f=p/'run_gp_wal_calibration.py';f.write_text(f.read_text().replace('gp_wal_driver_test01','gp_wal_driver_test02'))
