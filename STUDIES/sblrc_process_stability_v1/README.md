# sblrc process stability diagnostic v1

Status: preregistered before execution. No diagnostic child has been launched.

## Question

WP35 observed one `sblrc` oWALNUTS subprocess end nonzero without stderr or a
raw result. This isolated study instruments model load, initialization,
evaluation, exact 1,000-warmup/1,000-retained sampling, result publication,
and explicit drop under one- and four-replica/thread configurations.

This is a process diagnostic only. Its seeds and outputs are not posterior
performance evidence, and evidence seed 90101 is forbidden. The fixed design
and classification rule are in `PREREGISTRATION.md` and `protocol.json`.

## Planned use

```powershell
cd STUDIES\sblrc_process_stability_v1
cargo build --release --locked
& 'C:\dev\owalnuts-wt\posteriordb-v6\STUDIES\posteriordb_bench_v6\.venv\Scripts\python.exe' .\run_stability.py run
& 'C:\dev\owalnuts-wt\posteriordb-v6\STUDIES\posteriordb_bench_v6\.venv\Scripts\python.exe' .\run_stability.py analyze
& 'C:\dev\owalnuts-wt\posteriordb-v6\STUDIES\posteriordb_bench_v6\.venv\Scripts\python.exe' .\checksums.py
```

The orchestrator verifies the frozen input hashes and forbidden seed before
launching children. It records every child once, including Windows return-code
forms, stdout/stderr, duration, raw-output existence, and durable heartbeat
history.
