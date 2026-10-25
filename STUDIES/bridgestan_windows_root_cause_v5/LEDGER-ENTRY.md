### WP50E-BRIDGESTAN-WINDOWS-ROOT-CAUSE-V5 — replay of WP50D seed 50801734: the "nonfinite target position (chain 2, transition 9)" error reproduces 6/6 under both dispatches (and 3/3 with the original exe), deterministically within each arm; frozen verdict NOT_ESTABLISHED because the cross-dispatch stream hash differs, solely in the gradient buffer returned on recoverable evaluations

**Ordered time.** 2026-10-25 on `wt/windows-native-root-cause`. Preregistered at `d7f2c97a`, with the child built and verified before that commit. One launch of 11 processes, 21:07–21:08 local, strictly sequential.

**Design.** `STUDIES/bridgestan_windows_root_cause_v5/{PREREGISTRATION.md,protocol.json}`. Seed 50801734 is reused on purpose; 90101–90103 are not used.

- **Gating arms:** A, owned worker ×3; B, unserialised dispatch ×3.
- **Fidelity arm:** C, the original WP50D exe ×3.
- **Descriptive arms:** D and E, `RejectLeaf` under each dispatch.
- **Instrumentation:** passive research observers and a pass-through target wrapper.

**Outcome: frozen verdict `NOT_ESTABLISHED_NONDETERMINISTIC`.**

- **Reproduction:** the identical `Numerical` error in A 3/3, B 3/3 and C 3/3.
- **Within each arm:** the chain-2 streams were bit-identical, 7,705 observations and 763 target calls.
- **Across arms:** the hashes differ, so the frozen all-six identity failed.

**Descriptive, post hoc.** The only differing field in 7,705 chain-2 proposals is the gradient on 1,512 `Recoverable` evaluations: the owned worker returns zeros, the direct dispatch returns the NaN prefill. Everything else is bit-identical: positions, steps, momenta, energies, calls, completed transitions 0–8, and the overflow observation (last coordinate -inf at step 1.329). Under `RejectLeaf`, D and E complete with bit-identical draws `5d7e4a62b998da28` and one rejection, in chain 2 at transition 9.

**The event.** An integrator overflow in the initial fast warmup, from a start with log density -7.0e5. It is the same class as `nonfinite_position_policy_v1`.

**Integration question.** Not an integration bug. The error is `Numerical` with no target source, and 0 nonfinite inputs reached the target layer. The shipped `Abort` policy stops before the target is called, so the WP50D exit 1 is designed behaviour.

**Artifacts.** In `STUDIES/bridgestan_windows_root_cause_v5/`:

- `{README.md,LEDGER-ENTRY.md,build_child.py,run_replay.py,test_run_replay.py,describe.py,checksums.py,CHECKSUMS.sha256}` and `child/`;
- `artifacts/{processes,raw,launches,heartbeats}/`;
- `artifacts/{build-manifest.json,windows-events.json,summary.json,descriptive-localisation.json,run-log.txt,result.md}`.

**Next decision (coordinator).**

- **Accept or reject the stricter-than-stated identity rule.** On the coordinator's literal criterion (identical error, identical draws and gradient counts up to the fault) the fault is deterministic and dispatch-independent, which would make the WP50D static native-fault count 0/1000. On the frozen implementation it is not established.
- **If the opt-in is pursued,** normalise the direct dispatch's error-path gradient to match the owned worker.
