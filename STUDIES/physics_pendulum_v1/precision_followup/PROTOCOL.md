# Separately frozen precision follow-up

The original44-job pilot remains a negative result. Large-angle validation
failed primarily because future-angle mean MCSE was .013-.019rad versus the
frozen .01rad limit. All8 fits passed Rhat/ESS/divergence diagnostics. Small-angle
WAL was slower in kernel time and gains no follow-up. Do not retune either
sampler, change observations, relax precision, or claim fresh-data validation.

For the exposed large-angle case only, use the frozen raw .90 configurations
of both samplers. Four fresh seeds953500000..3, four chains500warmup/4000retained.
Unchanged model, native binary, MAP/starts, depth and accuracy gates. This is
a fixed4x retained-budget follow-up, not continuation until passing.

The original deterministic Laplace quadrature missed probability convergence:
24-vs40 order difference .00096, versus .0001. Separately evaluate40/80/160,
requiring80/160 to pass the same gates. No tuning of the approximation or
posterior. Retain its original failed integration receipt. Recompute both
nonlinear and linear96/160/256 grids as same-host workflow cost controls.
The original65536-draw nonlinear Laplace accuracy result remains a comparator;
its cost is historical and is not a fresh timing replicate.

At most12 concurrent one-core jobs,11 new jobs total. Each300s/1GiB/8MiB;
whole follow-up1200s/16GiB/128MiB, disk floor1GiB, initial>=1.25GiB.
Existing spatial/physics evidence retained. Source hashes frozen; analyze all
raw outcomes and independently verify predictions. No retry of failed jobs.

Operational correction: original outer monitor's ownership token was replaced
by nested job monitors, so its23MB peakRSS covers the driver rather than all
workers. Individual worker monitors remained active; the original campaign
finished without any limit termination and all jobs drained. Do not claim that
outer aggregate RSS or deadline cleanup was verified. Follow-up uses a DISTINCT
inner ownership environment key so the outer token survives into every child.
No scientific results change because of this supervision correction.
