# Amendment 1 — delta2_sidechecks_v1 (WP37A)

Frozen 2026-09-04 after protocol review and before any harness,
implementation, build, child launch, or sampling. This is an append-only
clarification of preregistration commit
`150b34ad88fa24d50392ff8c692f5308512f16a6`. The original
`PREREGISTRATION.md` and `protocol.json` remain byte-for-byte unchanged. Their
UTF-8/LF-normalized SHA-256 values remain:

- `PREREGISTRATION.md`:
  `4f61248d8207e0b3fc84f9d55e3a093b8fb963e1c6d1ba0e88ee1669a2aecf73`;
- `protocol.json`:
  `bf82f4a075c2811666b845cb90e763a94a7eb76c979d956377913be2dc9ce58b`.

Where this amendment is more specific than the original protocol, this
amendment controls. It does not change the two arms, target set, substantive
bounds, fresh seeds, planned cell count, no-rerun rule, or prohibition on a
default decision.

## A1. Updated strict Eight Schools track

The Eight Schools target is deliberately an **updated
current-final-default strict track**, not a bit-for-bit replay of the WP34
warmup configuration. Its warmup is dual averaging at target acceptance 0.95
with mass adaptation, `AcceptUnlessDivergent` warmup exhaustion, Stan diagonal
metric regularization, and no chain rescue. The retained kernel uses the
current final `MomentumSum` rule. In semantic API terms, the effective warmup
must equal:

```text
WarmupConfig::new(0.95)
  + mass_adaptation(true)
  + warmup_exhaustion(AcceptUnlessDivergent)
  + metric_regularization(Stan)
  + chain_rescue(None)
```

Every other listed historical strict-track setting is retained: the exact
noncentered target, observations, scales and starts; four sequential chains
and one thread; 1,000 warmup plus 1,000 retained; `h0 = 0.3`; depth 8; one
minimum micro-step; eight refinement levels; divergence threshold 1000; the
`walnutpie` sampling boundary without an initial-evaluation cache; callback
cap 10,000,000; and three separate timing repetitions. The arm's fixed
`max_error` (1 or 2) remains the only arm difference.

## A2. Exact estimators, transforms, and pooling

The analysis environment is Python with **ArviZ 0.23.4**. For every scalar,
the following estimators are frozen:

- rank-normalized folded split R-hat is `arviz.rhat(method="rank")`;
- bulk ESS is `arviz.ess(method="bulk")`;
- tail ESS is the minimum of the ArviZ quantile ESS at probabilities 0.05 and
  0.95, equivalently ArviZ tail ESS with `prob=(0.05, 0.95)`;
- mean MCSE is `arviz.mcse(method="mean")`;
- every ordinary sample variance or sample SD outside an ArviZ estimator uses
  `ddof=1`;
- every ordinary empirical quantile outside an ArviZ estimator uses the
  Hyndman-Fan type-7 definition (NumPy `method="linear"`).

Per-seed diagnostics always use the four original chains. Pooled diagnostics
treat each seed-by-chain series as a separate equal-length chain, without
concatenating across seeds:

- funnel: 12 x 4 = 48 chains, each of length 20,000;
- strict Eight Schools: 6 x 4 = 24 chains, each of length 1,000, using
  repetition 0 only after all three repetitions pass identity;
- Gaussian: 12 x 4 = 48 chains, each of length 1,000.

Pooled scalar means, tail probabilities, and variances flatten every retained
draw in the arm; all cells have equal retained length, so no seed receives
extra weight. Variances use `ddof=1`.

For Eight Schools, transforms are applied draw by draw before diagnostics:

```text
tau        = exp(log_tau)
theta_i    = mu + tau * z_i, i = 1..8
mean_theta = (theta_1 + ... + theta_8) / 8
sd_theta   = sqrt(sum_i (theta_i - mean_theta)^2 / 7)
```

Thus `sd_theta` is the within-draw sample SD over eight schools with
`ddof=1`. The across-draw SD of each of the six functionals also uses
`ddof=1`.

For each funnel tail event separately, the required batch MCSE splits every
original 20,000-draw chain into 40 consecutive, nonoverlapping 500-draw
batches. It computes the event proportion in each batch, then computes the
sample SD (`ddof=1`) of all 1,920 batch proportions and divides by
`sqrt(1920)`. No batch crosses a chain or seed boundary. ArviZ mean MCSE for
the indicator is also reported; the fixed substantive bounds remain the
gate.

## A3. Conservative E2 equivalence rule

The original E2 inequalities are replaced. After repetition identity is
established, use repetition 0 and the pooled 24-chain representation above.
For each functional and arm `a`, let:

