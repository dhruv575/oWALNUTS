# sblrc process stability diagnostic v1 — silent fault reproduced during drop

Status: preregistered in commit `44e42e9` before implementation or execution;
the instrumented harness was committed as `8e18e50` before execution. The
fixed 46-child matrix is complete.

## Question

WP35 observed one `sblrc` oWALNUTS subprocess end nonzero without stderr or a
raw result. This isolated study instruments model load, initialization,
evaluation, exact 1,000-warmup/1,000-retained sampling, result publication,
and explicit drop under one- and four-replica/thread configurations.

This is a process diagnostic only. Its seeds and outputs are not posterior
performance evidence, and evidence seed 90101 was forbidden and was not run.
The fixed design and classification rule are in `PREREGISTRATION.md` and
`protocol.json`.

## Verdict

**The process fault reproduced in one of 46 preregistered diagnostic
children.** The failing child was `sample-r4-t4-990603`: four replicas, four
threads, four chains, and exactly 1,000 warmup plus 1,000 retained transitions
per chain.

- Sampling completed and the raw result was durably written. It contains all
  4,000 retained draws as observed, all finite, after 146,627 target calls.
- Atomic heartbeats completed through `sampling/after` and
  `result_write/after`. The final event was `drop/before`; `drop/after` and
  `process/complete` were absent.
- The child then exited with raw/unsigned code `3221226356`, signed 32-bit
  `-1073740940`, hexadecimal `0xC0000374` (`STATUS_HEAP_CORRUPTION`), after
  3.313 seconds. Captured stdout and stderr were both empty, so this is a
  silent failure under the frozen rule.
- The other 45 children succeeded. This includes every standalone and
  in-process repeated load/drop child, every evaluation child, all three
  one-replica/thread sampling children, and two of three four-replica/thread
  sampling children.

The heartbeat narrows the observed failure to the explicit target
destruction/unload span after completed sampling and result publication. It
does not establish which destructor, library, or prior operation corrupted
the heap, so the root cause remains **not established**. No child was rerun.

Full process records, immutable heartbeat events, raw outputs, stdout/stderr,
the matrix table, and the machine-readable verdict are under `artifacts/`.

## Matrix result

| mode | configuration | result |
|---|---|---:|
| one load/drop | 1 replica / 1 thread | 12/12 succeeded |
| one load/drop | 4 replicas / 4 threads | 12/12 succeeded |
| evaluation | 1 replica / 1 thread | 6/6 succeeded |
| evaluation | 4 replicas / 4 threads | 6/6 succeeded |
| exact sampling | 1 replica / 1 thread / 1 chain | 3/3 succeeded |
| exact sampling | 4 replicas / 4 threads / 4 chains | 2/3 succeeded; 1 silent drop-span fault |
| 20 in-process load/drop cycles | 1 replica / 1 thread | 2/2 succeeded |
| 20 in-process load/drop cycles | 4 replicas / 4 threads | 2/2 succeeded |

Durations are retained only as hang/timeout diagnostics, not performance
evidence. No child timed out and no raw output was missing.

## Reproduce

```powershell
cd STUDIES\sblrc_process_stability_v1
cargo +1.88.0-x86_64-pc-windows-gnu fmt -- --check
cargo +1.88.0-x86_64-pc-windows-gnu check --locked
cargo +1.88.0-x86_64-pc-windows-gnu test --locked
python -m unittest -v test_run_stability.py
cargo +1.88.0-x86_64-pc-windows-gnu build --release --locked
& 'C:\dev\owalnuts-wt\posteriordb-v6\STUDIES\posteriordb_bench_v6\.venv\Scripts\python.exe' .\run_stability.py run
& 'C:\dev\owalnuts-wt\posteriordb-v6\STUDIES\posteriordb_bench_v6\.venv\Scripts\python.exe' .\run_stability.py analyze
& 'C:\dev\owalnuts-wt\posteriordb-v6\STUDIES\posteriordb_bench_v6\.venv\Scripts\python.exe' .\checksums.py
```

The orchestrator verifies the frozen input hashes and forbidden seed before
launching children. It records every child once, including Windows return-code
forms, stdout/stderr, duration, raw-output existence, and durable heartbeat
history. Existing launch markers prevent result-driven reruns.

The machine's default MSVC Rust target could not link because `link.exe` is
not installed. This was a build-environment issue, not a diagnostic result;
the installed Windows-GNU Rust 1.88 toolchain used by WP35 passed formatting,
check, and tests and built the executed release harness.
