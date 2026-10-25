# WP50E: deterministic replay of the WP50D static fault

This study is a process and engineering diagnostic, not posterior evidence.
It replays seed 50801734 (the single WP50D `static_unserialised` fault) in
the same configuration:

- **Gating arms:** the owned worker ×3 and the unserialised dispatch ×3.
- **Fidelity arm:** the byte-identical WP50D exe ×3.
- **Descriptive arms:** the research `RejectLeaf` policy under each dispatch.

Passive proposal and transition observers record chain 2's transitions 0..9,
and a pass-through target wrapper counts what the target saw. It was frozen at
`d7f2c97a` and run once. No library code was changed.

## Result (`artifacts/result.md`)

**Frozen verdict: `NOT_ESTABLISHED_NONDETERMINISTIC`.**

- **Reproduction.** The identical `Numerical` error "kernel attempted a
  nonfinite target position (chain 2, transition 9)" reproduced in 6/6
  gating replays, plus 3/3 with the original exe.
- **Within each arm.** The chain-2 stream was bit-identical across the three
  replays: 7,705 observations, 763 target calls.
- **Across arms.** The frozen all-six stream-hash identity failed, A vs B.

**Post-hoc localisation.** The only differing field is the gradient buffer
reported on 1,512 recoverable (Stan-exception) evaluations: zeros from the
owned worker, the NaN prefill from the direct dispatch. Positions, steps,
momenta, energies, call counts, completed transitions and the overflow
observation are bit-identical. Under `RejectLeaf`, both dispatches complete
with bit-identical draws.

**Integration question.** This is not an integration bug. The kernel aborts
under the shipped `Abort` policy before calling the target: 0 nonfinite
inputs reached the target layer, and there was no `TargetError` source.

## Reproduce

```
python build_child.py && python run_replay.py verify
python run_replay.py analyze && python describe.py   # the single run already happened
python checksums.py verify
```
