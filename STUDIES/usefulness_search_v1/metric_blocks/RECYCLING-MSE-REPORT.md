# Replicated recycling MSE screen

| Target | Family | MSE ratio (95% CI) | Worker cost ratio | Cost-adjusted ratio (95% CI) | Advance |
|---|---|---|---|---|---|
| analytic_rotated_gaussian | mean | 1.368 [1.244, 1.510] | 0.997 | 1.372 [1.247, 1.514] | True |
| analytic_rotated_gaussian | second_moment | 1.332 [1.203, 1.474] | 0.997 | 1.336 [1.206, 1.478] | True |
| analytic_rotated_gaussian | below_zero | 1.465 [1.282, 1.675] | 0.997 | 1.469 [1.286, 1.680] | True |
| analytic_rotated_gaussian | below_minus2 | 1.695 [1.474, 1.959] | 0.997 | 1.699 [1.478, 1.964] | True |
| noncentered | mean | 1.228 [1.139, 1.358] | 0.927 | 1.326 [1.229, 1.466] | False |
| noncentered | second_moment | 1.659 [1.572, 1.751] | 0.927 | 1.790 [1.696, 1.889] | True |
| noncentered | below_zero | 1.440 [1.283, 1.658] | 0.927 | 1.554 [1.385, 1.789] | True |
| noncentered | below_minus2 | 1.214 [1.117, 1.361] | 0.927 | 1.310 [1.205, 1.468] | False |
| funnel | mean | 1.027 [1.009, 1.055] | 1.095 | 0.938 [0.921, 0.963] | False |
| funnel | second_moment | 1.037 [1.011, 1.041] | 1.095 | 0.946 [0.923, 0.951] | False |
| funnel | below_zero | 1.044 [1.017, 1.078] | 1.095 | 0.953 [0.929, 0.984] | False |
| funnel | below_minus2 | 1.020 [1.004, 1.037] | 1.095 | 0.931 [0.917, 0.947] | False |

Ratios above one favor recycling. Worker cost includes serialization/output. Intervals are exploratory paired-replicate bootstrap intervals, conditional on measured cost; not simultaneous intervals or held-out confirmation. Exact stationary starts and fixed known settings do not test a cold workflow. All functionals, split-half sensitivity, bias flags and health events are preserved in the analysis JSON. Native/recycled NUTS comparisons remain outstanding.
