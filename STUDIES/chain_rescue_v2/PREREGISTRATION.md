# chain_rescue_v2 — preregistration (WP36)

Frozen 2026-09-04 before candidate implementation and before any study cell.
The machine-readable protocol is `protocol.json`. The source baseline is
commit `17f1d97` (the merge containing WP35 and the follow-up process
diagnostic). This commit contains only the preregistration scaffold: no study
harness, candidate implementation, or evidence.

## Question and evidence basis

WP33 made immediate `restart_from_best` the multi-chain default after
`chain_rescue_v1`. WP35 then recorded 30 restarts in 21 cells: 21
log-density and nine step events, including an early log-density restart on
every `hmm_drive_0` seed, restarts on `kidiq`, `earnings`, and `diamonds`,
and two step restarts as late as transition 249. A rescue can make R-hat
blind by moving a chain out of a real second mode. WP35 also had an `sblrc`
child disappear; the merged process diagnostic reproduced a
post-result `STATUS_HEAP_CORRUPTION` during the four-replica teardown span.

WP36 asks whether requiring the same signal twice removes nuisance actions
while preserving rescue efficacy, and whether either mutating rule is safe
enough to remain a default once original mode assignment is made observable.
This is a default decision study, not a claim of universal safety. Its
inference is limited to the fixed models, seeds, starts, and rules below.

## Frozen arms

All arms use the baseline sampler settings and differ only in chain-rescue
handling. Scoring occurs at the end of a completed slow metric window, after
that window's metric update and dual-averaging restart. The current WP33
score is unchanged:

- `step_hit`: the chain's step is strictly below `0.1` times the
  across-chain median step;
- `density_hit`: the across-chain median of window median log densities
  minus this chain's window median log density is strictly greater than
  `3.0` times the across-chain median window log-density IQR;
- a boundary is eligible only under the current rule: at least two chains,
  at least 10 transitions in the completed window, finite required scores,
  and at least one non-outlier source;
- the proposed source is the non-outlier chain with largest step, ties by
  larger median log density and then lower chain index.

If both booleans are true, the canonical criterion is `Step`; otherwise it
is `LogDensity` when only `density_hit` is true, and `null` when neither is
true. This Step priority is used in all three arms.

| arm | frozen behavior |
|---|---|
| `observe` | Compute and record exactly the current scores and proposed source. Never mutate chain state, never draw a source-window index, and never consume rescue RNG. Apart from added telemetry, it must be bit-identical to rescue disabled. |
| `current` | Explicit `restart_from_best`, not an inherited default: act immediately on every eligible hit using the current source-window draw and current state-transfer semantics. |
| `two_hit` | Per chain, act only when the same non-null canonical criterion is observed at two consecutive eligible slow-window boundaries. A first hit sets `(criterion, streak=1)`. The same criterion at the next eligible boundary acts. A clean boundary, skipped/ineligible boundary, criterion change, or restart resets the prior streak; criterion change starts the new criterion at one. |

For `two_hit`, "consecutive" means adjacent slow-window boundaries in that
chain's telemetry; a skipped boundary breaks the sequence. The source is
recomputed at the action boundary. A restart resets the streak to zero, so
the next hit is a new first hit. Neither a first hit nor a clean/skipped
boundary consumes rescue RNG.

No threshold, source rule, transferred state, source-position distribution,
or other sampler setting may be changed after a result is observed.

## Targets, cells, and order

The posteriordb checkout is commit
`28f8d3d6e975315f42aa274a8399f21e07a43b30`, as in WP33 and WP35. The
seven fixed posteriordb targets are:

1. `bball_drive_event_0-hmm_drive_0`
2. `kidiq-kidscore_momhsiq`
3. `earnings-logearn_interaction`
4. `diamonds-diamonds`
5. `arma-arma11`
6. `hudson_lynx_hare-lotka_volterra`
7. `mesquite-logmesquite_logvash`

The eighth target is Neal's 10-dimensional funnel.

Every cell has four chains and runs in a fresh child process. Posteriordb
cells use 1,000 warmup and 1,000 retained transitions, `Init::uniform()`,
adapted diagonal metric, four target replicas/threads, and the complete
baseline defaults except for the explicit arm. Funnel cells use 2,000
warmup and 20,000 retained transitions with fixed starts
`omega={-3,-1,1,3}` and all other coordinates zero.

