# WP50C: static mingw runtime for BridgeStan DLLs (fix, stress gate, payoff)

This is a process and engineering study. It produces no posterior evidence.
It follows WP50B (`../bridgestan_windows_root_cause_v2`). Each phase was
preregistered and committed before its own evidence (`PREREGISTRATION.md`,
`protocol.json`).

## Phase A: fix (`artifacts/phase-a-result.md`)

The fix links the mingw runtime statically into the model DLLs. The tool is
`integrations/bridgestan/tools/build_static_runtime.py`; usage is in the
integration README.

- **Model DLLs.** Built with the make override
  `LDLIBS_OS=-static-libgcc -static-libstdc++ -Wl,-Bstatic,--whole-archive -lwinpthread -Wl,--no-whole-archive,-Bdynamic`.
- **Private `tbb.dll`.** Built with the same flags plus
  `-Wl,--exclude-libs,ALL`. It is preloaded by full path.

Acceptance:

- **A1:** objdump shows no `libwinpthread-1`, `libgcc_s_seh-1` or `libstdc++-6`
  import.
- **A2:** the export lists are equal.
- **A3:** log densities and gradients are bit-identical at 64 positions, for
  sblrc and arK.
- **A4:** none of the three runtime DLLs is mapped when the static DLLs are
  loaded.

## Phase B: stress gate (`artifacts/phase-b-result.md`)

Setup:

- the integration at 9edcbac, where 4 replica modules evaluate truly
  concurrently and there is no owned worker;
- sblrc with 4 replicas, 4 chains and 4 threads;
- PowerShell launch with the registry PATH, so the WinLibs runtime binds the
  dynamic DLLs.

There were 480 interleaved children. Every child's mapped runtime modules
matched its arm.

- **Static, 1000/1000:** 0/300 faults (95% upper bound 0.99%).
- **Dynamic control, 1000/1000:** 1/60, `0xC0000374` during sampling.
- **Static, 4/4:** 0/60.
- **Dynamic control, 4/4:** 1/60, `0xC0000374` at exit.

**Verdict: `fix_supported`, after a disclosed correction to the event
correlation.**

- **The correction.** Windows reused a PID, so the preregistered PID+path
  match attributed one dynamic-control crash event to a clean static child
  launched 15 minutes later. That gave a literal `fix_not_supported`.
  Attribution now also requires the event time to fall inside the child's
  launch window. The literal summary is preserved.
- **Weak evidence.** The control reproduced at only 1.7%, below the 5%
  assumed. The one-sided Fisher p for 1/60 vs 0/300 is 0.167, and for the
  pooled 2/120 vs 0/360 it is 0.062.

## Phase C: payoff (`artifacts/phase-c-result.md`)

Setup:

- HEAD sampler, static DLLs, 1000/1000, 4 chains / 4 threads;
- 3 fresh seeds each for sblrc and arK;
- arms: HEAD's owned-worker `ReplicatedStanTarget` (serialised) vs a
  study-local 4-replica free-replica dispatch (unserialised).

Results:

- There were no faults. Gradients, draws fingerprints and call counts were
  bit-identical between the arms for every seed.
- The median serialised/unserialised sampling-wall ratio was **3.16 on sblrc
  and 4.05 on arK** (contended).
- The serialised arm also used 1.7–4.4x more process CPU.

## Recommendation

The frozen rule is met. **Change the Windows default from the owned worker to
multi-replica dispatch, but only for DLLs verified to be static-runtime.**
"Verified" means that neither the model nor the preloaded tbb imports a mingw
runtime DLL. That condition is cheap to check at load from the PE import
table.

**Keep the owned worker for dynamic-runtime DLLs.** This study re-confirmed
that they fault under concurrent replicas.

The safety margin rests on a positive control that reproduced only 2/120 times.
Ship the multi-worker path opt-in first, then flip the default after a larger
static gate (for example 1,000 children, alongside a control of ≥300).

## Reproduce

```
python <tool> --out build/static --tbb <V1>/sblrc__blr.stan <V1>/arK__arK.stan   # Phase A
python parity_check.py
python build_child.py && python run_phase_b.py verify && python run_phase_b.py probe
python run_phase_b.py analyze          # the single run already happened
python run_phase_c.py build && python run_phase_c.py analyze
python checksums.py verify
```

Use `C:\dev\owalnuts\integrations\.venv-bs\Scripts\python.exe`,
`RUSTUP_TOOLCHAIN=1.88.0-x86_64-pc-windows-gnu`, and `MAKE=mingw32-make`.
