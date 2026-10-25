# H3 — owned-worker drop-order / double-free / use-after-free audit (static)

Audited the Windows path of `integrations/bridgestan/src/lib.rs`.

## Model teardown happens exactly once, on the owner thread

- `ModelHandle::drop` destructs `ptr` once with `bs_model_destruct` and nulls
  the pointer; a guard `if !self.ptr.is_null()` prevents a second destruct.
- `NativeTarget::drop` takes the per-module `serial` lock and (Windows) the
  process-global native lock, then drops `self.loaded.take()`. The field order
  of `ModelAndLibraries { model, _libraries }` drops `model` (destruct) before
  `_libraries`.
- On Windows the libraries are `Arc<Library>` held in a process-lifetime
  registry (`resident_libraries`), so `FreeLibrary` never runs on drop; the
  model is destructed while its code is still mapped.
- The `NativeTarget` lives on the owner OS thread (it is the `OwnedBackend`).
  `OwnedClient::shutdown` sends `WorkerRequest::Shutdown`, the owner loop
  `break`s, the owner closure returns, and the owner's `NativeTarget` is
  dropped on the owner thread; `OwnedClient::drop` then `join()`s that thread.
  So model destruction and the owner's native TLS teardown both complete before
  `drop` returns, and nothing destructs the model a second time.

## No RNG / second handle aliases the model

- No `bs_rng` object is constructed. `bs_param_constrain` is always called with
  a null `rng` (`include_gq=false`), so there is no RNG whose lifetime could
  outlive the model.
- `ModelHandle` stores only the function pointers it needs plus `ptr`; it is
  owned uniquely by one `NativeTarget`. No clone, `Arc` or raw copy of `ptr`
  exists, so no second owner can destruct or dereference it.
- `ReplicatedStanTarget` holds `replicas: Vec<StanTarget>` and drops it before
  `_copies` (field order). On Windows each `StanTarget` owns its own
  `OwnedClient`/owner thread and its own model; there is no shared model handle
  across replicas, hence no cross-replica double-free. (On Windows the
  effective replica count is 1 regardless of request.)

## Panics do not bypass the join

- `OwnedClient::shutdown` always `join`s the owner (ignoring a worker panic),
  and `start_owned_worker` joins on the load-failure and panic paths. A
  disconnected/panicked worker is surfaced as a fatal `TargetError`, not a
  silent continued use of a freed model.

**Verdict: H3 NOT SUPPORTED.** The drop order is model-before-library, model
destruction is single and owner-thread-confined, the owner is always joined,
and no RNG or aliased handle references the model at teardown. This is
corroborated empirically by `bridgestan_owned_worker_v1` (540/540 owned
children fault-free with exact parity and the fake-backend owner-affinity /
ordering unit tests). The owned-worker drop ordering is not the source of the
corruption.
