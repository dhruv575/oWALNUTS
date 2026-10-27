# AMM predictive-functional review

Status: **implementation diagnostic and proposed research; not a preregistered
qualification study**. No sampler cells, market acquisition, or remote compute
were run for this package.

The practical goal is reliable posterior updates and correctly defined predictive
quantities for an AMM research loop. Posterior accuracy, forecast calibration and
profitable quoting require separate evidence. Deployment is outside the present
objective unless there is persuasive evidence of profitability.

`predictive_oracle.py` runs 30 deterministic, input-free checks using NumPy and
SciPy. It checks exact conditional lognormal scale formulas, predictive-return
integration by two numerical methods, the distinction between mixture quantiles
and conditional medians, and noncentered AR(1) window-path preservation. It uses
no random seeds and reads no study data. `oracle-results.json` records the results,
Python/NumPy/SciPy/platform versions, and both exact-byte and LF-normalized SHA256
of the executed source. Normalized identity is provided for cross-platform Git
line-ending conversions; exact-byte identity describes the actual local execution.

From the repository root:

```console
python STUDIES/amm_predictive_review_v1/predictive_oracle.py
```

The current result is 30 checks passed. A known-parameter example shows why
omitting next-period innovation understates the scale P95: by 15.17% for an
innovation SD of 0.2, and by 28.03% for 0.4. The corresponding documentation and
window-example correction was integrated on main at `35c4aedc`. These analytic
examples do not establish market calibration or profitability.

`PROPOSAL.md` records the WP96/WP97 methodological review, a bounded supplemental
artifact analysis, and a proposed fresh predictive-functional study. Candidate
seeds are not reserved. The proposal must be finalized, independently reviewed,
committed and frozen before qualification cells. Its compute ceilings are limits,
not claims that the full workloads fit; full-size smoke timing is required.

The oracle checks finite fixtures, not every parameter value. It is not a general
production predictive API: its fixed bracket and fixture-only input checks are
not general input validation. Quadrature's reported absolute error is checked below
1e-10 and its maximum recorded. The reference integration truncates the standard-normal
innovation to [-12,12]; at the tested fixtures the bounded-CDF tail contribution
is negligible compared with the stated numerical tolerances. No trading system,
quote policy or inference default is changed by this directory.

## Bounded check of archived reference draws

`wp88-reference-audit/` preserves a separately completed post-hoc audit of six
WP88 reference origins: ticks 0,50,100 on simulated and real N=250 data. The
saved mu/log_sigma/h_last coordinates have max R-hat 1.000196, minimum bulk/tail
ESS 22,364, and zero retained divergences. P50 MCSE is 0.079-0.135% and P95 MCSE
0.160-0.319%. Thus these six references do not demonstrate the suspected gate
weakness. This is not an audit of all ticks, beta, or the full latent path.

The original report/results and byte-exact executed source `audit-executed.py`
are preserved, including their original absolute provenance paths. `audit.py`
differs only in portable source/output path selection and was not rerun during
packaging. It defaults to this checkout's root; use `--repo-root` for a checkout
holding the untracked raw draws. It writes to `rerun/` unless `--output` is given,
preserving the packaged report. Requires ArviZ in addition to NumPy. Example:

```console
python STUDIES/amm_predictive_review_v1/wp88-reference-audit/audit.py --repo-root C:/dev/owalnuts
```

WP88/WP96 compact draws omit beta, so full return prediction cannot be recovered
from those files. WP97 stores beta; the proposed full-return diagnostic is scoped
accordingly.

## Recovery update: 2026-10-27, 17:20 UTC

Authentication was renewed and the existing CPU c7a.4xlarge instance is running.
WP96 was recovered and independently reproduced: all original policies fail their
frozen qualification. Its supplemental analytic-CDF diagnostics preserve that
verdict. WP97 and the separate fixed-budget precision diagnostic are active as of
this timestamp; this is a dated status, not a claim they remain active indefinitely.
The instance backstop is 19:35:51 UTC.

Instance `i-05c712c79c74ae7f8`, region `us-east-2`, profile `owalnuts`; current
restart address `3.22.233.143`. Rediscover the public address after future restarts.
See [the feasibility addendum](FEASIBILITY-ADDENDUM-20261027.md) for prerequisites
and limitations of another fresh study. No qualification was launched by this review.
