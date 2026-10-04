# Optional shared-log-volatility likelihood

The development variant `shared_logvol_student_t_v1` factors the dense flow Student-t likelihood to compute the volatility normalization once per time step. It retains the same normalized target, priors, mixed coordinates, and automatic PyTensor gradients. `pymc_student_t` remains the default. This variant is being validated for the study workflow; it is not a default sampler change or a market-usefulness result.

For residuals `r[t,g] = y[t,g] - location[t,g]`, the likelihood is

```
T * G * (lgamma((nu + 1)/2) - lgamma(nu/2) - log(nu*pi)/2)
- G/2 * sum_t h[t]
- (nu + 1)/2 * sum_tg log1p(r[t,g]^2 * exp(-h[t]) / nu)
```

The supported candidate recipe is dense `flow`, `mixed_slopes` coordinates, and block size 32. Other combinations and observation masks must be rejected. The worker option is `--likelihood-variant shared_logvol_student_t_v1`; the candidate records a distinct arm and the variant in its report, settings, compilation metadata, and every continuation attempt and tier report. Existing default commands retain their baseline behavior. Future comparison manifests must explicitly bind the variant rather than infer it from a favorable result.

The corrected, independently audited target-call experiment is archived in [mixed-target-optimization-v4](artifacts/mixed-target-optimization-v4/RESULTS.md), commit `8720ec5`. Across two compilation orders, the median paired baseline/candidate ratio was 1.135, with three candidate-slower pairs. These dependent microbenchmark blocks do not establish sampling speed, reliable interval coverage, or a cold-compilation advantage. The earlier wrong-runtime experiment remains separately archived as failed provenance evidence.

The expression uses squaring and `exp(-h)`, so overflow and underflow remain relevant. The integrated builder was checked under the attested runtime on the fixed 18-case extreme grid: no candidate-only rejections occurred, but six cases remained nonfinite for both implementations. All outcomes were retained. This small grid is not a general numerical robustness qualification. Numerical validation compares actual compiled values and gradients, including normalized constants, rather than assuming algebraic equivalence guarantees floating-point equivalence.

The next workflow experiment must retain all intended outcomes and costs, use the actual selected runtime, keep the full diagnostic and endpoint-precision gates, and evaluate accuracy on the appropriate reference fixture. A fixed-posterior reference bank cannot establish accuracy for different datasets. Powered repeated-data calibration and chronological market evaluation remain separate requirements.

Integration evidence is archived in [the initial correctness checks](artifacts/shared-logvol-integration-v1/RESULTS.md), [the integrated boundary check](artifacts/shared-logvol-boundary-v1/RESULTS.md), and [tier identity validation](artifacts/shared-logvol-integration-tier-v2/RESULTS.md). After adding tier identity, 22 focused and continuation regression tests passed. The tiny worker intentionally failed its precision gate at both short tiers; its output validates wiring and serialization, not adequate posterior sampling.
