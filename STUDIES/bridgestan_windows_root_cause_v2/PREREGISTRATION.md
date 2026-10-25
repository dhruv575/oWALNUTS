# WP50B — Windows BridgeStan heap corruption: libwinpthread source × launcher (preregistration)

Status: process diagnostic only. Frozen and committed before any evidence
child runs. It follows WP50 (`STUDIES/bridgestan_windows_root_cause_v1`),
which did not reproduce the fault in 0/300 children. WP50 found that its
children loaded Git for Windows' `libwinpthread-1.dll` rather than the WinLibs
copy belonging to the toolchain that built the models.

No fix is implemented here. The mechanism and the recommended fix are reported
for a separate decision. WP35/WP36 evidence seeds 90101–90103 are forbidden.

## Question

Does the Windows-GNU `STATUS_HEAP_CORRUPTION` (`0xC0000374`) reproduction
depend on two factors?

- which `libwinpthread-1.dll` copy the model DLL binds to;
- which launcher (PowerShell or Git Bash) starts the child.

All children are driven through the integration's original reproducing code
path at commit `9edcbac`: resident DLLs, scoped joined pools, and four
replica modules evaluated concurrently. That path's
`bridgestan_owned_worker_v1` comparator failed 16/180 with `0xC0000374`.

## Design: 2 × 2, paired by seed

| factor | level | operationalisation |
|---|---|---|
| libwinpthread | `git` | Git for Windows `mingw64\bin\libwinpthread-1.dll`, 63,875 B, sha256 `8d7a192a…` |
| libwinpthread | `winlibs` | WinLibs GCC 16.1.0 `mingw64\bin\libwinpthread-1.dll`, 72,171 B, sha256 `c29cbbe3…` |
| launcher | `powershell` | `powershell.exe -NoProfile` running `& <exe> <args>; exit $LASTEXITCODE`, with the registry Machine;User PATH (a fresh user PowerShell session) |
| launcher | `bash` | `C:\Program Files\Git\bin\bash.exe -l -c '"$0" "$@"'`, from the same registry base; the Git Bash login profile then prepends its own directories, as an interactive Git Bash does |

**How the libwinpthread factor is set.** The chosen copy sits beside a
byte-identical child exe in `build/arms/<git|winlibs>/`. The application
directory is first in the Windows DLL search order, so that copy binds
regardless of PATH. Each launch directory contains nothing else.

**What the launcher factor includes (frozen from the pre-launch check).** The
pre-launch manipulation check (`artifacts/manipulation-check.json`) ran one
no-sampling probe per cell. In all 4 cells, libwinpthread bound from the
cell's own directory. It also showed that `tbb.dll`'s dynamic imports
`libgcc_s_seh-1.dll` and `libstdc++-6.dll` resolve by PATH:

- under PowerShell they come from WinLibs (the matching toolchain);
- under Git Bash they come from Git's `mingw64\bin` (a different GCC build).

So the launcher factor is: shell, environment, **and** the C++ runtime source
for `tbb.dll`. Those three cannot be separated with this design. WP50's
non-reproducing condition corresponds to the `bash/git` cell.

**Per-child logging.** Every child records the full path and size of each of
`libwinpthread-1.dll`, `libgcc_s_seh-1.dll`, `libstdc++-6.dll` and `tbb.dll`
actually mapped (`GetModuleHandleW` + `GetModuleFileNameW`, after model load).
It also records its PATH and the 12-event atomic heartbeat sequence. The
parent records the launcher's return code. A cell's libwinpthread being
loaded from anywhere other than that cell's directory is a manipulation
failure, and is reported.

**Child shape.** Identical to the `bridgestan_owned_worker_v1` comparator
child: sblrc, 4 requested replicas, 4 chains, 4 threads, 4 warmup plus 4
retained. The child is built `--locked` with the comparator's dependency lock
inside a `git archive` of `9edcbac`; the exe hash is in
`artifacts/build-manifest.json`. The model is WP50's rebuild of sblrc,
because the prior hashed binary no longer exists (sha256 in `protocol.json`).

**Seeds and order.**
- Seeds 50600001–50600060. Each seed runs once in every cell, so 60 children
  per cell and 240 in total. An exact-word search found base 50600000 unused.
- Within seed index *i*, the cells run in the order
  `powershell/git, powershell/winlibs, bash/git, bash/winlibs`, rotated left
  by *i* mod 4. This is a balanced Latin square, so drift in machine load is
  not confounded with cell.
- Everything runs strictly sequentially, one model and at most 4 threads per
  process, with a 90 s timeout. The parent removes each child's private model
  cache directory after that child exits.

## Power

The comparator rate was 16/180 = 8.9% heap corruption; the sblrc-only fault
union was 10/60 = 16.7%. With 60 children per cell, the chance a cell sees at
least one fault is:

| true rate | P(≥1 fault in 60) |
|---:|---:|
| 8.9% | 0.996 |
| 16.7% | >0.999 |
| 4.4% (lifetime-study rate) | 0.933 |
| 2.2% (WP35A rate) | 0.737 |

**Margin test.** The one-sided Fisher exact test on a factor's margins
(120 vs 120) gives p = 0.030 for 5 faults vs 0. If one level is at 8.9% and
the other at 0, P(Bin(120, 0.089) ≥ 5) = 0.985.

## Classification

- **Fault:**
  - launcher timeout; or
  - nonzero launcher return code; or
  - raw output missing or not `ok`; or
  - heartbeat sequence different from the expected 12 events; or
  - an Application Error Event 1000 correlated by child PID and exe path.
- **Heap corruption:**
  - launcher return code `0xC0000374`; or
  - a correlated Event 1000 with exception code `c0000374`.
- **Event capture.** Git Bash maps NTSTATUS crashes to exit code 127, so the
  true code in those cells is recovered from Event 1000. Events 1000/1001 are
  captured once after the run, over the whole window plus 20 s, for every
  cell.

## Decision rule (frozen)

- A **cell reproduces** if it has ≥1 fault.
- A **factor is implicated** only if all three hold:
  - both cells at one level reproduce;
  - both cells at the other level have 0 faults;
  - the one-sided Fisher margin p < 0.05 in that direction.
- If exactly one cell reproduces, or the pattern fits neither main effect, it
  is reported as an interaction / single-cell result with its counts. No
  factor is then claimed alone.
- If all four cells are at 0, the result is non-reproduction on the 9edcbac
  path. Neither factor is implicated, and the per-cell one-sided 95% upper
  bound is 4.9%.
- The heap-corruption counts, last heartbeats and Event 1000 faulting modules
  are reported for every fault.
- **No fix is implemented.** If a factor or a cell is implicated, the report
  names the mechanism and the recommended fix (for example, pinning the DLL
  search path or shipping the matching runtime DLLs beside the binary) for a
  separate decision.

## Rules

- Run the matrix once, in the frozen order. Report every child. Never relaunch.
- Failures are results. Do not tune or substitute after observing results.
- Durations are contended and descriptive only.