There are 288 planned cells: 8 targets x 12 seeds x 3 arms. For seed index
`i` in the ordered seed list, arm order rotates:

- `i mod 3 = 0`: `observe`, `current`, `two_hit`;
- `i mod 3 = 1`: `current`, `two_hit`, `observe`;
- `i mod 3 = 2`: `two_hit`, `observe`, `current`.

Targets run in the order listed above, then the funnel. Within a target,
seeds run ascending and arms use the rotation. No cell shares a process
with another cell.

## Fresh paired evidence seeds

The 12 contiguous seeds are **92101, 92102, 92103, 92104, 92105, 92106,
92107, 92108, 92109, 92110, 92111, and 92112**. No numbers are skipped.
Before this scaffold was created, the following tracked-file search was run
from baseline `17f1d97`:

```powershell
git grep -n -P '(?<![0-9.eE])(?:92101|92102|92103|92104|92105|92106|92107|92108|92109|92110|92111|92112)(?![0-9.eE])' -- . ':(exclude)**/artifacts/**'
```

Result: **no matches** (Git exit 1, normalized by the invoking shell to the
printed result `NO_MATCHES`). The lookarounds exclude occurrences embedded
in a longer integer, decimal, or exponent, so this is a standalone
whole-number search rather than a digit-substring search.

The same seed produces the same four initial positions in each arm. The raw
record stores a per-chain `initial_position_sha256`: SHA-256 of the ASCII
domain separator `chain_rescue_v2.initial_position.v1`, followed by the
dimension as little-endian `u64`, followed by each unconstrained position
coordinate's IEEE-754 `f64::to_bits()` as little-endian `u64`, in coordinate
order. A model/seed triplet is invalid if these four hashes differ by arm.

## Required telemetry

Every chain at every slow-window boundary records:

- target, seed, arm, chain, zero-based window index, transition, completed
  window length, eligibility, and exact skip reason;
- current step, across-chain median step, step threshold, and `step_hit`;
- chain window median log density and IQR, across-chain density reference
  and spread, density gap and threshold, and `density_hit`;
- observed canonical criterion, prior criterion/streak, resulting
  criterion/streak, and proposed source chain;
- outcome (`skipped`, `kept`, `observed_hit`, `pending_first_hit`, or
  `restarted`);
- the full unconstrained pre-action position, even when no action occurs,
  and the chain's initial-position hash;
- for a restart, actual source chain, source-window position index,
  installed step, and a hash of the installed position.

`observe` may record the deterministic proposed source chain but must not
select or simulate a source-window position. Cell records also retain the
full unconstrained and constrained retained draws needed for exact identity,
mode-origin, diagnostics, and reference calculations; draw files may remain
ignored, but their hashes and derived metrics are durable.

## Original mode assignment and R-hat credit

Only `observe` retained draws define original mode assignment. For each
posteriordb model/seed/chain `c` and scalar reference parameter `p`, split
the 1,000 retained draws into draws 1–500 and 501–1,000. Let `a1,a2` be
the two means for `c`; let `b1,b2` be the corresponding means over all
1,500 draws from the other three chains; and let `m` and `I` be the type-7
median and IQR over all posteriordb reference draws for `p`.

Chain `c` is a **stable separated origin** when at least one parameter has
finite values, `I > 0`, and all of:

1. `|a1-a2| <= 0.25 I`;
2. `|b1-b2| <= 0.25 I`;
3. `|b1-m| <= 0.50 I` and `|b2-m| <= 0.50 I`;
4. for one common sign `s` in `{-1,+1}`,
   `s(a1-b1) >= 1.50 I` and `s(a2-b2) >= 1.50 I`.

This deliberately conservative rule identifies a chain stable in a
reference-separated region while the other three are stable near the
reference region. It does not label transient split disagreement.

The designation is copied to the same chain in the paired arms by model,
seed, chain index, and initial-position hash. Any restart of such a chain is
`origin_overwritten`, regardless of criterion or apparent posterior
improvement. Raw post-action R-hat is reported, but that model/seed/arm
cannot receive R-hat convergence credit: its credited standard diagnostic
gate is forced to fail and it cannot count as a rescued convergence win.

## Cell diagnostics and reference agreement

