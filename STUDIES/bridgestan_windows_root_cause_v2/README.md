# WP50B — Windows BridgeStan heap corruption: libwinpthread source × launcher

Status: complete. The preregistration was committed at `11babbcc` before any
evidence child ran. The matrix ran once: 240/240 children, strictly
sequential, no reruns, and 0 manipulation failures. This is a process
diagnostic only. **No fix is implemented in this study.**

## Verdict

**Single-cell result: the fault reproduced only in the all-WinLibs-runtime
cell.** Under the frozen rule neither factor is implicated on its own.

| cell (launcher / libwinpthread) | runtime DLLs actually bound | children | faults | `0xC0000374` | Event 1000 |
|---|---|---:|---:|---:|---:|
| powershell / winlibs | all WinLibs: winpthread, libgcc_s_seh, libstdc++ | 60 | **3** | 2 | 3 |
| powershell / git | Git winpthread + WinLibs libgcc_s_seh/libstdc++ | 60 | 0 | 0 | 0 |
| bash / winlibs | WinLibs winpthread + Git libgcc_s_seh/libstdc++ | 60 | 0 | 0 | 0 |
| bash / git | all Git (WP50's non-reproducing condition) | 60 | 0 | 0 | 0 |

- **Factor margins.** Both factors give 3/120 vs 0/120, one-sided Fisher
  p = 0.123. That is below the preregistered threshold for implicating a
  factor, so neither is.
- **Post-hoc only, not preregistered.** The reproducing cell against the
  other three combined gives 3/60 vs 0/180, one-sided Fisher p = 0.015. The
  other three cells together bound the fault rate at 1.65% (one-sided 95%);
  each cell alone bounds it at 4.9%.
- **The three faults** (per-child module paths verified from
  `GetModuleFileNameW`):
  - `powershell-winlibs-50600001`: launcher code `0xC0000374`; every
    heartbeat was written through `process/complete`, so it crashed during
    process exit. Event 1000 shows an access violation (`c0000005`) in
    `libwinpthread-1.dll` (the WinLibs copy).
  - `powershell-winlibs-50600014`: launcher code **0** with a complete
    heartbeat sequence, yet Event 1000 shows an access violation (`c0000005`)
    in `libwinpthread-1.dll` at process exit. It is a hidden fault, counted
    by the frozen classification.
  - `powershell-winlibs-50600035`: `0xC0000374` in `ntdll.dll` with last
    heartbeat `sampling/before`, so during sampling or worker-thread
    teardown; no raw output.
- **Rate.** The reproducing cell's 3/60 (5%) is consistent with the earlier
  4.4–8.9% rates. Its runtime set matches what a fresh PowerShell session
  binds, which is how the earlier reproducing studies were launched.

## Mechanism (narrowed, not fully separated)

- **It needs the complete matching WinLibs runtime.** The fault appears only
  when the WinLibs builds of all three are loaded together:
  `libwinpthread-1.dll` (bound by the model DLL), plus `libgcc_s_seh-1.dll`
  and `libstdc++-6.dll` (pulled in dynamically by `tbb.dll`). Replacing
  either Git's libwinpthread alone, or Git's libgcc_s/libstdc++ alone,
  produced no faults (0/60 each). This is weak evidence (3 vs 0), not a
  demonstration.
- **The faulting code is WinLibs winpthreads at thread or process teardown.**
  Two of the three faults are access violations inside that
  `libwinpthread-1.dll`, at process exit after the program had finished. The
  third is heap corruption during the sampling/worker-teardown interval.
  This matches WP50's static finding: the model DLL keeps per-thread state
  (emulated-TLS C++ exception globals and libwinpthread key destructors) that
  is cleaned up as threads exit.
- **This explains WP50's 0/300.** WP50 ran from Git Bash, which bound Git's
  runtime DLLs: the `bash/git` cell, 0/60 here too.
- **Not separated.** The launcher factor is confounded with where
  `libgcc_s_seh/libstdc++` come from, so the design cannot tell apart:
  - a WinLibs winpthreads defect that only triggers alongside WinLibs
    libgcc_s (WinLibs' libgcc_s is a posix-threads build that itself routes
    through winpthread), versus
  - a defect from mixing versions;

  nor can it rule out a plain chance pattern at these counts.

## Recommended fix, for a separate decision (not implemented)

1. **Keep the owned-worker mitigation as the default.** Nothing here
   qualifies multi-worker Windows execution.
2. **Remove the PATH dependence of the mingw runtime.** Today which runtime
   DLLs bind depends on how the process was launched.
   - Preferred: build the BridgeStan model DLLs and `tbb.dll` with the
     runtime linked statically (`-static-libgcc -static-libstdc++` and static
     winpthread), so nothing is resolved from PATH.
   - Otherwise: load them through an explicitly pinned search path
     (`SetDefaultDllDirectories` + `AddDllDirectory`, or `LoadLibraryExW`
     with `LOAD_LIBRARY_SEARCH_*`) pointing at one qualified runtime set.
3. **Do not ship or depend on Git's copies.** Their 0/180 is accidental and
   unqualified.
4. **Qualify any change with a stress gate.** Plan ≥300 children per
   configuration at a ~5% base rate. A worthwhile next diagnostic is a 2×2
   under one launcher that places libwinpthread and libgcc_s/libstdc++
   independently in the application directory, about 150 children per cell.

## Analysis correction (records unchanged)

The first `analyze` pass parsed the Event 1000 PID property as hex, but this
host writes it in decimal, so no event correlated. `correlate()` now reads
decimal (hex only with a `0x` prefix). `summary.json` and
`artifacts/analyze-log.txt` are regenerated from the unchanged records and
the unchanged `windows-events.json`. No child was relaunched. The fix adds
exactly one fault, `50600014`, which returned code 0 but has a correlated
Event 1000. That is the preregistered event-inclusive classification, not a
new rule.

## Files

- `protocol.json`, `PREREGISTRATION.md`: the frozen design.
- `child/`: the child crate, built inside an archive of `9edcbac` by
  `build_child.py`.
- `run_2x2.py` (orchestrator) and `test_run_2x2.py` (its tests).
- `artifacts/`:
  - `build-manifest.json`, `manipulation-check.json`,
    `launch-environment.json`;
  - per-child `processes/`, `raw/`, `heartbeats/`, `launches/`, `stdout/`,
    `stderr/`;
  - `windows-events.json`, `summary.json`, `run-log.txt`, `analyze-log.txt`.

```powershell
python -m unittest test_run_2x2.py
python run_2x2.py analyze
python checksums.py verify
```
