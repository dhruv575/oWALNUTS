# WP50 — Windows-GNU BridgeStan heap-corruption root cause

Status: complete. The preregistration (`PREREGISTRATION.md`, `protocol.json`)
was committed at `c4f3fcbb` before any evidence child ran. All 300 frozen
children ran once each, in order, and none was rerun. This is a process
diagnostic, not posterior evidence.

## Verdict

**Root cause not established. No hypothesis is supported, and H1 as stated,
H2 and H3 are refuted.** The fault did not reproduce: **0 of 300** evidence
children and 0 of about 295 calibration children exited with `0xC0000374`.
That includes the 60-child baseline built to match the reproducing
comparator. Under the frozen rule, no hypothesis can be supported on empirical
grounds.

The static audits and the prior-study evidence still narrow the mechanism:

- **H1 as stated (an emutls autodiff-stack destructor runs after
  `FreeLibrary`): refuted.**
  - The faulting non-threads build has no `STAN_THREADS` thread-local
    autodiff stack (`artifacts/h4-build-symbols.txt`).
  - The reproducing studies already kept the DLLs resident and already joined
    their workers before teardown, and they still faulted 8/180 and 16/180.
  - Here, the resident and unload arms both scored 0/60, so there is no
    difference in either direction.
- **H2 (allocator mismatch): refuted** by the boundary audit
  (`artifacts/h2-boundary-audit.md`). Every DLL allocation (error strings, the
  model) is freed by the DLL's own deallocator, and Rust never frees a
  DLL-owned pointer.
- **H3 (owned-worker drop order): refuted** by the drop-order audit
  (`artifacts/h3-drop-order-audit.md`).
  - The model is destructed once, on the owner thread, before the library is
    released, and the owner thread is always joined.
  - No RNG object exists, and no aliased handle to the model exists.
  - Empirically, the owned arm here scored 0/120, and the prior study scored
    0/540.
- **H4 (`STAN_THREADS` build): no effect observed.** The threads build scored
  0/30 and its no-threads control scored 0/30. The threads build only adds
  more per-thread emutls state; the faulting build is the non-threads one.

**Narrowed mechanism (not proven).** The non-threads build does have three
kinds of per-thread native state:

- a process-global map from `std::thread::id` to an autodiff stack;
- C++ exception-handling globals reached through mingw emulated TLS
  (`__cxa_get_globals` / `get_global`);
- libwinpthread `pthread_key` destructors, which mingw TLS callbacks run at
  every OS-thread exit.

That matches the earlier crash signatures: `ntdll` `0xC0000374` (heap) and
`libwinpthread-1.dll` `0xC0000005` (access violation). It is also consistent
with why the owned worker fixes the fault: only one long-lived thread ever
enters native code. This is a narrowing, not a demonstration, because nothing
here reproduced the fault.

## Matrix result

| arm | role | children | faults | `0xC0000374` |
|---|---|---:|---:|---:|
| `sampler_concurrent` | baseline: 4 resident replicas, concurrent direct calls | 60 | 0 | 0 |
| `sampler_concurrent_unload` | H1: same, with `FreeLibrary` after the run | 60 | 0 | 0 |
| `sampler_owned` | fix: one long-lived owner thread, serialized | 120 | 0 | 0 |
| `sampler_concurrent` with the `STAN_THREADS` model | H4 | 30 | 0 | 0 |
| `sampler_concurrent` with the no-threads model | H4 control | 30 | 0 | 0 |

Every child used:

- the real `owalnuts::sampler::Sampler`, with 4 chains on 4 threads and 100
  warmup plus 100 retained draws;
- median ~33–35k gradient calls per child, of which ~4k were recoverable Stan
  exceptions, so the error-message allocate/free path was exercised heavily.

The child sees zero native faults here. The upper bound on the
baseline-configuration fault rate is 4.9% (one-sided 95%, from 0/60). If the
comparator's 8.9% rate applied, 0/60 would have probability 0.004. So this
harness and environment differ materially from the conditions that
reproduced the fault.

## Why it may not have reproduced (untested confounds)

1. **Which `libwinpthread-1.dll` was loaded.** `artifacts/environment.json`
   shows the children resolved it to Git's
   `C:\Program Files\Git\mingw64\bin` copy (63,875 B). The models were
   compiled by WinLibs GCC 16.1.0, whose own copy (72,171 B) comes later on
   PATH. The prior studies were launched from PowerShell and never recorded
   which copy their children loaded. The leading suspect in the narrowed
   mechanism is the winpthread TLS-destructor path, so this is the first
   factor to control.
2. **Direct FFI instead of the integration's 9edcbac code path.** The harness
   does not reproduce that path's SHA-256 replica cache, its module lock plus
   process-lock pattern, or its `bs_param_constrain` calls.
3. **Different model binaries.** The prior hashed models are gone; these were
   rebuilt from the same sources with the same BridgeStan version and flags,
   but the bytes differ.

## Payoff measurement

Not run. The preregistered condition was "if H1 holds, implement never-unload
or join-first and measure unserialized sampling cost". H1 did not hold:
never-unload is already the Windows behaviour and does not remove the fault.
Durations in the process records are contended and descriptive only.

## Recommendation

- Keep the owned-worker plus process-wide serialization mitigation unchanged.
  Do not drop serialization on the strength of this study.
- No sampler, default or doc change, beyond recording in open question 8 that
  H1 (unload), H2 and H3 are closed.
- Next study: run the integration's own comparator path (9edcbac) as a 2×2:
  Git versus WinLibs `libwinpthread-1.dll`, launched from PowerShell versus
  Git Bash. Record the loaded module path in each child. Only reopen
  multi-worker Windows execution if one cell reproduces and its paired cell
  is clean.

## Layout and verification

- `src/main.rs`: child harness. It contains micro arms and sampler arms,
  calls BridgeStan through direct `libloading` FFI, and refuses seeds
  90101–90103.
- `run_root_cause.py`: orchestrator, with exclusive launch markers and no
  relaunch.
- `test_run_root_cause.py`: tests for the orchestrator.
- `artifacts/`:
  - `processes/`, `raw/`, `heartbeats/`, `launches/`, `stdout/`, `stderr/`:
    per-child records;
  - `summary.json` and `run-log.txt`: matrix totals and the run log;
  - `environment.json`: machine and loaded-DLL record;
  - `calibration-non-evidence.md`: the pre-freeze calibration runs;
  - the three audits.
- Models are rebuilt from the posteriordb `28f8d3d` sources and gitignored.
  Their hashes are in `protocol.json`.

```powershell
cargo +1.88.0-x86_64-pc-windows-gnu test --release
python -m unittest -v test_run_root_cause.py
python run_root_cause.py verify --binary target\release\bridgestan-windows-root-cause-v1.exe
python run_root_cause.py analyze
python checksums.py verify
```