Posteriordb keeps the WP35 gates on every scalar reference parameter:
rank-normalized folded split R-hat `<=1.01`, bulk ESS `>=400`, tail ESS
`>=400`, zero retained divergences, finite draws, and no sampler error.
ArviZ 0.23.4 estimators are used. A cleanly returned sampler error is a
valid failing result, not a process exclusion.

For every parameter, report

`z = (mean - reference_mean) / sqrt(mcse^2 + reference_mcse^2)`

and `d = |mean-reference_mean| / reference_sd`. Report every parameter,
the raw maximum `|z|` and its parameter, and the raw maximum `d`. The
existing WP35 reference gate remains: no credited diagnostic-passing cell
may have raw maximum `|z| > 4.0`.

A **decisive reference disagreement** is parameter-specific and requires
both `|z| > 4.0` and `d >= 0.10` for the same parameter. It is a red-line
failure even in a cell that does not pass diagnostics. Thus a very precise
but practically smaller shift remains visible in raw reporting and can fail
the legacy gate when the cell otherwise passes, but it is not called a
decisive disagreement. No global Holm procedure is used: there are two
named paired sign tests below, every fixed gate is conjunctive, and no
claim is made for an unregistered parameter or model family.

Funnel reports the MCSE z of `P(omega < -5)` against exact probability
0.0478, omega bulk ESS and rank R-hat, divergences, final steps, depth caps,
target calls, every action, and the origin analysis applied directly to
`omega` with the analytic `N(0,3)` reference median and IQR.

## Process validity, exclusions, and no reruns

Each child atomically writes and flushes its raw result, then tears down.
The parent records the raw artifact state, stdout/stderr, timeout state, and
raw/signed/hex process exit code. A cell is process-valid only if the child
exits successfully and its durable result is complete and schema-valid.

A crash or nonzero exit after a durable result is still a **process fault**,
not a successful cell. Any timeout, abnormal exit, missing/malformed result,
initial-position hash mismatch, or process-protocol failure invalidates the
entire three-arm model/seed triplet for paired analysis. It is reported and
is never rerun. A sampler-level error returned in a successful, valid child
remains a valid failing observation. Every planned child is launched at
most once; there are no result-driven reruns.

Each target, including the funnel, requires at least 10 valid paired
model/seed triplets. Fewer than 10 makes the study inconclusive and forbids
a default change. All 288 launch records, including exclusions, must be
present for the completeness gate.

## Frozen paired analyses

All ratios compare the same valid model/seed triplet. Exact zero
differences are ties and are omitted only from the named sign test. For
`n` non-tied seed blocks, the one-sided exact sign p-value is
`2^-n * sum(C(n,j), j=w..n)`. A sign gate requires at least 10 non-tied
blocks and `p<=0.05`; equivalently, wins must be at least 9 of 10, 9 of 11,
or 10 of 12. If fewer than 10 complete or non-tied blocks are available,
that gate is inconclusive and cannot pass.

The failure-class set is `hmm_drive_0`, `arma11`, and `lotka_volterra`.
For each complete seed block, its efficacy score is the number (0–3) of
credited standard diagnostic passes.

The nuisance-action set is `kidiq`, `earnings`, and `diamonds`. For each
complete seed block, its action score is the total number of restarted
chains over those three models.

The efficiency statistic per posteriordb cell is
`min over reference parameters of min(bulk ESS, tail ESS) / total target
calls`, with warmup and retained target calls included. Wall time is
reported but not gated on the shared machine. A missing, nonfinite, or
nonpositive efficiency value in a process-valid triplet fails the efficiency
gate; it does not create a process exclusion.

## Decision gates

`two_hit` becomes the default if and only if every gate below is
conclusively satisfied:

1. **Completeness:** all 288 launch records exist; every target has at least
   10 valid triplets; the complete-seed intersections used by each sign
   test have at least 10 valid and at least 10 non-tied blocks.
2. **Safety:** `two_hit` has no `origin_overwritten`; no decisive reference
   disagreement; the WP35 reference gate holds; and on each of `kidiq`,
   `earnings`, `diamonds`, and `mesquite`, its credited pass count is no
   more than one below either paired `observe` or `current`, with no more
   than two such pass losses in total over those four models. For each
   comparator separately, the total is the sum over models of
   `max(0, comparator_passes - two_hit_passes)`.
