# Synthetic price-cell kernel checks, 2026-10-28

Five checks passed locally under the existing Python 3.14 research environment
(3.886 seconds), and on the existing AWS instance under the pinned Python 3.12
research environment (3.204 seconds, outer timeout 60 seconds).

The kernel includes normalized Student-t transition constants and the logistic
change-of-variables Jacobian. Its integral is the observation event probability,
not one: posterior normalization conditional on the observed event is separate.

Coverage:

- Conditional log kernel agrees with SciPy Student-t log densities at nonuniform
  cells; analytic u gradients agree with central finite differences.
- Three one-cell integrals agree with independent Student-t CDF differences.
- A two-cell tied-price integral agrees with a nested price-space integral that
  evaluates the last transition analytically. A product of independent return
  probabilities differs, confirming that dependence matters in this fixture.
- Coordinates at +/-40 and +/-1000 retain finite log kernels and the limiting
  Jacobian gradient, including where floating-point logistic saturates.
- Zero-width, reversed and nonfinite cells are rejected.

These are conditional, low-dimensional mathematical checks. They do not test
the full SV parameter gradient, posterior sampler fidelity, narrow market-scale
cell conditioning, historical rounding rules, missingness or economic claims.
Quadrature uses finite transformed-coordinate bounds and ordinary numerical
error tolerances; it is numerical corroboration, not a replacement for the
analytic propriety proof. The implementation is a research kernel, not yet a
replacement for the frozen market target.

AWS had 30,048 MiB available memory and 8.3 GiB disk available at this check.
No sampling campaign was running. The next useful compute work is full-target
synthetic validation, after implementing independently checkable SV derivatives;
running further unchanged improper-target comparisons would not advance fidelity.

## Full SV extension

`price_cell_sv.py` now supplies the normalized-prior joint log target and all
analytic gradients in (mu,log_sigma,beta,z,u). Independent direct recurrence and
SciPy density checks agree for T=1,4,12; central finite differences check every
coordinate, including drift, innovation scale, stationary initial state and
latent-price coordinates. Fixtures contain repeated price cells. The full test
passed locally; the combined six-test suite passed on pinned AWS Python 3.12 in
3.212 seconds under a 60-second timeout.

`price_cell_sv.stan` is a separately expressed autodiff candidate. It has not yet
been compiled or compared with the analytic implementation. That comparison,
including T=250 and broad finite parameter fixtures, is the next gate before
bounded synthetic sampling. These finite checks are not a global numerical
stability guarantee or evidence of posterior sampling fidelity.

## Independent Stan comparison completed

BridgeStan compiled the independent implementation and all 16 deterministic
fixtures passed (T=1,4,12,250; four cases each). Cases include tied cells,
nonuniform widths, width 1e-6, and transformed coordinates up to +/-1000.
Normalized density comparisons explicitly set `propto=False`. Maximum absolute
log-density error was 2.9104e-11; maximum absolute gradient error was 1.1642e-9.
The run took 13.337 seconds including compilation, with four compiler jobs and
an outer 240-second timeout. The source-bound report is preserved under
`evidence/price-cell-stan-20261028`.

BridgeStan warned about loading the same shared object repeatedly. This run
compiled once before constructing the 16 data-specific models; it did not
recompile between loads. The warning therefore does not indicate a changed
library was silently reused in these comparisons.

The next gate is bounded synthetic posterior sampling and independent
reference checks. Historical observation semantics remain unresolved, so these
results do not admit a market-data campaign or rescue the old target's claims.
