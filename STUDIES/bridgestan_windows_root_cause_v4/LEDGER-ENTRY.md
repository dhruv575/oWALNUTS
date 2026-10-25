### WP50D-BRIDGESTAN-WINDOWS-ROOT-CAUSE-V4 — confirmatory gate NOT SUPPORTED: static-runtime DLLs on the unserialised multi-replica target had 1/1000 faults (a sampler-reported nonfinite-position error, not a crash) vs 4/300 crashes for dynamic DLLs on the same target; the owned worker was 0/300

**Ordered time.** 2026-10-25 on `wt/windows-native-root-cause`. Preregistered at `0ec73277`, with the child built and the manipulation probe passed before that commit. One launch of 1,600 children, 19:58–20:53 local, strictly sequential. Event capture followed, then the frozen analysis.

**Design.** `STUDIES/bridgestan_windows_root_cause_v4/{PREREGISTRATION.md,protocol.json}`.

- **Configuration:** PowerShell with the WinLibs PATH, HEAD sampler, sblrc, 4 replicas / 4 chains / 4 threads, 1000/1000.
- **Arms:**
  - `static_unserialised`: 1,000 children, seeds 50801001–50802000.
  - `dynamic_unserialised`: 300 children, seeds 50803001–50803300. Primary positive control.
  - `dynamic_owned`: 300 children, seeds 50804001–50804300. The coordinator's literal control, disclosed in advance as expected not to reproduce.
- **Interleaving:** single-arm blocks of 10.
- **Correlation, frozen:** Event 1000 attributed only by arm exe path, PID and the child's lifetime window. An unattributed static-path event would count as a static fault.
- **Seeds:** exact-word verified unused; 90101–90103 forbidden.

**Status.** 1,600/1,600 records; 0 timeouts; 0 manipulation failures, since no static child mapped `libwinpthread-1`, `libgcc_s_seh-1` or `libstdc++-6`; 4 events attributed, 0 unattributed; nothing rerun.

**Outcome: frozen verdict `not_supported`** under both control readings.

- **`static_unserialised` 1/1,000** (one-sided 95% upper bound 0.47%). The fault, `50801734`, exited with rc 1 at `sampling/before` with the stderr "kernel attempted a nonfinite target position (chain 2, transition 9); the integrator overflowed". There was no Event 1000 and no NTSTATUS code.
- **`dynamic_unserialised` 4/300**, all crashes: 2 × `0xC0000374` (one mid-sampling, one at exit), and 2 hidden exit-0 crashes, each a `c0000005` in WinLibs `libwinpthread-1.dll` at offset `0x8c89`.
- **`dynamic_owned` 0/300.**
- **Fisher:** one-sided p = 0.0114 for 4/300 vs 1/1,000; p = 1.0 for the owned-worker control.

**Descriptive, post hoc, not part of the verdict.** Crash-type faults were static 0/1,000 vs dynamic-unserialised 4/300.

**Artifacts.** In `STUDIES/bridgestan_windows_root_cause_v4/`:

- `{README.md,LEDGER-ENTRY.md,build_child.py,run_gate.py,test_run_gate.py,checksums.py,CHECKSUMS.sha256}` and `child/`;
- `artifacts/{processes,raw,heartbeats,launches,stdout,stderr}/`;
- `artifacts/{build-manifest.json,manipulation-check.json,launch-environment.json,windows-events.json,summary.json,run-log.txt,result.md}`.

**Conclusion.**

- Dynamic-runtime DLLs crash under unserialised replicas at about 1.3%, and the owned worker suppresses this.
- Static-runtime DLLs produced no crash in 1,000 children, but they did not meet the frozen 0/1,000 gate, because one child failed with a sampler numerical error.
- The Windows default stays the owned worker.

**Next decision.** Preregister a deterministic replay of seed 50801734: static DLLs under the owned worker, then under the unserialised target, then dynamic DLLs under the owned worker. That classifies the static fault. An opt-in `WindowsDispatch::ConcurrentIfStaticRuntime`, with the load-time PE-import check, is prepared on the branch and is not merged.
