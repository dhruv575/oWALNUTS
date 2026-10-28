# Frozen rolling NUTS implementation comparison

**Model-admissibility limitation:** the exact-tie derivation indicates improper
posteriors on 155 January and 311 February windows, including February sentinel
577. Independent mathematical review is pending. Historical reference flags
are not posterior-propriety certificates. These results preserve the frozen
numerical experiment; they do not establish proper-posterior fidelity or an
accuracy-matched algorithm advantage. See [the derivation](../../amm_accounting_v1/POSTERIOR-PROPRIETY.md).

All six planned paths completed, producing all 48 planned sentinel scores.
The outer campaign completed in 3,577.31 seconds, with 8.01 GB peak sampled RSS
and 1.147 GB output. The bounded analysis completed in 40.71 seconds and both
supervisors verified process drain. No failed path was replaced or extended.

| Month | Replicate | NUTS path seconds | E72 WALNUTS K400 seconds | NUTS/WALNUTS time |
|---|---:|---:|---:|---:|
| December | 0 | 2033.20 | 701.78 | 2.90 |
| December | 1 | 2013.13 | 686.43 | 2.93 |
| January | 0 | 2015.32 | 1454.91 | 1.39 |
| January | 1 | 1950.12 | 1461.73 | 1.33 |
| February | 0 | 1483.49 | 670.60 | 2.21 |
| February | 1 | 1562.90 | 671.55 | 2.33 |

NUTS compiles once per path, but performs 1,000 new warmup transitions for each
400-retained-draw update. WALNUTS retains its adapted state and performs 400
refresh transitions. Both use four chains and the same complete causal paths;
they do not use equal computational effort. These timings compare concrete
implementations and settings, not an isolated algorithm mechanism.

None of the 48 retained NUTS update fits passed every full-coordinate gate
(R-hat <=1.01, bulk/tail ESS >=400, and no divergences). Among these fits,
mu was flagged 16 times and log_sigma 11 times; innovation-coordinate flags
also occurred. There were 10 recorded divergences over all completed updates.
This is not a whole-path qualification result. Initialization diagnostics are
preserved separately, using 200 retained draws rather than 400.

Across the 48 numerical pairs, NUTS had smaller absolute reference discrepancy
in 21 log-density and 21 PIT comparisons. Its estimated MCSE was smaller in
29 log-density and 32 PIT comparisons. These dependent, exposed-development
counts are descriptive; they are not independent binomial tests or confirmatory
predictive effects. One of the fixed reference windows has exact ties. The
largest available NUTS discrepancy among historically passing references was
0.111618 log-density units. No unavailable target-evaluation counts were invented.

Reporting checks matched journal hashes, causal indices, packed array metadata,
compact values, pre-score native records, retained trace/draw identities and
the paired conditioning-window/label identities. All 54 initialization/update
diagnostic slots remain in the evidence. The 65 downloaded reporting files
matched the sealed manifest and the analysis completion hashes. The complete
9,175-file evidence tree was sealed and its downloaded archive verified against
every member hash, including all 54 full traces. The archive is 1,102,583,479
bytes with SHA-256
`0fe2a1b363cd6c6858d163dae1fd7ee52aac63b14dfdad0b2d4c41bf525a3abe`.
S3 upload and exact-version restoration remain separate preservation steps.

Evidence: [report bundle](evidence/rolling-market-result-20261028/COMPARISON.json),
[full diagnostic inventory](evidence/rolling-market-result-20261028/diagnostics/SUMMARY.json),
and [frozen reporting contract](ROLLING-REPORT-CONTRACT.md).
Posterior admissibility and a justified observation/prior repair now take
priority over additional tuning of this target. No economic or uniqueness
claim follows from the relative timings.
