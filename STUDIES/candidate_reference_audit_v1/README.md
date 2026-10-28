# E71: fast-update approximation at 24 fixed reference points

All 24 E66 candidate mixtures were reconstructed from their sealed 4x400
chain/draw score arrays and matched the stored logpdf/PIT scores within 1e-12.
They were compared with E70's independently fitted 4x16,000 references. No
candidate values were changed and no inference was rerun.

| Descriptive scope | Points | Max absolute logpdf difference | Max absolute PIT difference |
|---|---:|---:|---:|
| All original fixed spots | 24 | 0.0360384 | 0.00388331 |
| Spots with passing E70 references | 22 | 0.0108725 | 0.00388331 |

Median candidate log-density delta-MCSE is 0.00513070 versus 0.000783222 for
the extended references. This is a comparison of the two medians, not a
median paired error ratio. The candidate therefore has more Monte Carlo
uncertainty at these points; MCSE remains a diagnostic rather than a guaranteed
error bound. The two failed extended references remain in the full result table
and are not treated as ground truth. The 22-point subset is explicitly selected
by reference diagnostics, not a new qualification population.

This does not certify whole-path posterior accuracy or quantify a predictive
advantage for exact inference. The useful next test is a frozen budget-by-seed
comparison, keeping the target and window unchanged and reporting cost together
with discrepancies. All raw inputs remain in the verified E66 and E70 archives.
The audit verifies their artifact seals before arithmetic. `results.json`
retains each candidate/reference uncertainty and signed difference separately.
