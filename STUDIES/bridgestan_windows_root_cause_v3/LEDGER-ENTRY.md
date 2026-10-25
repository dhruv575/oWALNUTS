### WP50C-BRIDGESTAN-WINDOWS-ROOT-CAUSE-V3 — the static mingw runtime removes the PATH-dependent heap corruption (static 0/360 vs dynamic 2/120), and removing the Windows owned-worker serialisation is worth 3.2x (sblrc) / 4.0x (arK) contended sampling wall with bit-identical draws

**Ordered time and commits.** 2026-10-24/25 on `wt/windows-native-root-cause`. Each phase was preregistered before its evidence.

- Phase A: preregistered at `37f0bdbc`, results at `ab3d41f1`.
- Phase B: preregistered at `6c166c2a`, results at `ee46cdd7`.
- Phase C: preregistered at `ba28af73`, with the protocol status and seed check at `3bc064c5`. Results are in this commit.

**Phase A (fix).** `integrations/bridgestan/tools/build_static_runtime.py`, documented in the integration README.

- **Model DLLs:** `LDLIBS_OS=-static-libgcc -static-libstdc++ -Wl,-Bstatic,--whole-archive -lwinpthread -Wl,--no-whole-archive,-Bdynamic`.
- **Private tbb.dll:** the same flags plus `-Wl,--exclude-libs,ALL`.
- **Acceptance A1–A4 passed:**
  - no runtime imports;
  - export lists equal;
  - bit-identical log density and gradient at 64 positions for sblrc and arK;
  - no runtime DLL mapped at load.

**Phase B (stress gate).** The 9edcbac unserialised 4-replica path, sblrc, PowerShell with the WinLibs PATH. 480 interleaved children, 0 manipulation failures, nothing rerun.

- **Results:**
  - static 1000/1000: 0/300;
  - dynamic control 1000/1000: 1/60, `0xC0000374` at `sampling/before`;
  - static 4/4: 0/60;
  - dynamic 4/4: 1/60, `0xC0000374` at exit.
- **Verdict:** `fix_supported`.
- **Analysis correction.** Windows reused PID 26612, so the PID+path event match also attributed a control crash event to a clean static child launched 15 minutes later. That produced a literal `fix_not_supported`. The corrected rule requires the event time to fall within the child's launch window. The literal summary is preserved. WP50B is unaffected, because it used per-cell exe paths.
- **Strength.** The control rate was only 1.7%. One-sided Fisher p is 0.167 for 1/60 vs 0/300, and 0.062 pooled (2/120 vs 0/360).

**Phase C (payoff).** HEAD sampler, static DLLs, 1000/1000, 4 chains / 4 threads.

- **Arms:** HEAD owned-worker `ReplicatedStanTarget` vs a study-local 4-replica free-replica dispatch.
- **Seeds:** sblrc 50700701–703 and arK 50700711–713, exact-word verified unused.
- **Results:** 12/12 children with 0 faults. Start gradients, draw fingerprints and call counts were identical for every seed.
- **Median wall ratio (contended):** sblrc 3.16 (2.74, 4.92, 3.16) and arK 4.05 (10.8, 4.05, 3.65). Serialised process CPU was 1.7–4.4x higher.

**Recommendation.** The frozen rule is met.

- Change the Windows default to multi-replica dispatch only for DLLs verified to be static-runtime, checked from the PE imports at load.
- Keep the owned worker for dynamic-runtime DLLs.
- Because the control rate was low, ship the change opt-in first. Flip the default after a larger static gate (≥1,000 children with a ≥300-child control).

**Artifacts.** In `STUDIES/bridgestan_windows_root_cause_v3/`:

- `{PREREGISTRATION.md,protocol.json,README.md,LEDGER-ENTRY.md}`;
- `{parity_check.py,build_child.py,run_phase_b.py,run_phase_c.py}` with their tests;
- `child/` and `payoff/`;
- `artifacts/{phase-a-*,phase-b-*,phase-b/,phase-c-*,phase-c/}`;
- `CHECKSUMS.sha256`.
