# H1 mechanism and H4 — build / TLS-symbol audit (static)

Symbol dumps are in `h4-build-symbols.txt` (mingw-w64 `nm`/`objdump`).

## What per-thread native state the FAULTING (non-threads) build actually has

The repo's default, non-`STAN_THREADS` build — the one that reproduces the
fault in the prior studies — does **not** contain Stan Math's
`STAN_THREADS` `thread_local ChainableStack thread_instance` emutls variables
(the `__emutls_v.*thread_instance` symbols appear only in the `STAN_THREADS`
build). It does, however, contain:

- `stan::math::AutodiffStackSingleton<...>::instance_` plus a global
  `std::_Hashtable<std::thread::id, unique_ptr<AutodiffStackSingleton...>>`
  with `_M_insert_unique_node` / `_M_deallocate_node` — i.e. a process-global
  **map from `std::thread::id` to a heap-allocated autodiff stack**, populated
  lazily on first use per OS thread and never erased on thread exit;
- `__cxa_get_globals` / `__cxa_get_globals_fast` and
  `__emutls_v._ZZN12_GLOBAL__N_1L10get_globalEvE6global`, i.e. the C++
  exception-handling per-thread globals reached through mingw emulated TLS;
- `__dyn_tls_init` / `__dyn_tls_dtor` / `__dyn_tls_init_callback` and imports of
  libwinpthread-1.dll `pthread_key_create` / `pthread_setspecific` /
  `pthread_getspecific` — the Windows/mingw TLS-callback machinery that runs
  C++ EH-globals and pthread-key destructors **at every OS thread's exit**.

So the hypothesis-H1 picture — "Stan Math's thread-local autodiff stack has
emutls destructors that run on unmapped memory when the DLL is FreeLibrary'd" —
is wrong in its specifics for this build: there is no `STAN_THREADS`
thread-local autodiff stack here, and the DLLs are not unloaded.

## Why library unload (H1 as stated) is refuted

Two independent facts refute the FreeLibrary mechanism:

1. The reproducing studies already held the model and preload DLLs
   **process-resident** (`bridgestan_lifetime_v1` registry;
   `bridgestan_owned_worker_v1` comparator "resident DLLs"), so `FreeLibrary`
   never ran before the fault — yet the fault still occurred (8/180 and 16/180
   heap-corruption). Never-unload was already in effect and did not prevent it.
2. Those studies also joined their Rayon workers before teardown (scoped,
   joined pools), so "join workers before dropping the library" was already in
   effect and did not prevent it either.

The WP50 `sampler_concurrent` (resident) vs `sampler_concurrent_unload`
(FreeLibrary) arms are the direct discriminator; their counts are in
`summary.json`.

## Narrowed mechanism

The per-thread native state that is actually torn down at worker-thread exit in
the faulting build is the **mingw/libwinpthread TLS-callback path** (C++
EH-globals via emutls `get_global` plus pthread-key destructors), not Stan's
STAN_THREADS autodiff TLS and not a FreeLibrary'd destructor. This matches the
observed fault signatures in `bridgestan_owned_worker_v1`: 14/18 correlated
Application-Error events were `0xC0000374`/`ntdll.dll` (heap) and 3/18 were
`0xC0000005`/`libwinpthread-1.dll`. The owned-worker mitigation removes the
fault precisely because no short-lived OS thread ever enters native code (only
one long-lived owner does, joined exactly once) and because it exposes one
effective replica/module, so the process-global thread-id→autodiff-stack map is
only ever touched by a single thread.

## H4

The `STAN_THREADS` build additionally carries the `thread_local`
`ChainableStack thread_instance` and the per-entry-point `thread_instance`
emutls variables (`h4-build-symbols.txt`), i.e. strictly more per-thread
emutls state with its own destructors. The repo deliberately builds
non-threads (9–16x cheaper per gradient on mingw; see the crate README). The
`sampler_concurrent_threads` vs `sampler_concurrent_nothreads_control` arms
test whether the threads build changes the fault count/signature; counts are in
`summary.json`. The build choice does not create the fault (the faulting build
is the non-threads one); it only changes the amount of per-thread TLS state.
