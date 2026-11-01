# Physics pilot: useful Bayesian inference, no WALNUTS advantage

Completed55 experiment jobs on the existing AWS host:44 in the frozen pilot,
11 in a separately frozen precision follow-up. All jobs exited and drained;
both analyses verified raw outputs against independent ODE calculations.
No new cloud resources, evidence deletion, or deployment. Two synthetic cases
are computational evidence, not validation on real hardware or neural models.

## What was tested

A damped pendulum with known initial angle, zero initial velocity, and known
Gaussian observation noise. Infer effective damping and restoring coefficient
from six noisy observations over1.5seconds; forecast angles through6seconds.
Initial angles .3 and2rad give small- and large-angle cases. The data generator
uses independent high-accuracy DOP853; samplers share native RK4 sensitivities,
likelihood, initial points, priors and tuning budgets. The equation follows
[MIT's Simple Pendulum](https://underactuated.csail.mit.edu/pend.html).

Controls include tuned native NUTS, Gaussian Laplace with Monte Carlo AND
deterministic forecast integration, a linearized pendulum, and full2D numerical
posterior integration. Grid convergence qualifies all four initial references.
Heldout outcomes are opened only after sampler selection is frozen.

## Results

Small angles: both samplers pass4/4 fresh-seed accuracy checks. WALNUTS does not
win: paired median NUTS/WAL total-time ratio .962; NUTS kernel time is smaller
in every pair. Cheap nonlinear Laplace and the integrated linear model meet
the forecast tolerances, removing the demonstrated need for a costly sampler.

Large angles, initial pilot: both samplers pass conventional convergence checks,
but0/4 each meet the full precision requirement. Future-angle MCSE .013-.019rad
exceeds the .01rad limit. The Gaussian approximation misses forecast means by
about .07rad; linear-model means differ by up to1.18rad from the nonlinear
reference. Original deterministic Laplace event-probability integration also
fails its numerical convergence check; that failure remains preserved.

Large angles, separately frozen follow-up: unchanged raw .90 configurations,
four fresh seeds,4x retained draws. Both methods pass4/4, including unchanged
accuracy and MCSE limits. NUTS is faster in every paired kernel and full-cost
comparison. Median total costs: WAL6.558s, NUTS5.640s. Paired median NUTS/WAL
ratio .8655, meaning WAL takes approximately16% longer. Median kernels3.536s
versus2.593s. Whole-workflow differences include startup, prediction, diagnostics
and charged MAP preparation; report these separately from sampling performance.

Higher-order Laplace integration now qualifies numerically and still misses
the forecast tolerance: maximum mean difference .07023rad versus .02 allowed.
The qualified nonlinear grid costs8.169s, so WAL's1.246x ratio against this
control also misses the1.5x advancement gate. The original negative pilot is
not replaced by the follow-up. Neither study advances to a usefulness claim.

Known-truth large-angle forecast RMSE is .198rad for integrated nonlinear Bayes,
.246 for Laplace and .591 for the integrated linear model. These are descriptive
values for ONE exposed noise realization, not population calibration or evidence
of better control decisions. The follow-up reuses that dataset and is fresh-seed
computational evidence only. Generic follow-up analysis emits an empty case0
entry; case0 was not rerun and its original qualified reference remains valid.

## Operational audit and limitations

Both archive streams are verified locally:219 original members and78 follow-up
members; dependency between archives recorded. All83 spatial archive members
were also verified before dispatch. S3 remains pending expired AWS login; remote
originals retained. No loss or cleanup was required to fit the study.

Initial outer supervisor's ownership token was overwritten by inner monitors:
its23MB RSS is driver-only and must not be called aggregate memory. Per-job
monitors remained active. Sum of the largest16 recorded worker peaks is5.580GB,
a conservative concurrent-worker bound; all groups drained. Follow-up preserves
the outer token using a distinct inner key: measured aggregate peak3.643GB.
A separate nested-deadline test confirms descendant cleanup. Neither campaign
hit a resource limit. The generic 'solver_errors' counter also includes numerical
logit-saturation rejections; it is not a count of failed ODE trajectories.

This low-dimensional, cheap simulator does not establish where WALNUTS wins.
Do not enlarge it merely to make alternatives lose. A future physics candidate
needs an independently justified expensive model and uncertainty requirement,
qualified references, and strong specialized inference/approximation controls.
