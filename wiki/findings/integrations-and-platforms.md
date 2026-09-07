# Integrations: BridgeStan, autodiff, Python transport, and the Windows native fault

## State of knowledge

oWALNUTS samples any Stan model through BridgeStan at Stan's gradient cost, and from Python at native speed once the gradient is compiled outside the interpreter. The gradient dominates: a 6.7 µs Stan gradient against a 40 ns hand-written one means the Eight Schools throughput claim only holds for hand-written targets. Off-the-shelf Rust autodiff (Enzyme, the `reverse` tape) was not competitive; the project's own arena tape is within 3–14x of hand gradients. The one hard platform problem is a Windows GNU native fault at BridgeStan target teardown that reproduced in three diagnostic studies; the owned-one-worker backend passed 720/720 children at 3–5x the sampling cost and is shipped as a narrow mitigation without an established root cause. Version 0.2.0 is published on crates.io and PyPI with a green cross-platform CI matrix.

## Timeline of evidence

- **WP15a-AUTODIFF-BRIDGESTAN-ENZYME-V1** (`integrations/bridgestan`, `integrations/enzyme`, `integrations/AUTODIFF-RESEARCH.md`): BridgeStan `Target` agrees with hand gradients to 1e-13 or better. Per-call gradient 6.7 µs vs 40 ns hand on Eight Schools (167x), 8.4 µs vs 201 ns at T=100, 38 µs vs 2.9 µs at T=1000. Paired sampling with identical seeds is bit-identical in trajectory; Eight Schools ESS/s falls 12.5k to 1.2k. Enzyme: nightly accepts `-Zautodiff` but no `libEnzyme` ships on Windows. `reverse` 0.2.2 tape: gradients agree but 58–68x hand per call.
- **Autodiff arena tape** (`integrations/autodiff`): fused-primitive tape with `Var` handles, enum nodes, segmented n-ary nodes and `cumsum` blocks, at 2.8x a hand gradient on the T=1000 state-space path, 4.1x on Eight Schools, 13.7x on the 10-D funnel where the hand gradient is a 7.6 ns loop.
- **WP15B-PYTHON-TARGETS-V1** (`integrations/python`, `BENCH.md`): overhead per fused call native 0.6–0.8 µs, PyMC 6 µs, numpy 10–13 µs, JAX 26–84 µs, torch 170–290 µs. Eight Schools owalnuts+pymc 1,439 ESS/s vs NumPyro warm 897; loses on pure-JAX targets (414 vs 897) and to nutpie on PyMC models (1,298–2,120 vs 17,844–25,043). The GIL serialises Python targets: threads=4 is slower than threads=1 for numpy. The nutpie gap was identified as callback transport, not sampler efficiency.
- **WP18-GIL-FREE-TRANSPORT-V1** (`integrations/python`, `RawTarget` in the facade): `from_cfunc` / `from_pymc(gil_free=True)`. Eight Schools cfunc at 4 threads 30,982 ESS/s vs nutpie cores=4 27,754; per-call 5.69 µs (GIL) to 1.25 µs (cfunc); ESS per exact fused call unchanged across transports (0.0336/0.0338). Thread scaling 3.1x.
- **WP19-FLAGSHIP-CRYPTO-SV-V1** and **WP21-CRYPTO-SV-V2** (`STUDIES/flagship_crypto_sv_v1`, `_v2`): five-asset stochastic volatility with T up to 3,153. Zero divergences in all cells, cross-backend agreement, fastest wall on 5/5 assets, but BTC/ETH global ESS below 400 at 4 x 3,000 where NumPyro passes; nutpie and NumPyro windowed adaptation extract 1.5–2x more global ESS on the (a, s) ridge. v2 selected the paper-mode arm E and met the gates only in a labelled 2x-compute pooled tier; the pymc callable transport was found thread-unsafe (shared PyTensor storage) and `from_pymc(thread_safe=True)` was added; a quiet-machine re-measurement showed arm E's 1.7x call count, not contention, explained the higher walls.
- **Mingw TLS finding** (posteriordb v1 to v2, `research-program-2026-09-04.md`): the ten-times wall gap in WP22 was not the sampler. Mingw-w64 GCC emulates thread-local storage and Stan Math touches its thread-local autodiff stack on every node, so a `STAN_THREADS=true` build cost 10x per call. A non-threaded build plus `ReplicatedStanTarget` (one loaded module per thread) took `arK` from 10.54 s to 1.53 s at identical trajectories; WP23 measured 7–22x ESS/s on arK, hmm_example and eight schools at identical gradient counts and wall per gradient 0.771x CmdStan.
- **WP22 to WP23** (`STUDIES/posteriordb_bench_v1`, `_v2`): in v1 six `arma11` cells and four others died because `StanTarget` treated NaN log density or gradient as fatal where CmdStan and nutpie reject the proposal, and two `lotka_volterra` starts were not evaluable. v2 mapped these to recoverable rejections and added `Init::uniform()` start retries: zero cells lost to fatal NaN or start failure (v1 lost 12).
- **WP35** and **WP35A-SBLRC-PROCESS-STABILITY-V1** (`STUDIES/sblrc_process_stability_v1`): one oWALNUTS `sblrc` subprocess in posteriordb v6 exited with no stderr and no result. The 46-child diagnostic reproduced it once: a four-replica, four-thread sampling child completed and durably published its result, then exited `0xC0000374` (`STATUS_HEAP_CORRUPTION`) with its last heartbeat at `drop/before`. Root cause not established.
- **WP36-CHAIN-RESCUE-V2**: seven of 288 children were process faults (six heap-corruption exits, one post-result timeout at `drop/before`).
- **BRIDGESTAN-LIFETIME-V1** (`STUDIES/bridgestan_lifetime_v1`): resident DLLs plus joined Rayon workers, 180 children per arm. Baseline 15/180 faults; fixed arm still 8/180, all `0xC0000374`. Rejected under the zero-fault gate.
- **BRIDGESTAN-OWNED-WORKER-V1** (`STUDIES/bridgestan_owned_worker_v1`): every native call on one owned OS thread per target with one effective replica and a process-global native-call mutex. Initial 540 children zero faults; final frozen run 720/720 (540 ordinary, 180 concurrent four-target) with zero nonzero exits, timeouts, missing outputs or correlated Event 1000 records; one-sided 95 % zero-failure upper bound 0.415 %. Sampling medians 3.1x (diamonds), 3.7x (sblrc), 5.1x (mesquite) the four-replica comparator. Accepted as a narrow Windows GNU mitigation.
- **Release** (`wiki/release-0.2.0.md`, `research-program-2026-09-04.md`): main pushed to GitHub on 2026-09-04; core matrix (Linux GNU 1.88, Linux stable, Windows GNU 1.88, Windows MSVC 1.88, three integration jobs, both BridgeStan real-model gates) green after pinning Linux-specific kernel fingerprints; wheels for Windows, manylinux x86_64/aarch64, macOS x86_64/arm64 plus the sdist built and tested. On 2026-09-05 `v0.2.0` was tagged and 0.2.0 published to crates.io and to PyPI through the trusted publisher; `pip install owalnuts` verified in a clean venv.

