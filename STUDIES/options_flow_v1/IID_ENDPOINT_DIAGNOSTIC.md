# Independent iid endpoint diagnostic

`exact_iid_quantile_control.py` constructs distribution-free quantile confidence
bounds using binomial order-statistic ranks. For fixed-size iid continuous draws,
the number below the true p-quantile is Binomial(n,p). Each tail receives
alpha/(2m), giving simultaneous coverage of at least 1-alpha for m prespecified
quantiles. Small samples can correctly produce infinite bounds. This control
does not apply to autocorrelated MCMC draws or optional stopping.

Six focused tests passed on integrated main (0.63 seconds), including independent
enumeration of small binomial probabilities and full multinomial enumeration of
joint two-endpoint coverage. There is no Monte Carlo in these tests.

The posthoc `diagnose_iid_bank_quantiles.py` reconstructed every one of the 24
iid-null main trials from the frozen allocation campaign. It verifies the frozen
plan, archived generator, runtime and audited result/bank hashes. Regenerated
pooled empirical quantiles matched the original results exactly in all 24 cases.
No new streams were introduced and no bootstrap analysis was rerun.

All 48 backend samples were checked regardless of original success: two exact
two-endpoint controls missed. The additional 24 pooled controls also had two
misses. These are per-sample simultaneous bounds, not a guarantee across all
48 backend samples or all 24 pooled samples. The full retained results are in
`artifacts/iid-bank-quantile-diagnostic-v1.json`.

The previously highlighted bootstrap miss (F8/N4096, replicate 5) is covered by
both exact backend controls and the pooled control. The pooled upper-quantile
bound is [1.64405626, 1.68417978], covering truth 1.64485363. This supports further
investigation of finite-fit bootstrap uncertainty, not a calibration verdict or
proof that the exact method is uniformly superior. In particular, the exact
control allocates alpha across two endpoints, while the original bootstrap
allocates error across three component families as well. Their nominal error
allocations are different.

The diagnostic is posthoc and cannot qualify a prospective calibration claim.
Correlated-sample accuracy still requires an appropriate independent control.
