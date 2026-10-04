# Additive CFunc continuation: proposed first implementation

The smallest credible implementation is a dedicated Rust worker thread that
owns the target, copied starts, configurations and cancellation state, then
creates borrowed `ChainRun` values inside its own stack frame and services a
command channel. No `ChainRun` crosses the channel. This avoids unsafe
self-referential structs and avoids reconstructing a chain at chunk boundaries.
This document is a design only; no kernel or API changes are implemented.

## Existing support and constraints

`src/walnutpie.rs:7104` already holds complete transition state in
`ChainRun<'a,T>`. `advance(end)` advances the same RNG, position, cached target
evaluation, adapted metric and tuning. The internal rescue driver already
interleaves advances. However, `ChainRun` borrows target, starts, configuration,
fixed mass and `ExecutionControl`; it cannot simply be put in a Python object
alongside the objects it borrows. `PersistentChainContext` contains only RNG and
cached state, so it alone is insufficient for continuation.

`finish(self)` consumes a run and labels output with configured retained count,
even if fewer transitions were requested. It must not be used to manufacture
partial results. A new internal chunk-output accessor must report actual
completed ranges without reseeding, reevaluating the current position, changing
adaptation, or consuming a run. The current start reserves storage for the full
configured budget; first version may keep this bounded reservation and return
copies of new slices. Streaming storage can be a separate improvement.

## Proposed narrow public contract

An additive `start_cfunc_session(target, init, chains, warmup, max_draws, seed,
...)` returns a session with `adapt()`, `draw(n)`, `close()` and cumulative
telemetry. Initially support CFunc targets, diagonal mass, sequential chains,
and existing defaults only. Reject unsupported parallel/rescue/dense options
explicitly. `max_draws` is the lifetime retained budget **per chain**, fixed at
construction; `draw(n)` advances every chain by n additional retained draws.
Reject requests exceeding remaining budget before any chain advances. Target
evaluation limits and cancellation apply to the whole session, never reset per
chunk. Report both per-chunk and cumulative work, warmup and elapsed times.

Warmup runs once. Each later call advances absolute transition indices beyond
the warmup boundary, preserving frozen metric and step size. Chunk results have
`[chains,new_draws,dimension]` shape and explicit retained start/end indices.
Python can concatenate them for existing diagnostics. No chunk independently
claims convergence, and no previous draws are silently discarded.

## Worker lifetime and Python ownership

The Rust bridge transfers owned inputs into a worker closure. Within that
closure construct `RawTarget`, `RunConfig`, starts, `RunControl` and per-chain
execution controls before constructing the vector of borrowed runs. The
receive/advance/reply loop lives in that same scope; runs drop before their
referents. Use each chain's existing `splitmix64(base_seed+chain_index)` seed
derivation. Advancing chains in deterministic sequence at every chunk must
preserve per-chain output identity for deterministic reentrant targets.

The session must retain a strong Python reference to the **whole CFuncTarget**,
including its `keep_alive` tuple, not merely the address. Give the worker an
owned strong `Py<PyAny>` guard as well, so dropping the Python-facing handle can
never free compiled code while a call is in flight. Do not invoke Python on the
sampling worker. Existing raw ABI thread-safety, determinism and buffer rules
still apply. Destruction of Python references must follow PyO3's attachment/drop
rules, after the last raw-target use. Explicit close joins while the caller is
detached from the interpreter; binding implementation must prove this ordering.

Only one mutating call may be active. Use a nonblocking busy guard and reject a
concurrent/reentrant `adapt` or `draw` immediately rather than blocking with the
GIL held. The cancellation flag is independent of that guard, so `close` or a
cancel request can signal an active worker. Wait for replies with the interpreter
detached, checking Python signals through a bounded polling protocol if needed.

## Failure and cancellation semantics

State machine: created -> adapting -> ready -> advancing -> ready/exhausted;
any transition error, panic, deadline or cancellation -> terminal failed.
Never continue after partially advancing some chains. A failed batch returns
structured error plus cumulative work and completed per-chain indices; prior
successful chunks remain valid artifacts. No reseed, rollback or automatic
retry. Invalid caller arguments detected before advancement need not poison a
ready session. Disconnected command/reply channels trigger cancellation and
worker exit. `close()` is idempotent.

Cancellation is cooperative at existing control checks, not preemption of an
arbitrary native callback. A callback that never returns cannot be safely
killed by Rust. Avoid claiming bounded destructor latency: either join after
cooperative cancellation, or detach only while the worker retains all target
ownership and document delayed resource release. Prefer explicit context-manager
close; process-level timeout remains the only hard boundary for a stuck target.

## Minimal implementation footprint

* `src/walnutpie.rs`: internal session driver colocated with private `ChainRun`,
  chunk-output extraction, cumulative control/telemetry, no kernel changes.
* `src/sampler.rs`: a narrow owned command/reply facade or safe session handle
  delegating to that driver; keep `ChainRun` and its lifetimes private.
* `integrations/python/src/lib.rs`: CFunc session pyclass, owned keepalive guard,
  GIL-detached calls, conversion and cancellation/error mapping.
* `integrations/python/python/owalnuts/__init__.py`: public convenience wrapper,
  context manager, validation and unchanged ordinary `sample` behavior.
* Focused Rust state-identity and Python ownership/lifecycle tests plus docs.

An owned-state extraction refactor could ultimately remove the worker thread:
split all borrowed dependencies out of `ChainRun` and pass them into each
advance. That touches most of its execution plumbing and is a larger regression
surface now. It is preferable only if thread/channel overhead or API constraints
prove material; one command per hundreds of draws is unlikely to make the
channel the primary cost, but that is an expectation to test.

## Evidence required before exposing or benchmarking

Compare `[N]`, `[1,N-1]` and uneven multi-chunk partitions against uninterrupted
sampling with the same total budget. Require bitwise equality of draws and
transition diagnostics, exact cumulative target-call counts, seeds, final metric
and step size, including adaptation boundaries and cache enabled/disabled.
Test global draw/target budgets, zero/oversized requests, cancellation in warmup
and retention, target errors, worker panic/disconnection, concurrent calls,
double close, exhausted state, and keepalive survival after deleting the user's
target reference. Check no live worker remains after normal close.

Only then run a frozen paired workflow experiment charging construction,
adaptation, every chunk, diagnostics and serialization. Existing full-restart
results remain historical evidence; continuation changes the execution policy
and needs its own identity and failure denominator.