## What worked

| change | study | result | why |
|---|---|---|---|
| BridgeStan `Target` integration | WP15a | any Stan model samples at Stan gradient cost; agreement to 1e-13 | Stan's C-ABI exposes log density and gradient directly |
| Non-`STAN_THREADS` build plus `ReplicatedStanTarget` | v2 rebuild | `arK` 10.54 s to 1.53 s; 7–22x ESS/s at identical gradients | mingw emulated TLS made every autodiff node a TLS lookup |
| Recoverable mapping of NaN density/gradient and start retries | WP23 | 12 lost cells in v1 to 0 in v2 | matches CmdStan and nutpie reject-the-proposal behaviour |
| GIL-free `cfunc` transport | WP18 | 30,982 vs nutpie 27,754 ESS/s at 4 cores; per-gradient unchanged | the nutpie gap was callback transport, not the kernel |
| Own fused-primitive arena tape | `integrations/autodiff` | 2.8x / 4.1x / 13.7x hand gradients | segmented n-ary nodes and `cumsum` blocks avoid per-scalar nodes |
| Owned-one-worker native backend with process-global mutex | BRIDGESTAN-OWNED-WORKER-V1 | 0/720 faults, upper bound 0.415 % | every native call on one owned thread; teardown serialised |
| Python package constructing `owalnuts::sampler` types | 0.2 programme | draws bit-identical to a Rust `Sampler` run, defaults cannot drift | one configuration path |
| `from_pymc(thread_safe=True)` | WP21 | per-thread compiled functions | shared PyTensor storage was thread-unsafe |

## What did not work

| change | study | result | why |
|---|---|---|---|
| Enzyme `-Zautodiff` on Windows | WP15a | unusable | no `libEnzyme` in the nightly sysroot |
| `reverse` 0.2.2 tape | WP15a | 58–68x hand per call; 4–11x worse ESS/s | per-scalar tape nodes |
| Pure-JAX Python targets | WP15B | 414 vs NumPyro 897 ESS/s | 26–84 µs per-call overhead through the callback |
| Threads > 1 on GIL-bound Python targets | WP15B | threads=4 slower than threads=1 | the GIL serialises every callback |
| `STAN_THREADS=true` BridgeStan build on mingw | WP22 | 10x wall per call | emulated thread-local storage |
| Resident DLLs plus joined Rayon workers | BRIDGESTAN-LIFETIME-V1 | 8/180 faults remain | teardown serialisation was incomplete |
| One-shot frozen path metric on T of about 3,000 SV | WP19, WP21 | BTC/ETH global ESS below 400; start-trapped pymc cells | windowed adaptation extracts 1.5–2x more global ESS on the ridge |
| Eight Schools ESS/s claim with autodiff gradients | WP15a | 12.5k to 1.2k | the 6.7 µs gradient dominates a 40 ns hand gradient |

## Current state

BridgeStan is the supported route for Stan models on Linux and macOS through `from_stan` and the Rust `StanTarget`. On Windows GNU the owned-one-worker backend is qualified with one effective replica and a 3–5x sampling cost; expert Rust `StanTarget` use on Windows MSVC, and multi-worker Windows execution, are unqualified. Windows Python `from_stan` and direct Python BridgeStan operations are disabled for 0.2. The Python package inherits the sampler defaults, exposes `from_cfunc`, `from_pymc` (GIL-free and thread-safe variants), `init="uniform"`, `summary()` and the numba path. Wheels build for five platforms; 0.2.0 is on crates.io and PyPI.

## Open questions

- The Windows heap-corruption root cause. Three studies bound it to target teardown after result publication but none identifies the destroying call; the mitigation is behavioural.
- Windows MSVC qualification of the owned-worker backend, and whether the historical multi-replica path is safe on Linux and macOS.
- A same-`.stan`-file exact-work three-way (oWALNUTS-BridgeStan vs CmdStan vs nutpie) was proposed by WP15a and WP18 and is what the posteriordb line later became; a strict nutpie comparison on PyMC models with exact work counters is still unrun.
- Re-probing Enzyme when a rustup component ships.
- The pymc thread-safe re-measurement phase of WP21 was stopped externally and remains a one-command follow-up.

Source: [ledger](../research-ledger-2026-08-31.md).
