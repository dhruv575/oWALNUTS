# Diagnose the all-zero stress cases without replacing the failed panel

The fixed nine-case panel has six qualified two-method comparisons and three
failed all-zero comparisons. Both methods fail at caps 1 and 2; the independent
slice control also fails at cap .5. Mean agreement when diagnostics fail does
not qualify a reference. Preserve all failures and original seeds/budgets.

The all-zero likelihood permits very small latent observation scales together
with a beta restricted to a correspondingly tiny interval. A proper posterior
can still have severe scale/location coupling. Test this hypothesis by examining
saved chain trajectories of log_sigma, mean(h), beta and beta/exp(mean(h)/2),
alongside chain-specific distributions and depth saturation. Do not interpret
pooled means alone or extend the original budget post hoc.

A candidate exact coordinate change for a separately declared follow-up is
beta=exp(mean(h)/2)*b, with log Jacobian mean(h)/2. The density must retain the
original Gaussian prior on physical beta; assigning a new Gaussian prior to b
would change the scientific model. This reparameterization is exploratory and
does not itself provide an independent posterior reference. Verify transformed
density and derivatives against the original target before sampling. Retain
physical parameter summaries so any comparison is on the same target.

The native WALNUTS bounded-scale callback now has deterministic admission.
A later fixed sampler panel must include failed stress cases, compare physical
coordinates, separate warmup from retained events, and report all costs.
Native parity cannot justify skipping the geometry diagnosis or selecting a
prior cap by which implementation is easiest to sample.

These development experiments do not establish a market prior, predictive
calibration, economic decision value, profitability, or paper novelty.

## Saved-trace diagnosis

The read-only audit `diagnose_bounded_zero.py` found stark chain-location
differences at cap 2. NUTS chain medians of mean(h) were about -60 to -63;
slice chain medians were about -164 to -177. These are failed chains and neither
set is an estimate we can endorse. At cap .5 the respective medians were about
-27.2 to -27.4 and -26.4 to -27.0. The cap-2 slice log_sigma medians were about
.6923, very close to log(2)=.6931. This supports investigating scale/location
coupling and boundary concentration; it does not prove that reparameterization
will suffice or that either chain has found the posterior's dominant region.

`bounded_scale_rescaled.py` implements the exact coordinate change above.
Ten tests passed, including finite differences for every coordinate at T=1,
12 and 250 for all three caps, and a representable extremely small beta.
The first test command used a local environment without pytest; the default
Python environment then ran all tests successfully. No new sampling occurred.
