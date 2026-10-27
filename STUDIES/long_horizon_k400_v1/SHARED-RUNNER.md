# Shared linear runner interface (draft, no study execution)

`linear_runner.run_lane(y, *, updates, seeds, score_ticks, retain_ticks, engine_factory, score_hook, output, metadata_hook=None, window=250, k=400)`

- `y`: finite float64 vector, at least250+updates+1 entries. No truth arrays passed to the engine. `seeds` includes `initial` and `warm`.
- `engine_factory(initial_window_copy, seeds_copy)`: returns the unchanged numerical DrawResident wrapper with `.advance(observation,400)`, `.close()`, `.initial`, and optional `.y` window check. Native telemetry must provide `call_index`, `seed`, `work`, `diagnostics`. Exact call/chain base-seed schedule is validated.
- `score_hook(readonly_draw_copy, readonly_current_window_copy, next_label, tick)`: returns a mapping with `status` ok/partial/unavailable (defaultok) plus arbitrary scalar/array evidence. Scored ticks must also be retained ticks. Long study passes11 checkpoints; real study can pass all1488 ticks. Score failure is recorded and does not stop later native updates.
- `metadata_hook(tick,current_index,label_index)`: optional fixed source timestamp/context mapping, independent of the engine. Window bytes/hash and indices are always recorded by the runner.

Files are immutable per tick: compact `.npy` and native `.npz` plus `native/TICK.json` are fsynced BEFORE score_hook, so process exit or scorer mutation cannot erase/change valid native evidence. Final `records/TICK.json` points to native/score arrays and records per-chain scalar health at EVERY update. Every compact receives a value hash, including unretained ticks, for paired prefix identity. `progress.jsonl` is append-only/fsynced, with initial/start/score-start/completion events; only the current event/record is touched. It supports a bounded tail read for monitoring and a single final pass for interruption accounting. Previous rows are never rewritten or rehashed. `INITIAL.json` and `DONE.json` are each written once.

Native failure stops/poisons via engineclose and marks the attempted scored tick unavailable; remaining planned ticks remain unattempted. A separate close_error never overwrites the original failure. Persistence failure is terminal infrastructure failure, with no replay. Numerical failure after advance preserves draws and allows subsequent state evolution.

Time boundaries: native_wall includes the advance call; scoring_seconds covers callback/copy; record I/O includes raw/native/final record writes. Completion journal records total through final record but excludes its own append; whole-lane elapsed includes all progress/record operations. Full process costs additionally include interpreter/import/admission outside this function. Shared-host timing is labeled accordingly.

Eight deterministic/literal fixtures pass, including actual child exit inside scoring, native+close failure, readonly-copy mutation isolation, score-failure continuation, causal indexing and scale-column mapping. No reserved RNG or live data were consumed. Final protocol/source/runtime binding and parent authorization remain required.
