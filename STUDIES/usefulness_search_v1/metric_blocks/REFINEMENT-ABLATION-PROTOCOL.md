# Exposed refinement/error-threshold factorial

Fixed metrics, native steps, starts and seeds from matched_geometry01. Baseline
is the preserved two-level,local-error1 runner. Evaluate three additional cells
per recoverable target: (levels1,error1),(levels1,error1000),(levels2,error1000).
All five recoverable targets are included; ARMA remains failed recovery. No
step-size tuning. No kernel source change. This2x2 decomposition avoids equating
removing refinement with simultaneously relaxing the error threshold.

First require analytic rotated-Gaussian accuracy for the1/1000 control and exact
baseline replay at2/1. Confirm reported tuning values and zero reverse work for
single-level cases. Original divergence reporting is unchanged. The1/1000 arm
is NUTS-like, not assumed identical to native NUTS: turning, orbit selection and
divergence handling may still differ.

Re-use2000-draw accuracy gates and reference/cost accounting from the matched
geometry diagnostic. Only jointly qualified comparisons receive ratios; no
runtime comparison. Report ratios versus both baseline WALNUTS and native NUTS,
including pilot costs. This is an exposed mechanism study; no default promotion
or application claim, regardless of results.15workers180s/2GiB/64MiB,one at a
time,BLAS1,diskfloor1GiB. Preserve exceptions and numerical failures.