- `m_a` be the flattened pooled mean;
- `s_a` be the flattened pooled sample SD (`ddof=1`);
- `u_a` be the pooled ArviZ mean MCSE;
- `s_pool = sqrt((s_fixed1^2 + s_fixed2^2) / 2)`;
- `u_combined = sqrt(u_fixed1^2 + u_fixed2^2)`.

Every one of the six functionals must satisfy both:

```text
abs(m_fixed2 - m_fixed1) + 2 * u_combined <= 0.10 * s_pool
abs(s_fixed2 - s_fixed1)                  <= 0.15 * s_pool
```

The SD rule deliberately has no bootstrap or uncertainty allowance. This
avoids making equivalence easier as Monte Carlo uncertainty grows. A
nonfinite input or `s_pool <= 0` fails E2.

## A4. Per-child timeouts

The timeout measured by the parent from successful process creation through
child exit is:

| target | timeout |
|---|---:|
| funnel | 3,600 seconds |
| strict Eight Schools, each repetition | 900 seconds |
| Gaussian | 600 seconds |

Crossing the target's deadline is process-invalid even if a raw result appears
later. The child is terminated, the timeout and any late-file state are
recorded, and the cell is never rerun.

## A5. Validity, schema, configuration, and failure predicates

A cell is **process-valid** if and only if all of the following hold:

1. its tuple `(ordinal, target, seed, repetition, arm, sentinel)` is one
   unique entry in the canonical manifest in A8;
2. exactly one authenticated create-new launch marker and exactly one durable
   process record exist for that tuple, and their nonce/tuple agree;
3. the child was created successfully, did not time out, and exited once with
   status 0;
4. stdout and stderr were closed and their recorded byte counts and SHA-256
   values match the durable files;
5. exactly one atomically published raw-result file existed before child exit,
   and its recorded byte count and SHA-256 match;
6. the process record itself is complete and parseable.

A clean child may encode a returned sampler error in its raw result and remain
process-valid; that is a substantive failing observation. A crash, nonzero
exit, timeout, missing/late/partial result, duplicate marker/record, or hash
mismatch is process-invalid.

A process-valid cell is **schema-valid** if and only if its raw JSON has the
frozen schema identifier and completion sentinel; exactly matches the
manifest tuple; has one of the two permitted variants (`samples_complete` or
`sampler_error`); and contains all target-specific dimensions, chain counts,
transition counts, repetition metadata, work counters, telemetry counters,
effective configuration, provenance hashes, and required estimator inputs
with the required JSON types and array shapes. A `samples_complete` payload
must contain exactly four equal-length retained chains of dimension 10, 10,
or 100 and length 20,000, 1,000, or 1,000 for funnel, Eight Schools, or
Gaussian respectively. A `sampler_error` payload must contain the error stage,
class, message, and all counters known up to the error. Missing, malformed,
wrong-shaped, duplicate, or contradictory fields are schema-invalid.
Nonfinite scientific values represented by the schema are substantive
failures, not silently converted into schema exclusions.

A schema-valid cell is **configuration-authenticated** if and only if:

1. its baseline, preregistration, amendment, harness source/tree, binary,
   Cargo lockfile and effective-config hashes match the selected committed
   provenance record;
2. target, seed, arm, repetition, starts/initializer, chain/thread counts,
   warmup/retained counts, timeout, callback/admission limits, metric,
   adaptation, kernel options and no-rescue setting equal the frozen
   target/arm configuration;
3. `fixed1` has `max_error = 1.0`, `fixed2` has `max_error = 2.0`, and no
   other serialized effective setting differs within a paired target cell;
4. the initial-position hashes agree between paired arms for each
   seed/chain, and all three Eight Schools repetitions agree for each
   seed/arm/chain;
5. the runtime algorithm revision and binary hash are identical across all 84
   children.

Any false predicate is configuration-invalid. Process validity, schema
validity, and configuration authentication are evaluated before scientific
gates and are never repaired with a replacement run.

For E4, divergence rate and maximum-depth rate use the fixed denominator
**4,000 retained transitions** (four chains x 1,000), with counts summed over
chains. The original 0.01 thresholds therefore mean at most 40 events each.
After repetition identity, scientific E4 counters use repetition 0; process
and identity predicates use all three repetitions.

For each paired seed (and, for process/sampler status on Eight Schools, each
paired repetition), "`fixed2` introduces no new failure" means: if paired
`fixed1` has zero events of a listed class, `fixed2` must also have zero. The
listed classes are process failure, returned sampler error, any nonfinite draw
or required statistic, retained divergence, retained invalid stop, and
retained refinement exhaustion. The E4 divergence/depth rate thresholds and
all original health-count requirements still apply even when `fixed1` has an
event.

