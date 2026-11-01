# Pre-inference clarification

After numerical preflight, before calibration/reference/validation outcomes:
include deterministic Laplace forecast quadrature (orders24/40 in the2D
whitened Gaussian) as well as65536 draws, so Monte Carlo overhead cannot
manufacture an expensive approximation baseline. Require last-level mean
differences<=.002 approximate SD, relative SD<=.005, angle means<=1e-4 and
event probability<=1e-4. Compare forecast accuracy against nonlinear reference.

Practical advancement additionally requires WAL's median full workflow at
least1.5x faster than qualified nonlinear reference quadrature as a competing
inference workflow, and neither Laplace variant nor qualified linear-grid
model meets the forecast tolerances. Known-truth forecast RMSE and heldout
scores remain descriptive on just two synthetic datasets. No algorithm tuning
or runtime settings changed. Laplace is defined in the sampled logit coordinates.
