# WP50C — static mingw runtime for BridgeStan DLLs: fix, stress gate, payoff

Process/engineering study in three phases. Each phase is preregistered and
committed before its own evidence runs. Follows WP50B
(`STUDIES/bridgestan_windows_root_cause_v2`). In WP50B the post-sampling
`STATUS_HEAP_CORRUPTION` reproduced only when the WinLibs `libwinpthread-1.dll`
+ `libgcc_s_seh-1.dll` + `libstdc++-6.dll` set was bound from PATH (3/60), and
the faults were inside `libwinpthread-1.dll` at teardown. Goal: remove the
PATH dependence and measure the payoff. Evidence seeds 90101–90103 are
forbidden.

## Phase A — fix (frozen before the build)

Change: link the mingw runtime statically into every BridgeStan DLL we load.

- **Model DLLs.** The make command-line override
  `LDLIBS_OS=-static-libgcc -static-libstdc++ -Wl,-Bstatic,--whole-archive -lwinpthread -Wl,--no-whole-archive,-Bdynamic`.
  `LDLIBS_OS` is Stan Math's `?=` per-OS link-library slot, and its Windows
  default is already `-static-libgcc -static-libstdc++`. The stock model DLL
  therefore imports only `libwinpthread-1.dll` from the runtime, and the
  `--whole-archive` static winpthread removes that import. Plain `-static`
  is not usable, because it also forces a static `-ltbb`; an exploratory
  scratch build failed with "cannot find -ltbb".
- **tbb.dll.** It is ours to build: Stan Math builds it from its bundled
  `tbb_2020.3`, and it imports `libgcc_s_seh-1.dll` and `libstdc++-6.dll`.
  A private copy is built from a copy of those sources with Stan Math's own
  `Makefile.tbb` invocation and
  `LDFLAGS=-static-libgcc -static-libstdc++ <static winpthread> -Wl,--exclude-libs,ALL`.
  It is preloaded by full path, so the model's `tbb.dll` import binds to it.
  The shared `~/.bridgestan` tree is never modified.
- **Where it lives.**
  - `integrations/bridgestan/tools/build_static_runtime.py`, which this study
    calls;
  - the Windows build section of `integrations/bridgestan/README.md`,
    written after the build with the exact flags.
- **Feasibility disclosure.** Before freezing, two exploratory scratch builds
  were made (outside the repository) to find a link line that works: plain
  `-static` failed, the `--whole-archive` form succeeded. A first private TBB
  build exported 20 extra libgcc unwinder symbols, so
  `--exclude-libs,ALL` was added. No sampler, child or stress run was made.

Acceptance (all must hold; frozen in `protocol.json` `phase_a.acceptance`):

- **A1 — imports.** Neither the sblrc nor the arK model DLL, nor the private
  `tbb.dll`, imports `libwinpthread-1.dll`, `libgcc_s_seh-1.dll` or
  `libstdc++-6.dll` (`objdump -p`).
- **A2 — exports.**
  - Each static model's export names equal those of its WP50 dynamic build.
  - The private `tbb.dll` exports every stock export. Any extra exports are
    reported; the target is zero.
- **A3 — numerical parity.** Log density and gradient at 64 deterministic
  positions are bit-identical between the static and dynamic builds. Each
  build is evaluated in its own process with its own `tbb.dll`.
- **A4 — load check.** In the static process none of the three runtime DLLs
  is mapped, and `tbb.dll` is the private copy.

If A1 cannot be met, the fallback is pinning an explicit DLL search path, and
that will be stated. If A2–A4 fail, it is reported and Phase B is not run on
these DLLs.

Phase A result (`artifacts/phase-a-result.md`): A1–A4 all hold.

## Phase B — stress gate (frozen before any Phase B child)

Frozen in `protocol.json` `phase_b`; run by `run_phase_b.py run` exactly once.

### B.1 Configuration (the WP50B reproducing cell)

