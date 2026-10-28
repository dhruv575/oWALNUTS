# Specialist market-window corroboration

Status: frozen campaign launched on AWS after five readiness tests passed.
Root: `/home/ubuntu/lanes/specialist-market-20261028/run01`. All 16 worker
slots were observed live. The first local scheduler-test invocation failed
before execution because its isolated runtime lacked psutil; AWS's pinned
runtime includes it. The source, input and 192-seed bindings are preserved in
`evidence/market-readiness-20261028/`. No market result is claimed at launch.
Follow the completed literal reference check
with the worker in `market_worker.py`. Three local tests cover all 192 index
slots, preservation of partial draws after a failure, and actual literal sweeps
for both methods. The internal sampling clock stops at 295 seconds to leave
serialization room inside the unchanged 300-second external cap. Frozen input
preparation, seed audit and the reviewed campaign supervisor remain required.
Follow the completed literal reference check
with all 24 fixed E70 windows (eight per month, December–February), including
the two flagged references. Use the original E66 sealed data contract and actual
next-return label. Preserve each window's causal indices and data hashes.
No window is chosen because a specialist looks favorable there.

Both original and interwoven methods run on every window: 48 method/window
fits and 192 chain slots. Each chain starts from the declared prior-center state,
with 1,000 warmup sweeps and 2,000 retained sweeps, as in development. No warm
state is transferred between windows. Fresh seed schedules must be audited and
frozen before execution. Existing specialist numerical code and target are
unchanged; bind their source hashes and the pinned AWS runtime.

Each chain gets one core, at most 300 seconds, 1 GiB sampled RSS, 64 MiB output
and two million counted density evaluations. Schedule up to 16 chains on
disjoint cores, with an outer 4,800-second campaign limit, 22 GiB RSS and 8 GiB
output limit. Require 10 GiB free disk at admission; stop new launches below
4 GiB or after a containment failure. No retries, cap extensions or dropped
chain slots. Preserve partial draws and terminal failures. Readiness tests and
reviewed process containment precede sampling.

For every method/window, retain full latent and compact draws, per-chain cost,
evaluation counts and failures. Report the same 254-coordinate diagnostics,
posterior means/quantiles and actual-label predictive density/PIT with MCSE.
Use the unchanged GH64/128 evaluator. Compare to all 24 E70 references and
their passing subset separately; failed reference flags remain visible.
Report both specialist variants, every window and incomplete fit. Don't pool
chains across methods, select a winner after seeing results, or combine shared
reference uncertainty as independent.

This is a cold-window corroboration and cost/precision study. E72 uses warm
streaming paths: its end-to-end timing cannot serve as a matched cold-fit speed
baseline. A later matched algorithm benchmark must equalize initialization,
adaptation, hardware and precision objectives. This study does not establish
whole-path calibration, predictive superiority over forecasting controls,
decision value or profitability. Exposed historical windows are not untouched
confirmation data.