3. **Efficacy:** against `observe`, `two_hit` wins the one-sided exact sign
   test on the 12 failure-class seed scores. Against `current`, its credited
   pass count is no more than one lower on each failure-class model and no
   more than two lower over the three models combined.
4. **Nuisance-action reduction:** `two_hit` wins the one-sided exact sign
   test for fewer nuisance actions than `current`, and its total nuisance
   actions over the complete seed blocks are at most 60% of `current`.
5. **Funnel:** every valid `two_hit` seed has `|tail-mass z|<=2.0`; at
   least half of the valid seeds pass omega R-hat `<=1.01`, omega bulk ESS
   `>=400`, zero divergences, finite draws, and no sampler error (exactly
   at least 5/10, 6/11, or 6/12); and its full-gate count is no more than
   one below either paired arm.
6. **No-fire:** the pre-evidence observer conformance check is bit-identical;
   at least 10 valid `mesquite` `two_hit` cells have zero restart actions;
   and every valid zero-action `current` or `two_hit` cell on any target is
   bit-identical to `observe` in retained unconstrained and constrained draw
   bytes, total target calls, final step and metric hashes, and retained
   diagnostics (rescue telemetry excepted).
7. **Efficiency:** for every posteriordb model, the median paired
   `two_hit/current` efficiency ratio is at least 0.90, and the geometric
   mean over all valid posteriordb model/seed ratios is at least 0.95.

The implementation must also pass a pre-evidence conformance check showing
`observe` and rescue-disabled execution have identical retained bytes,
work counters, final adaptation hashes, and non-rescue telemetry on fixed
non-evidence fixtures. Failure stops the study before evidence; it may be
fixed before the first evidence cell with the change recorded, but no
evidence may be retained from a failed implementation.

## Red lines and fallback

The candidate-specific red lines are:

- `origin_overwritten`: any restart of an observe-defined stable separated
  origin;
- `reference`: any decisive reference disagreement;
- `funnel`: any valid seed with `|tail-mass z|>3.0`, nonfinite retained
  draws, or a sampler error;
- `no-fire`: any zero-action cell that is not bit-identical to `observe`,
  or any evidence that `observe` consumed rescue RNG or mutated state.

The decision is mechanical:

1. if all seven `two_hit` gates pass, make `two_hit` the default;
2. otherwise, if `current` has any of its four red-line failures, make
   rescue disabled/no rescue the default;
3. otherwise retain explicit immediate `current`;
4. any incomplete or inconclusive analysis counts as `two_hit` failing,
   but does not by itself create a `current` red line.

No other observed result can alter this ordering. Any default change is a
separate labelled implementation commit after the study is complete.

## Predictions

1. `two_hit` cuts nuisance actions by at least 40% and meets the exact sign
   gate, chiefly by removing first-window `kidiq`, `earnings`, and
   `diamonds` actions.
2. `two_hit` preserves immediate rescue efficacy within the fixed count
   margins and improves failure-class seed scores over `observe`.
3. `observe` identifies at least one stable separated `hmm_drive_0` origin.
   `current` overwrites at least one such origin; `two_hit` overwrites fewer
   but is also expected to overwrite at least one persistent mode.
4. Neither mutating arm has a decisive reference disagreement; raw maximum
   `|z|` occasionally exceeds 4 while the corresponding practical shift is
   below 0.10 reference SD.
5. Every valid `two_hit` funnel seed remains within `|z|<=2`, at least half
   pass the full funnel diagnostic gate, and neither paired-arm count is
   exceeded by more than one.
6. At least 10 `mesquite` `two_hit` cells have no action and are
   bit-identical to `observe`.
7. `two_hit` retains at least 0.95 geometric-mean efficiency versus
   `current`.
8. The predicted final decision is **no rescue**: prediction 3 makes
   `two_hit` fail its origin-safety gate and gives `current` an
   `origin_overwritten` red line. This outcome is a prediction, not a
   change to the frozen fallback.

## Execution rules

Report every planned cell, every exclusion, both raw and credited
diagnostics, every registered prediction, and the mechanical decision. Do
not tune, substitute models or seeds, silently drop parameters, pool across
invalid triplets, or rerun a child after observing any output. Implementation
bugs found after the first evidence launch make the study inconclusive; they
do not authorize deleting and restarting the evidence.