- **Code path.** The integration at `9edcbac`: resident DLLs, scoped joined
  pools, `ReplicatedStanTarget` with 4 truly concurrent replica modules on
  Windows. There is no owned worker. The child (`child/`) is the WP50B child
  with three changes: the preload `tbb.dll` and warmup/retained are CLI
  arguments; the frozen (shape, seed) pairs are new; and it has a `probe`
  mode. It is built by `build_child.py` from `git archive 9edcbac`.
- **Launch.** PowerShell `-Command "& '<exe>' <args>; exit $LASTEXITCODE"`
  under the registry Machine;User PATH. The launch directory holds only the
  exe, so every runtime DLL that a dynamic build needs is bound from PATH.
  That is the WinLibs bin, the set that faulted in WP50B.
- **Model.** sblrc, 4 replicas, 4 chains, 4 threads.

### B.2 Arms

Arms run interleaved in 60 blocks of 8. Block b holds 5 `static_long`, then 1
each of `control_long`, `static_short` and `control_short`, rotated left by
b mod 8. Children run strictly sequentially.

- **`static_long`.** Phase A static sblrc DLL plus private `tbb.dll`;
  1000/1000; 300 children; seeds 50700001–50700300. This is the gate arm.
- **`control_long`.** The old dynamic sblrc DLL (WP50, sha 29625697…) plus the
  stock `tbb.dll`; 1000/1000; 60 children; seeds 50700401–50700460. This is
  the concurrent positive control.
- **`static_short`.** Static DLLs at 4/4; 60 children; seeds
  50700501–50700560. See B.3.
- **`control_short`.** Dynamic DLLs at 4/4; 60 children; seeds
  50700601–50700660. This repeats the WP50B powershell/winlibs-equivalent
  cell.

**Manipulation check.** It ran before this commit with the probe mode, no
sampling (`artifacts/phase-b-manipulation-check.json`). Static: none of the
three runtime DLLs is mapped, and `tbb.dll` is the private one. Dynamic: all
three come from the WinLibs bin, and `tbb.dll` is the stock one. The check is
repeated per child at `load/after`.

### B.3 The "static without owned-worker serialisation" arm

The coordinator asked for 60 static children with 4 replicas truly parallel.
At `9edcbac` that is already the gate's code path, because the owned worker
arrived later, in 29290a0. A second 1000/1000 arm would therefore duplicate
`static_long`. So these 60 children run at the WP50B shape (4/4), the shape
where the dynamic fault was first measured. A dynamic 4/4 control runs
alongside so that the short shape has its own positive control. Both short
arms are descriptive and do not gate.

### B.4 Classification and decision rule

**Fault.** Any of:

- launcher timeout (300 s);
- nonzero launcher return code;
- missing or non-ok raw output;
- heartbeat sequence different from the expected 12;
- a correlated Application Error Event 1000, matched on decimal child PID and
  exe path. This includes hidden exit-0 crash events.

**Heap corruption.** 0xC0000374 as the return code or as the event exception
code.

**Gate.**

- **Fix supported:** `static_long` 0/300 AND `control_long` ≥ 1 fault.
- **Inconclusive (control did not reproduce):** `static_long` 0/300 AND
  `control_long` 0/60.
- **Fix not supported:** `static_long` ≥ 1 fault.

Phase C runs only if the fix is supported.

**Power.**

- The control rate assumed is 0.05 (WP50B 3/60). P(control ≥ 1 in 60) is
  0.95; it would be 0.74 at a rate of 0.022.
- 0/300 bounds the static fault rate below 0.99% (95%).
- Secondary, one-sided Fisher test of control k/60 vs static 0/300:
  p = 0.167, 0.027 and 0.0044 for k = 1, 2, 3.

**Reporting rules.**

- Manipulation failures are reported. Arms are counted intention-to-treat.
- Durations are contended wall times, because other agents share the
  machine.
- There are no reruns, and failures are results.
