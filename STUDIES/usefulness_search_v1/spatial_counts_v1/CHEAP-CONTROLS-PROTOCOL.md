# Cheap prediction controls, frozen before evaluation 2026-10-31

Training counts and known coordinates only; do not open HELDOUT.json. Preserve
five-fold multinomial splitting of each training cell count, equal probabilities,
PCG64 seed952400001. Each fit uses exposure.16; internal validation exposure.04.
Select the largest smoothing bandwidth (or largest shrinkage shape) on exact
score ties. These internal scores select settings and are not heldout evidence.

Spatial smoother: Gaussian weights on cell centers in100m units, normalized
per receiving cell over the observed rectangle. This is a discretized boundary
correction and preserves constant intensities; not an exact continuum integral.
Bandwidth grid .25,.5,1,2,4,8. Rate estimate K*y/(exposure*row_sum(K)); plug-in
Poisson prediction, no posterior-uncertainty claim. Select summed validation
Poisson log likelihood across the five fixed folds.

Independent gamma-Poisson empirical Bayes: prior shape in
.1,.25,.5,1,2,4,8,16,32,64,128,256,1000000; prior mean equals the mean count
divided by fitting exposure, fitted separately inside each fold. Select summed
negative-binomial posterior-predictive log likelihood. Final mean fitted only
on all training counts. Hyperparameter uncertainty is omitted and must be
labeled. Also retain fixed independent Gamma(.5,rate.025) cell prior and exact
homogeneous shared Gamma(.5,rate.025) rate posterior. Priors not selected from
heldout results. Same full-census count-rate units as the GP.

Checks: folds conserve each cell count; kernel constant-rate preservation;
all rates finite positive; conjugate predictive probability sums and first
two moments agree with independent numerical summation (three moderate cases).
Record full grids, selected parameters, 200-cell rates or Gamma parameters,
source/data hashes and elapsed time. Local job120s/1GiB/16MiB, disk floor1GiB.
No application or predictive improvement claim before frozen heldout scoring.
