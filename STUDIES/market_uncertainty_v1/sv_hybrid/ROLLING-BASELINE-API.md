# Pinned NUTS data reuse and initialization

Inspected the installed nutpie 0.16.8 Python source in the pinned AWS runtime.
This is source inspection, not yet a sampling readiness result.

`compile_stan.py`, SHA-256
`144b3582b3dc0a0b4aae39cb2cc2223607bd8bbd6b347f62331e92cd44c0fab9`:
`CompiledStanModel.with_data` copies the data mapping, applies updates, constructs
a new native Stan model and returns a wrapper retaining `self.library`. This
supports compiled-library reuse when the fixed-dimensional rolling data changes.
It does not carry a completed sampler's per-chain state into that new model.

`sample.py`, SHA-256
`b2508b66d63c1ee53db1cea4be4fa0a347dfb55499179ea885e7a82b95ef4164`:
`init_mean` is documented as a transformed-space center for jittered chain
initializations. Each `sample` call creates a new background sampler. The
inspected interface does not establish reuse of previous per-chain positions,
adapted metrics or step sizes. Do not describe a shared initialization center
as exact warm continuation.

The existing E72 WALNUTS resident implementation initializes with 1,000 warmup
and 200 draws, then remaps each stored state, retargets its resident session and
refreshes 400 or 1,600 transitions per rolling update. It also retains the adapted
state. A re-adapting NUTS implementation would differ in both continuation and
adaptation policy. A comparison could measure practical implementations but
would not isolate within-orbit adaptation as the cause of any observed gain.

Before market admission, use a bounded literal readiness case to check data
ownership, compiled-library identity, named parameter ordering, initialization
semantics and complete diagnostics across multiple data updates. Declare all
adaptation costs and keep baseline limitations visible. Do not disable necessary
adaptation merely to make transition counts appear equal, or call an unsupported
zero-refinement configuration ordinary NUTS.

## Literal readiness result

The frozen three-fit readiness case completed with the same library object
reused across all data updates and no mutation of previous model data mappings.
One initial fit used 1,000 warmup / 200 retained draws; two updates each used
1,000 warmup / 400 retained draws, four chains and four cores. All recorded
divergence counts were zero. Compilation took 13.685 seconds; sampling times
were 0.985, 1.096 and 1.019 seconds. These are literal-fixture observations,
not a market benchmark or full diagnostic qualification.

The center for each update was the mean of remapped terminal chain states;
new chains were jittered around it and adaptation restarted. This must not be
reported as exact chain-state or metric reuse. The input center, full draws,
warmup traces and source/seed bindings were preserved remotely. Plan and terminal
receipts are in `evidence/rolling-reuse-readiness-20261028`; full archive
verification remains outstanding. No phone notification is warranted for this
engineering-readiness completion alone.
