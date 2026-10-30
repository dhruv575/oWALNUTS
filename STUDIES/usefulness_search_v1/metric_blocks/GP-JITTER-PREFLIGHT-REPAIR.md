# Preserve failed dense warmup preflight

Attempt 01 passed omitted/zero-amplitude parity, repeated jitter runs, reported-step bounds and work accounting on both metrics. It failed the final dense warmup-preservation assertion. Dense adaptation invokes one-draw internal runs with discarded=0 and warmup=None, so the initial predicate mistakenly jittered these calls. Diagonal warmup preservation passed.

Attempt 01 sources, ten raw outputs and binaries are preserved. Attempt 02 adds a private explicit exclusion field to the isolated RunConfig and sets it on dense warmup subcalls. Structured-refresh warmup subcalls also receive the exclusion, but that path is outside this experiment and its retained schedule is not qualified. The normal diagonal predicate and dense final retained run remain eligible. No production changes. Repeat the entire frozen preflight, including the failed assertion; do not weaken its requirement. This repair is made before any statistical comparison.
