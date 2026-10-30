from pathlib import Path
p=Path(__file__).resolve().parent
w=(p/'momentum_timing_worker.py').read_text().replace(',timeout=180','')
(p/'momentum_timing_worker02.py').write_text(w)
runner=(p/'run_momentum_timing.py').read_text().replace('momentum_pool_timing01','momentum_pool_timing02').replace('momentum_timing_worker.py','momentum_timing_worker02.py').replace('MOMENTUM-POOL-TIMING-PROTOCOL.md','MOMENTUM-POOL-TIMING-REPAIR.md')
(p/'run_momentum_timing02.py').write_text(runner)