Every ESS/callback or ESS/call score and every ratio used by E3 or G3 must be
finite and strictly positive, with a finite positive work denominator.
Otherwise that efficiency gate fails; zero or nonfinite values are not
omitted from its aggregation.

## A6. Mechanical decision labels and scope

The original single failure label is replaced by this precedence:

1. Return `INCONCLUSIVE_NOT_QUALIFIED` if any planned launch/process record is
   missing, process-invalid, schema-invalid, configuration-invalid, provenance
   invalid, manifest/sentinel invalid, or not repetition-identical; also use
   this label when only the incumbent fails a required substantive baseline
   sanity condition and no fixed2-specific or arm-agreement gate fails.
2. Otherwise, if any complete-data fixed2 accuracy, gross-safety,
   arm-agreement, efficiency, health-count, counter-nonregression, or no-new-
   failure gate fails, return
   `FIXED2_NOT_QUALIFIED_FOR_ADAPTIVE_TO_2`.
3. Return `QUALIFIED_FOR_SEPARATE_ADAPTIVE_DELTA_STUDY` only if every original
   gate as clarified here passes.

If both arms fail a substantive condition, fixed2 has also failed and rule 2
applies. Neither non-qualification label proves that every target-adaptive
delta rule is invalid. It stops only this preregistered path that may adapt to
2; fixed 2 remains ineligible for a default decision, no adaptive-to-2
implementation proceeds, and cheaper reverse-coarsening becomes the next
research target.

## A7. All-tracked-file seed search

Before this amendment was written, the seed search was repeated against
**all tracked files** at source baseline
`443e86a3bb053ed1a2a1560caca5266427a3b35c`, including artifacts,
checksums, ledgers, and study records. There was no path exclusion:

```powershell
$pattern = '(?<![0-9A-Za-z_.])(?:93101|93102|93103|93104|93105|93106|93107|93108|93109|93110|93111|93112)(?![0-9A-Za-z_.])'
git grep -n -P $pattern 443e86a3bb053ed1a2a1560caca5266427a3b35c -- .
```

Git returned exit 1 and no output, recorded as **`NO_MATCHES`**. The
lookarounds exclude only digit strings embedded in a larger alphanumeric,
underscore, or dot token, including unavoidable hexadecimal checksum
substrings. Therefore seeds 93101–93112 remain frozen; no replacement is
needed.

## A8. Canonical 84-child manifest and repetition sentinel

The canonical manifest is the following UTF-8/LF text, including its final
newline. Columns are
`ordinal|target|seed|zero_based_repetition|arm|sentinel`.

