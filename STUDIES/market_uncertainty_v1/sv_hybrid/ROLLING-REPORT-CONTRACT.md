# Rolling implementation comparison: reporting contract

Written while the six-path campaign is running. This adds analysis requirements;
it does not change sampling, admission, seeds, resource bounds or stopping rules.
These are exposed development months, not confirmatory predictive evidence.

## Denominators and comparisons

Keep all six NUTS paths and all 48 planned sentinel slots. NUTS job j maps to
E72 K400 job 2*j: the same month, chronological window and replicate index.
The replicate index is a bookkeeping match, not a shared random-number stream.
Verify the causal window hash and label index before comparing any sentinel.
Use the same E70 reference estimates and flags as E72, keeping the two flagged
reference windows visible. Report all-reference and passing-reference subsets
with their planned and available counts; do not replace failed references.

Preserve not-started, timeout, native-failure, scoring-failure and complete
statuses separately. Missing scores are unavailable, never zero. Report
completed path totals separately from partial-path elapsed times and completion
fractions. Neither deleting failures nor extrapolating partial throughput yields
a measured full-path speedup. E72 K1600's two January timeouts remain part of the
earlier experiment and are not repaired by this comparison.

## Evidence and precision

Require drained terminal supervision before final analysis. Validate journal
completion entries against immutable record hashes, then verify referenced
arrays and compact draw files. Reconstruct pointwise log density and PIT from
the saved per-chain/per-draw arrays. Reuse the established autocorrelation-aware MCSE
calculation with its stated limitations; report unavailable numerical estimates
explicitly. Treat shared reference errors and repeated chronological windows as
dependent. Do not combine two candidate MCSEs as independent uncertainty for an
algorithm contrast or treat 48 slots as independent replications.

At retained ticks, cross-check compact arrays against full trace extraction and
report posterior diagnostics for the full target coordinates, not just the
four compact predictive coordinates. Summarize recorded divergences across all
completed updates. Zero divergences alone does not establish posterior fidelity;
sentinel diagnostics cannot certify unretained windows. Initialization uses only
200 retained draws and must be distinguished from 400-draw update fits.

## Computational interpretation

Report end-to-end campaign and per-path elapsed time, initial compilation and
adaptation, update time, scoring and serialization, plus sampled utilization,
peak memory and output. Do not add overlapping timing categories or interpret
wall time as target evaluations. NUTS target-evaluation counts are unavailable.
Its new 1,000-step adaptation on every update is real charged work; WALNUTS
inherits its adapted state. Equal retained counts do not mean equal work.

Any observed contrast is between these concrete implementations and settings.
It does not isolate the WALNUTS algorithm from compilation, initialization,
metric reuse, adaptation schedule or sampler implementation. Report negative
results and retain the already observed cold-fit advantage of NUTS over the
blocked specialist, which is a different comparator from WALNUTS.

## Claims withheld

No whole-path posterior qualification follows from completion. No untouched-data
predictive gain follows from this development comparison. No decision-value,
profitability, algorithm uniqueness or submission-readiness claim follows from
sampling speed or reference proximity. Each remains a separate research gate.
