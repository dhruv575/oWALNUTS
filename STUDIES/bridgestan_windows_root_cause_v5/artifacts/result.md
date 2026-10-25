# WP50E result

The study was preregistered at `d7f2c97a` and launched once (21:07–21:08
local). All 11 of 11 processes ran. There were no timeouts and no Event 1000,
and nothing was rerun.

## Frozen verdict: `NOT_ESTABLISHED_NONDETERMINISTIC`

**The error reproduced in every replay.**

- Gating arms: 6/6 (A owned 3/3, B unserialised 3/3).
- Original WP50D exe: 3/3.
- Every replay gave the identical error: `Numerical`, "kernel attempted a
  nonfinite target position (chain 2, transition 9)".

**Each arm was deterministic.** Within A, and separately within B, the
chain-2 stream was bit-identical across all three replays: 7,705
observations, last target call 763, the same hash.

**The stream identity was not.** The frozen rule required one chain-2 stream
hash across all six replays. A and B differ (`c478e86a…` vs `0e5e50a8…`), so
the frozen rule returns NOT_ESTABLISHED.

## Descriptive localisation (post hoc; `descriptive-localisation.json`)

This section does not change the verdict.

**Where the streams differ.** Across all 7,705 chain-2 proposals the **only**
differing field is the `gradient` reported for the 1,512 proposals with
outcome `Recoverable`, which are Stan exceptions:

- the owned worker returns `0.0`, because its worker allocates a zeroed
  gradient vector and copies it back on error;
- the unserialised target leaves the kernel's NaN prefill.

**What is identical between the arms:**

- the starts and every coordinate (as IEEE bits);
- step sizes, mid-step momenta, kinetic and potential energy, H, and the
  outcomes;
- target-call counts, and the completed transitions 0–8 (selected position
  and momentum, log density, gradient and adaptation);
- the first `KernelNonfinite` observation.

The kernel discards the gradient of a zero-density point, so the dynamics are
identical. With `RejectLeaf`, the owned (D) and unserialised (E) runs complete
with **bit-identical draws** (`5d7e4a62b998da28`) and identical call counts
(163,280). Chain 2 has the single rejection, at transition 9, target call 763.

**Other chains.** Chains 0 and 1 match in observation count. Chain 3's count
varies from replay to replay (10,993 to 22,257), because it is cancelled at a
timing-dependent point after chain 2 aborts. Their hashes differ between arms
only through the same recoverable-gradient field.

## The event (chain 2, transitions 0..9)

- **Start.** Chain 2 starts at a point with log density -701,443.
- **Step size.** It is in the initial fast-adaptation window, where the step
  goes 0.5, 1.17, 0.115, 0.120, 0.162, 0.254, 0.432, 0.772, 1.42, 2.66.
- **Proposals.** Within trajectories they reach |q| of up to 1e201–1e267;
  between 2 and 1,141 of each transition's proposals are recoverable Stan
  exceptions.
- **The overflow.** At transition 9 (reverse phase, refinement level 1,
  step 1.329, 2 micro-steps) the last coordinate overflows to -inf, with
  kinetic energy +inf.
- **Same class as nonfinite_position_policy_v1.** It is the same class of
  event that study recorded: an integrator overflow in the initial fast
  warmup, which `RejectLeaf` turns into one rejected leaf. This is on a
  different target.

## The integration question: not an integration bug

In every reproducing replay:

- the error kind was `Numerical`, with no target source;
- the target wrapper saw 0 nonfinite inputs and 0 fatal errors;
- there were 6,750 recoverable errors, all handled.

Under the shipped `NonfinitePositionPolicy::Abort` the kernel stops before
calling the target. No `TargetError` existed for the Replicated target to
surface. The WP50D child's exit 1 is the designed outcome of the shipped
policy, propagated by the child's `?`.

## A separate, real (minor) difference found

The two dispatches leave different gradient buffer contents on a recoverable
`TargetError`: the owned worker returns zeros, and the direct dispatch returns
the NaN prefill or whatever BridgeStan wrote. This is harmless to the kernel,
but it breaks observer and telemetry bit-parity. The opt-in direct dispatch
should normalise the error-path gradient to match the owned worker before it
is considered.
