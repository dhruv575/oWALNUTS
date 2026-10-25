# WP50E: deterministic replay of the WP50D static fault (seed 50801734)

This study is a process and engineering diagnostic, not posterior evidence.
WP50D (`../bridgestan_windows_root_cause_v4`) had a single
`static_unserialised` fault. Child `50801734` exited with rc 1 at
`sampling/before`, and its stderr read "kernel attempted a nonfinite target
position (chain 2, transition 9); the integrator overflowed". There was no
Event 1000 and no NTSTATUS code.

This study classifies that fault. Everything here is frozen in
`protocol.json` and implemented in `run_replay.py` (with tests in
`test_run_replay.py`) before any replay. The single launch runs in a fixed
order. Failures are results, and nothing is rerun. No library code changes.

## Replays (strictly sequential, one process at a time, 4 threads)

The same model (Phase A static sblrc DLL, private `tbb.dll`), data, seed and
shape as the faulting WP50D child:

- 4 replicas, 4 chains, 4 threads;
- 1000/1000, diagonal metric, default adaptation and tuning;
- uniform init, `admit_worst_case`.

The launcher is the same: PowerShell under the registry PATH. Each arm has its
own exe-only launch directory.

**Gating arms:**

- **A:** owned worker (HEAD `ReplicatedStanTarget`), shipped `Abort` policy, ×3.
- **B:** unserialised dispatch (the WP50D study-local target, code copied
  verbatim), `Abort`, ×3.

**Supplementary arms:**

- **C:** the byte-identical WP50D child exe (sha `d3d7fe34…`), arm
  `static_unserialised`, seed 50801734, ×3. It has no observers and no
  `research` feature, so it checks that the replayed event is the WP50D event.
- **D, E:** the owned and unserialised dispatches with the research-only
  `NonfinitePositionPolicy::RejectLeaf`, ×1 each. These are descriptive.

**Order:** A1 B1 C1 B2 A2 C2 A3 B3 C3 D E.

## Instrumentation (A, B, D and E only; passive)

The v5 child runs through `Sampler::run_with_comparison_observers`. That
entry point needs the `research` feature, which is enabled on the child's
`owalnuts` dependency only. The child has three passive instruments:

- **Proposal observer.** Every proposal of every chain is hashed into a
  per-chain stream: transition, target call, phase/direction/level/leaf/
  micro-steps/outcome, step, coordinates, gradient, mid-step momentum, kinetic,
  potential and H. Chain 2's proposals for transitions 0..9 are stored in
  full, as values and as IEEE bits.
- **Transition observer.** For chain 2, transitions 0..9: the selected
  position and momentum, log density, gradient, diagnostics, work, leaf
  outcomes, and the adaptation step before and after.
- **Pass-through target wrapper.** It counts calls, nonfinite inputs,
  recoverable and fatal `TargetError`s, and nonfinite values returned.

## Frozen classification (as the coordinator set it)

**`DETERMINISTIC_DISPATCH_INDEPENDENT`** iff all three of these hold:

1. **Every replay reproduces the error.** In all six A/B replays the sampler
   returns `ErrorKind::Numerical`, the message contains "kernel attempted a
   nonfinite target position", and the error reports chain 2, transition 9.
2. **The chain-2 stream is identical up to the fault.** That means the same
   count, hash, last target call and first `KernelNonfinite` observation. It
   covers positions, gradients and target-call counts. The starts are also
   identical.
3. **There is no crash in a gating arm.**

Then the fault is a deterministic sampler/target event independent of
dispatch, and **the WP50D static arm's native-fault count is 0/1,000 by
construction**.

**Otherwise the fault is NOT established as such**, and the result says
which of these held:

- `NOT_ESTABLISHED_UNSERIALISED_ONLY`: B reproduces 3/3 and A 0/3;
- `NOT_ESTABLISHED_NOT_REPRODUCED`: no gating replay reproduces;
- `NOT_ESTABLISHED_NONDETERMINISTIC`: any other pattern.

If arm C does not reproduce 3/3, that is reported as an anomaly limiting the
transfer to WP50D. It does not change the rule.

## The integration question (frozen interpretation)

The shipped policy is `NonfinitePositionPolicy::Abort`. `RejectLeaf` is
research-only and `NOT_QUALIFIED` (`STUDIES/nonfinite_position_policy_v1`).
Under `Abort` the kernel checks the position *before* calling the target:
`src/walnutpie.rs`, in the transition's evaluation closure.

- **Not an integration bug** if, in every reproducing replay, the error kind
  is `Numerical`, there is no target source, and the target wrapper saw 0
  nonfinite inputs. Exit 1 is then the designed outcome of the shipped policy.
  No `TargetError` existed for the Replicated target to surface.
- **Candidate integration bug** if the error kind is `Target`, a target
  source is present, or nonfinite inputs reached the target layer.

## Seeds and disclosure

- **Seed.** 50801734 is reused on purpose, since it is the fault being
  replayed. 90101–90103 are not used.
- **Disclosure.** Before this commit the v5 child was compiled and its unit
  tests ran. `run_replay.py verify` passed. No replay has run.
