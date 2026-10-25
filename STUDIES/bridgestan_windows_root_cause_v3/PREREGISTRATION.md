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
