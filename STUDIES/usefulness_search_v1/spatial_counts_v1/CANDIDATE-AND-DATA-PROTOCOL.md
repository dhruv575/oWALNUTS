# Spatial partial-census inference candidate

Hypothesis,not established advantage: spatially heterogeneous count inference
may need a richer model than the exact temporal changepoint control that defeated
the preceding candidate. Larger latent dimension may challenge cheap importance
correction,but that must be tested,not assumed. Do not weaken native controls.

Source:spatstat/spatstat.data commit3316eca0ef691ee8717fb4421918dd95978b5560,
data/bei.rda and its original man/bei.Rd and DESCRIPTION. Package license GPL>=2;
preserve attribution and data-source references. Documentation describes3605
Beilschmiedia pendula locations in a1000x500m Barro Colorado Island rectangle,
plus elevation and gradient covariates. This public dataset is exposed,not
blinded new data; do not imply a new census or future-time forecast.

Freeze20x10 equal50m-square cells,centres25,75,... metres. Cell intensities mean
full-census expected counts per2500m2 cell,not pointwise density; model is a
discretized count model,not an exact continuum point-process likelihood.
Primary partial census uses independent per-point Bernoulli(.2) inclusion,
NumPy PCG64 seed952000001,in original source order. Remaining points are the
historical heldout partial census (exposure.8). No resampling for favorable
counts. Later reserved split seeds952000002..4 cannot be used for settings
selection on the primary split. They share the same spatial realization and
cannot establish population-wide generalization or independent site replication.

Retain original coordinates,mask,full/train/heldout cell counts,cell boundaries
and provenance. Check point conservation and disjoint inclusion,bounds and
source point count. Extract elevation and gradient at cell centres using exact
matching raster coordinates if available;otherwise stop this preparation rather
than silently choose interpolation. Standardize each covariate using all200
known cell covariates (no outcome data),retaining means/SDs. Scale coordinates
by100m. No heldout scores until inference,predictive and uncertainty rules freeze.

Proposed GP model frozen here: rho~Gamma(shape2,rate1) in100m units,
alpha~halfNormal(0,2),RBF covariance+jitter1e-10. Log full-census cell intensity
f=beta0+beta_elev*z_elev+beta_grad*z_grad+L*z;beta0~N(0,5),slopes~N(0,2),
z~N(0,I). Training y~Poisson(.2*exp(f)). Noncentered coefficients and latent field.
205 unconstrained parameters; no model selection from heldout counts.

Required competitors before advancing: tuned native NUTS on identical target;
conditional Laplace/defensive importance correction with all setup cost; a
terrain-only Poisson regression with qualified low-dimensional uncertainty;
homogeneous and nonspatial cell-rate count controls; and training-selected spatial
kernel smoothing with edge correction. Prefer a cheap method if it gives the
needed uncertainty and prediction. Candidate endpoint is heldout spatial count
prediction and intensity uncertainty,not biodiversity decisions or conservation
outcomes. Strong calibration and whole-workflow cost are separate requirements.
No practical,unique or novel contribution is presently claimed.

This stage prepares and validates data only. Bound parsing/preparation120s/2GiB/
16MiB;retain failures. Numerical model preflight and inference budgets require
their own reviewed freeze before execution. Source and parser versions recorded.
