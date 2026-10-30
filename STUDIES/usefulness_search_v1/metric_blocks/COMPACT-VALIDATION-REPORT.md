# Fresh compact-recycling validation

| Target | Family | MSE ratio (95% CI) | Direct cost ratio | Cost-adjusted ratio | Descriptive range |
|---|---|---|---|---|---|
| analytic_rotated_gaussian | mean | 1.299 [1.142, 1.443] | 1.078 | 1.205 | [1.016, 1.433] |
| analytic_rotated_gaussian | second_moment | 1.312 [1.192, 1.453] | 1.078 | 1.217 | [1.060, 1.443] |
| analytic_rotated_gaussian | below_zero | 1.348 [1.164, 1.524] | 1.078 | 1.251 | [1.035, 1.514] |
| analytic_rotated_gaussian | below_minus2 | 1.293 [1.121, 1.462] | 1.078 | 1.199 | [0.997, 1.452] |
| noncentered | mean | 1.370 [1.268, 1.513] | 1.142 | 1.199 | [1.092, 1.350] |
| noncentered | second_moment | 1.653 [1.566, 1.743] | 1.142 | 1.447 | [1.349, 1.555] |
| noncentered | below_zero | 1.638 [1.462, 1.877] | 1.142 | 1.435 | [1.259, 1.674] |
| noncentered | below_minus2 | 1.300 [1.189, 1.457] | 1.142 | 1.139 | [1.024, 1.300] |
| funnel | mean | 1.017 [1.005, 1.032] | 1.163 | 0.875 | [0.854, 0.900] |
| funnel | second_moment | 1.042 [0.980, 1.060] | 1.163 | 0.896 | [0.832, 0.924] |
| funnel | below_zero | 1.074 [1.053, 1.100] | 1.163 | 0.924 | [0.895, 0.960] |
| funnel | below_minus2 | 1.016 [1.000, 1.032] | 1.163 | 0.874 | [0.849, 0.900] |

Predeclared scoped primary passed: False.
No general improvement or application claim. Coverage diagnostics, all coordinate results, events and exact truths are in the JSON. Cost-adjusted endpoint ranges are descriptive, not joint 95% intervals. Native/recycled NUTS and cold-workflow validation remain outstanding.
