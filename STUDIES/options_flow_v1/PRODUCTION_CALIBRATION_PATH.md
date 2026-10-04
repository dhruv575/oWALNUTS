# Production-procedure calibration: shortest next implementation

Static review during the dense flow timing hold. This is a proposed development
path, not a frozen protocol or a new user requirement. No calibration run was
launched. Basis: `wiki/methods.md`, `wiki/findings/kernel-correctness.md`, and the
current options-flow calibration, qualification, simulator and worker code.

## Reuse the current production procedure

Add one new planner/executor and a report-normalization adapter. Generate fresh
prior fixtures, freeze the actual candidate recipe, four starts, one warmup,
retained tiers, endpoint stopping rule, timeout, and all intended cells before
execution. Use the public CFunc continuation workers, not the old native runner
merely because the old SBC aggregator already understands its output. Freeze
one deployed recipe per model after development comparisons; a reference arm
need only cover a small preselected independent agreement subset initially.

Use independent datasets as the replication unit. Flow `model.simulate(prior=True)`
and exogenous-anchor `local_level.simulate(prior=True)` already emit full truth
and future outcomes. Preserve original fixtures and all failures. Do not apply
ordinary prior-generative coverage claims to the application's data-dependent
first-observation prior. No fit may select starts or tuning from generated truth.

## Exact code gaps

1. `calibration.py` assumes flow functionals, `*/{arm}-report.json`, and raw
   `chains[].draws`; current public workers instead write canonical arrays in
   tier directories and distinct report provenance schemas. It cannot ingest
   the current production procedure directly. Its coverage tally is also nested
   under successful ESS-spacing/rank subsampling, making the coverage sample
   depend on an unrelated rank diagnostic. Calculate interval coverage directly
   from reports and fixture truths, independently of optional rank processing.
2. The new adapter must bind immutable original report/fixture/build hashes and
   normalize old `source_sha256` versus continuation absolute-path `bindings`,
   exact settings, selected tier, starts, failure reason and all-attempt cost.
   Current workers label output exploratory; do not silently relabel historical
   output. A new protocol envelope can carry its own prospective protocol hash
   and link the original report bytes. Failed, missing and timed-out expected
   cells must remain explicit rows.
3. `qualification.py` hardcodes six named primaries, +/-5 percentage points,
   `max(1200, requested_n)`, and `healthy == count`. These implement the earlier
   proposal, not a general or user-required decision rule. Separate the actual
   protocol's prespecified margin, family, sample size and failure criterion
   from the statistical calculation. Preserve exact simultaneous intervals and
   a separately stated usable-fit probability bound. Never lower requirements
   after viewing outcomes to manufacture a pass.
4. Check the *production* stopping gate on every tier (all canonical coordinates,
   every physical functional and all declared forecast rows), even if six
   prespecified outputs alone enter the primary coverage family. Current
   qualification cell checks only primary endpoint precision. Store first-pass
   tier and cap failures; do not rerun failed fixtures with changed recipes and
   replace their results.
5. Report conditional-on-usable coverage and unconditional usable-and-covering
   rates as different quantities. Failed fits count as failures in the latter;
   they are not evidence that an uncomputed interval failed mathematical
   posterior coverage. Include both denominators and failure categories.
6. ESS-based spacing in `calibration.py` is not an independence proof for SBC
   ranks. Keep histograms/p-values exploratory unless a separately justified
   autocorrelation-aware rank method is implemented. Coverage equivalence is
   not a full posterior-distribution SBC guarantee. Preserve exact target/gradient
   controls and independent posterior agreement, following the wiki's oracle
   and fingerprint discipline.
7. The earlier prose specifies flow forecast x_next=0, while the simulator
   generates random exogenous x. Either freeze the existing random-x joint
   design explicitly, or implement a generator that uses fixed x to generate
   the corresponding outcome. Never overwrite x alone after generating y.

## Small, bounded staging

First author and test manifest/adapter failure cases without inference. Then
freeze an **exploratory resource pilot of eight fresh fixtures per model**, for
example T=32/G=4 flow and T=32 local level, with one future observation and the
chosen production recipes. Using G4 retains the actual 14-functional flow gate.
Use the same 1k/2k/4k/8k continuation stopping policy; a prospectively chosen
600-second whole-worker cap would bound 16 candidate cells at 2h40m, plus four
preselected reference cells at 40m, excluding controller overhead. These are
upper bounds from a proposed cap, not measured runtime predictions. A different
cap is legitimate if frozen before execution and carried into its claim.

The pilot decides execution feasibility, storage/serialization cost, usable-fit
rate and whether troublesome prior regimes need development work. Eight datasets
per model cannot establish tight calibration or 99% reliability. If the recipe
changes, use new independent datasets for the next confirmatory protocol; keep
pilot failures in its own ledger.

A six-output primary family is reasonable only if its parameter/forecast choices
are defensible and specified before outcomes; other useful evidence should not
be forced into that family.

Only after the recipe and claim are fixed, run `calibration_design` to choose
replication count from the desired margin, familywise alpha and all-primary
power. Its per-functional power alone is insufficient: combine via a conservative
union bound or justified dependence-aware design. The earlier 1200/model is one
possible design for its particular six-functional +/-5-point proposal, not a
mandatory target. Reliability precision can itself require hundreds of trials:
even zero failures needs roughly 300 independent attempts before a one-sided 95%
exact lower bound reaches 99%. A larger permitted failure rate or wider coverage
margin is a different, explicitly narrower claim, not a retrospective shortcut.

Keep demanding T1000 accuracy/performance and chronological market usefulness
as separate remaining components; cheaper short-path calibration cannot replace
either. No positive financial alpha is required for a useful uncertainty workflow.
