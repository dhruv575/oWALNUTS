# Public CFunc continuation precision worker

`pymc_continuation_workflow.py` is an exploratory local-level worker. It uses the
existing normalized PyMC model, independent runtime JAX parity, canonical starts,
canonical output conversion, all-coordinate health screen, five functionals and
observed predictive interval precision screen. It changes the execution policy:
one admission and one warmup, followed by retained increments to 1/2/4/8 thousand
draws per chain. The public session freezes adaptation after warmup.

Example (run through the study's contained hardware launcher for timed work):

```text
python pymc_continuation_workflow.py --fixture fixture.json --out fresh-output --seed 123 --coordinates observation_residual --warmup 1000 --tiers 1000 2000 4000 8000
```

The output directory must not exist. Each tier has its own raw canonical draws,
fit report and attempt record. Top-level checkpoints follow warmup and surround
each tier; status remains running until the worker actually finishes. Source,
fixture, Python executable and extension identities are checked between stages.
These runtime hashes identify inputs; they do not prove that the binary was
built from those sources. A future frozen benchmark must bind a separately
attested release build and hardware/containment metadata.

Admission, adaptation, each draw request, evaluation, serialization and total
invocation costs remain visible. Failed requests retain elapsed costs and prior
successful tiers. Cleanup errors cannot replace an earlier execution error.
Warmup diagnostics are separate from retained diagnostics; cumulative work must
not be summed across successive tiers. The callback totals include initialization
and reconcile with the session's actual counter. Progress is a completed-request
snapshot, not live per-transition telemetry. External hard termination requires
the executor to record its own terminal outcome and wrapper elapsed cost.

Predictive evaluation always uses chain seed plus 130000, as in the existing
workers. This is a stable seed contract, not a promise that shape-dependent
predictive random arrays share an exact prefix. Posterior draws do share the
exact prefix. The core session retains bounded full history and the worker
serializes complete prefixes at each tier; this is not constant-memory streaming.

Validation: seven workflow tests plus four public adapter session tests passed
against the isolated release extension (11 total, 2.68 seconds). They include
real native CFunc replay against uninterrupted sampling through observation-
residual canonical transport, all nine diagnostic fields, one admission/warmup,
failure accounting, source mutation rejection and checkpoint persistence.
The release build used Rust 1.88.0 Windows GNU with `--locked`; it is preliminary,
because no before-build source manifest was captured. No speed claim or sampler
qualification follows from these tests.
