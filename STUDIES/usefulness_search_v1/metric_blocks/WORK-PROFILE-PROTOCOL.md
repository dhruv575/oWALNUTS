# Existing kernel work-counter audit

Expose existing retained-work counters through an isolated runner. Do not alter
the target, step, metric, random stream or kernel. Replay all five recoverable
targets at factors1 and4 from the preserved matched-geometry and step-ladder
inputs. Require exact retained draws, actual target calls, divergences, masses,
step sizes, seeds and algorithm revision versus the old runner.

Reconcile actual calls with all-phase telemetry and retained initial+forward+
reverse calls. Report built-leaf forward microsteps separately. Forward calls
not attached to built leaves are not automatically all failed refinements:
they may include work on a leaf discarded by another check. Preserve stop counts
and accepted-level histograms. Do not interpret call fractions as wall fractions
or assume work can be removed without changing the invariant distribution.

All10 workers bounded180s/2GiB/64MiB,one at a time,BLAS1,diskfloor1GiB. These
exposed profiles select a mechanism to study; they do not validate an improvement.