```text
01|funnel|93101|0|fixed1|SINGLE
02|funnel|93101|0|fixed2|SINGLE
03|funnel|93102|0|fixed2|SINGLE
04|funnel|93102|0|fixed1|SINGLE
05|funnel|93103|0|fixed1|SINGLE
06|funnel|93103|0|fixed2|SINGLE
07|funnel|93104|0|fixed2|SINGLE
08|funnel|93104|0|fixed1|SINGLE
09|funnel|93105|0|fixed1|SINGLE
10|funnel|93105|0|fixed2|SINGLE
11|funnel|93106|0|fixed2|SINGLE
12|funnel|93106|0|fixed1|SINGLE
13|funnel|93107|0|fixed1|SINGLE
14|funnel|93107|0|fixed2|SINGLE
15|funnel|93108|0|fixed2|SINGLE
16|funnel|93108|0|fixed1|SINGLE
17|funnel|93109|0|fixed1|SINGLE
18|funnel|93109|0|fixed2|SINGLE
19|funnel|93110|0|fixed2|SINGLE
20|funnel|93110|0|fixed1|SINGLE
21|funnel|93111|0|fixed1|SINGLE
22|funnel|93111|0|fixed2|SINGLE
23|funnel|93112|0|fixed2|SINGLE
24|funnel|93112|0|fixed1|SINGLE
25|eight_schools_strict|93101|0|fixed1|REPEAT_1_OF_3
26|eight_schools_strict|93101|0|fixed2|REPEAT_1_OF_3
27|eight_schools_strict|93101|1|fixed2|REPEAT_2_OF_3
28|eight_schools_strict|93101|1|fixed1|REPEAT_2_OF_3
29|eight_schools_strict|93101|2|fixed1|REPEAT_3_OF_3
30|eight_schools_strict|93101|2|fixed2|REPEAT_3_OF_3
31|eight_schools_strict|93102|0|fixed2|REPEAT_1_OF_3
32|eight_schools_strict|93102|0|fixed1|REPEAT_1_OF_3
33|eight_schools_strict|93102|1|fixed1|REPEAT_2_OF_3
34|eight_schools_strict|93102|1|fixed2|REPEAT_2_OF_3
35|eight_schools_strict|93102|2|fixed2|REPEAT_3_OF_3
36|eight_schools_strict|93102|2|fixed1|REPEAT_3_OF_3
37|eight_schools_strict|93103|0|fixed1|REPEAT_1_OF_3
38|eight_schools_strict|93103|0|fixed2|REPEAT_1_OF_3
39|eight_schools_strict|93103|1|fixed2|REPEAT_2_OF_3
40|eight_schools_strict|93103|1|fixed1|REPEAT_2_OF_3
41|eight_schools_strict|93103|2|fixed1|REPEAT_3_OF_3
42|eight_schools_strict|93103|2|fixed2|REPEAT_3_OF_3
43|eight_schools_strict|93104|0|fixed2|REPEAT_1_OF_3
44|eight_schools_strict|93104|0|fixed1|REPEAT_1_OF_3
45|eight_schools_strict|93104|1|fixed1|REPEAT_2_OF_3
46|eight_schools_strict|93104|1|fixed2|REPEAT_2_OF_3
47|eight_schools_strict|93104|2|fixed2|REPEAT_3_OF_3
48|eight_schools_strict|93104|2|fixed1|REPEAT_3_OF_3
49|eight_schools_strict|93105|0|fixed1|REPEAT_1_OF_3
50|eight_schools_strict|93105|0|fixed2|REPEAT_1_OF_3
51|eight_schools_strict|93105|1|fixed2|REPEAT_2_OF_3
52|eight_schools_strict|93105|1|fixed1|REPEAT_2_OF_3
53|eight_schools_strict|93105|2|fixed1|REPEAT_3_OF_3
54|eight_schools_strict|93105|2|fixed2|REPEAT_3_OF_3
55|eight_schools_strict|93106|0|fixed2|REPEAT_1_OF_3
56|eight_schools_strict|93106|0|fixed1|REPEAT_1_OF_3
57|eight_schools_strict|93106|1|fixed1|REPEAT_2_OF_3
58|eight_schools_strict|93106|1|fixed2|REPEAT_2_OF_3
59|eight_schools_strict|93106|2|fixed2|REPEAT_3_OF_3
60|eight_schools_strict|93106|2|fixed1|REPEAT_3_OF_3
61|gaussian100|93101|0|fixed1|SINGLE
62|gaussian100|93101|0|fixed2|SINGLE
63|gaussian100|93102|0|fixed2|SINGLE
64|gaussian100|93102|0|fixed1|SINGLE
65|gaussian100|93103|0|fixed1|SINGLE
66|gaussian100|93103|0|fixed2|SINGLE
67|gaussian100|93104|0|fixed2|SINGLE
68|gaussian100|93104|0|fixed1|SINGLE
69|gaussian100|93105|0|fixed1|SINGLE
70|gaussian100|93105|0|fixed2|SINGLE
71|gaussian100|93106|0|fixed2|SINGLE
72|gaussian100|93106|0|fixed1|SINGLE
73|gaussian100|93107|0|fixed1|SINGLE
74|gaussian100|93107|0|fixed2|SINGLE
75|gaussian100|93108|0|fixed2|SINGLE
76|gaussian100|93108|0|fixed1|SINGLE
77|gaussian100|93109|0|fixed1|SINGLE
78|gaussian100|93109|0|fixed2|SINGLE
79|gaussian100|93110|0|fixed2|SINGLE
80|gaussian100|93110|0|fixed1|SINGLE
81|gaussian100|93111|0|fixed1|SINGLE
82|gaussian100|93111|0|fixed2|SINGLE
83|gaussian100|93112|0|fixed2|SINGLE
84|gaussian100|93112|0|fixed1|SINGLE
```

Its SHA-256 is
`7ed4837570692ce2c7f44939d0e32b276b14eb834d86b4869d3de44149138c86`.
The pre-evidence manifest sentinel requires exactly 84 unique tuples, target
counts 24/36/24, ordinals 1–84 without gaps, and this hash.

`SINGLE` requires exactly repetition 0. For every strict Eight Schools
`(seed, arm)` pair, the three required sentinels are exactly
`REPEAT_1_OF_3`, `REPEAT_2_OF_3`, and `REPEAT_3_OF_3`, at repetition indices
0, 1, and 2. The parent tracks a three-bit repetition mask initialized to
`000`; each create-new marker irreversibly sets its indexed bit, and the pair
is complete only at `111`. A set bit forbids another launch even if the child
failed. Any missing, duplicate, out-of-manifest, wrong-sentinel, wrong-order,
or non-`111` final repetition state triggers
`INCONCLUSIVE_NOT_QUALIFIED`.
