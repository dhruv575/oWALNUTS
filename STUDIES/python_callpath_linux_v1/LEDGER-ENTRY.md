### WP78-PYTHON-CALLPATH-LINUX-V1 — on Linux the compiled Python paths cost what a Rust target costs; the nutpie per-gradient gap persists (pooled 1.67x)

- Ordered time: 2026-10-26, `wt/python-linux` (base `55e5a0aa`); prereg `aaaae69a`, A1 `91e68119` (exact float parsing in the Rust harness) before any cell; smoke disclosure `ab82574d`. Lane 4 (cores 12-15) of the shared box, pinned, co-tenanted. Seeds 7878101–7878103, micro 7878501.
- Design: WP47's three models; arms rust, cfunc (numpy error model + guard), njit callable, gil_free, `from_pymc` (thread_safe at t4), `from_jax`, nutpie 0.16.8; threads 1/4; 4 x 1,000/1,000; 126 sampler + 18 micro cells, all ok.
- Outcome: µs/gradient at t1 rust 1.57/0.57/3.84, cfunc 0.98–1.15x rust, gil_free 1.2/2.2/4.0x, njit callable +1.4–1.6 µs, `from_pymc` +5–30 µs, `from_jax` +21–40 µs; callables 0.39–0.82x at t4, compiled 3.2–3.8x. Bit-identical rust ≡ cfunc ≡ njit callable and t1 ≡ t4 (44/44). nutpie gap 1.71/1.44/1.88, pooled 1.67 (WP58 1.70); nutpie fails eight 3/3.
- Predictions: held P3, P4, P5, P6, P8; partial P1 17/18, P2 9/12, P7 18/24.
- Decision (docs only): gil_free + threads=4 first for PyMC; `from_cfunc` for kernels (within 1.5x of Rust); callables threads=1; nutpie faster on gauss100 (1.42x) and hier (1.88x), fails the gates on eight; gap persists on Linux.
