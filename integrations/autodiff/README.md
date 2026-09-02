# owalnuts-autodiff

Write a log density once, generically over a `Scalar` type, and get an
`owalnuts::walnutpie::Target` whose gradient comes from a reverse-mode tape:
no hand-written gradient, and a per-call cost of a few times the hand-written
one rather than the 50-70x of the off-the-shelf tape crates measured in
`../AUTODIFF-RESEARCH.md`.

Route (e) of the research track: a Stan-Math-style expression DSL over a
reusable arena tape with fused primitives (`normal_lpdf` over vectors,
`cumsum`, `dot`, ...) and hand-written adjoints. Pure Rust, stable toolchain,
`#![forbid(unsafe_code)]`.

## Worked example: Eight Schools

```rust
use owalnuts::walnutpie::{DiagonalMass, RunConfig, sample_chains};
use owalnuts_autodiff::{AutodiffTarget, Const, Data, Linear, Model, Scalar, cauchy_lpdf, normal_lpdf, normal_lupdf};
use std::num::NonZeroUsize;

struct EightSchools { y: [f64; 8], se: [f64; 8] }

impl Model for EightSchools {
    fn dimension(&self) -> usize { 10 } // mu, log tau, z[8]
    fn log_density<S: Scalar>(&self, q: &[S]) -> S {
        let (mu, log_tau, z) = (q[0], q[1], &q[2..]);
        let tau = log_tau.exp();
        normal_lpdf(mu, Const(0.0), Const(5.0))                       // mu ~ normal(0, 5)
            + cauchy_lpdf(tau, Const(0.0), Const(5.0)) + log_tau     // tau ~ half-cauchy(0, 5), + log-Jacobian
            + normal_lpdf(z, Const(0.0), Const(1.0))                 // z ~ normal(0, 1)
            + normal_lupdf(Data(&self.y), Linear::new(mu, tau, z), Data(&self.se)) // y ~ normal(mu + tau z, se)
    }
}

let target = AutodiffTarget::new(EightSchools {
    y: [28., 8., -3., 7., -1., 1., 18., 12.],
    se: [15., 10., 16., 11., 9., 11., 10., 18.],
});
let starts = vec![vec![0.0; 10]; 4];
let config = RunConfig::new(1000, NonZeroUsize::new(1000).unwrap(), 42);
let mass = DiagonalMass::identity(NonZeroUsize::new(10).unwrap());
let out = sample_chains(&target, &starts, &mass, &config, NonZeroUsize::new(4).unwrap()).unwrap();
println!("first draw: {:?}", out.chains()[0].sample(0).unwrap());
```

That is the whole model: the same function is evaluated with `S = f64` for
values and with `S = Var` for the gradient, and the two paths are
bit-identical by construction (the fused primitives share one kernel). The
likelihood, the `z` prior and the half-Cauchy are one tape node each; the
call records 9 nodes and 18 partials, and costs about 200 ns on this machine.

## What you can write

* Arithmetic on `S`: `+ - * /`, unary minus, the same with an `f64` on the
  right, the assignment forms, `Sum` over iterators, comparisons (by value),
  and `exp ln sqrt powi powf tanh log1p expm1 abs square recip softplus
  sigmoid`, plus `rdiv(c)` = `c / x` and `rsub(c)` = `c - x`.
* Fused densities with broadcasting: `normal_lpdf`, `normal_lupdf` (drops the
  terms that do not depend on parameters, as Stan's `~` does),
  `student_t_lpdf(x, nu, mu, sigma)` (fixed `nu`), `cauchy_lpdf`,
  `lognormal_lpdf`, `exponential_lpdf`, `gamma_lpdf`, `half_normal_lpdf`,
  `bernoulli_logit_lpmf`, `poisson_log_lpmf`. Every argument is an
  [`Operand`]: a scalar `S`, a slice `&[S]` or `&Vec<S>`, `Const(c)`,
  `Data(&[f64])`, `Shifted(&[S], c)` (elements `x[i] + c`, no node), or
  `Linear::new(a, b, &x)` (elements `a + b * x[i]`, no node). Vectors must
  have equal length; scalars broadcast.
* Reductions: `dot`, `sum`, `log_sum_exp`, `cumsum`, `cumsum_affine(x, scale,
  shift)` (a random walk with drift in one block node).
* Constraining transforms returning `(value, log_jacobian)`: `exp_constrain`,
  `lower_bound_constrain`, `logistic_constrain`, `interval_constrain`,
  `ordered_constrain`.

Return `S::from_f64(f64::NEG_INFINITY)` for a zero-density point. By default
any non-finite value or gradient is reported to the sampler as a recoverable
zero-density evaluation (the kernel refines through it, as with the BridgeStan
and Python facades); `AutodiffTarget::with_nonfinite_policy` makes NaN fatal.

## How the tape works

* `Var { value: f64, index: u32 }` is a 16-byte `Copy` handle into the
  thread's tape. The value travels with the handle, so arithmetic never reads
  the tape: it appends one node. Constants are index 0 (their adjoint lands in
  a dummy slot; no branches), inputs are indices `1..=n` with no stored node.
* Scalar nodes are an enum with inline operands and partials
  (`Unary`/`Binary`/`Ternary`, 40 bytes). `Var + f64` and `Var - f64` reuse the
  operand's index (derivative one) and cost nothing.
* A fused primitive records one `Nary` node made of one *segment* per
  operand. An operand whose elements sit at consecutive tape indices (any
  sub-slice of the inputs, detected in O(1) by address; a `cumsum` output)
  stores partials only and its reverse sweep is a contiguous `axpy`; scattered
  operands store index/partial pairs; broadcast scalars and the parents of a
  `Linear` accumulate into one entry. A T=1000 local-level likelihood is 5
  nodes and 2998 partials with no indices.
* `cumsum` over a contiguous input is a *block* node spanning its outputs
  (filler entries keep node index = tape index); its reverse sweep is one
  reverse scan.
* The tape is a `thread_local!` reused across calls (buffers keep their
  capacity; `reset` is four `clear`s), so every Rayon worker has its own and
  parallel chains need no locking. No allocation per call after warm-up unless
  the model itself allocates (e.g. the `Vec` returned by `cumsum`; use
  `cumsum_into` with your own buffer to avoid it).

`last_tape_stats()` reports the node, partial and index counts of the last
evaluation on the current thread, which is the quickest way to see whether a
model is written in fused form.

## Measured cost (GNU Rust 1.88, Windows 11, single thread, best of 5)

See `../AUTODIFF-RESEARCH.md` (section *Route (e): fused-primitive tape*) for
the full tables, the paired sampling runs and the discussion. Summary:

| model | hand-written | autodiff | ratio |
|---|---:|---:|---:|
| Eight Schools, fused form (9 nodes) | 27 ns (data as compile-time constants) / 51 ns (data in a struct) | ~206 ns | 7.6x / 4.1x |
| Neal's funnel, 10-D | 8 ns | ~108 ns | 14x (fixed per-call cost bound) |
| Local level T=100, `normal_lupdf` | 145 ns | ~440 ns | 3.0x |
| Local level T=1000, `normal_lupdf` | 1.38 us | ~3.9 us | 2.8x |
| Local level T=1000, full `normal_lpdf` | 2.39 us | ~8.9 us | 3.7x |
| Noncentered local level T=100 (`cumsum_affine`) | 256 ns | ~1.2 us | 4.7x |

The fixed cost of a call (two thread-local borrows, tape reset, input setup,
adjoint buffer, gradient copy) is about 25 ns and each scalar node about 5 ns
(the reverse sweep is a store-to-load dependency chain), so tiny models with a
10 ns hand gradient cannot reach 5x with any tape; the state-space target
(<= 3x at T=1000) is met, and end-to-end wall time on Eight Schools is within
1.2-1.5x of the hand-written target because the kernel's own per-call work
dilutes the gradient cost.

## Layout

* `src/tape.rs` - the arena tape and the reverse sweep.
* `src/scalar.rs` - the `Scalar` trait, `f64` and `Var`.
* `src/operand.rs` - broadcasting operands (`Const`, `Data`, `Shifted`, `Linear`).
* `src/dist.rs` - fused kernels and the value/tape drivers.
* `src/transform.rs` - constraining transforms.
* `src/target.rs` - `Model`, `AutodiffTarget`, `gradient_with`.
* `src/models.rs` - Eight Schools, Neal's funnel and the local-level
  state space with their hand-written gradients (test oracles and benchmark
  baselines).
* `tests/gradients.rs` - every primitive against central finite differences;
  the models against their hand gradients (bit-identical values, gradients to
  1e-10); tape reuse; independent per-thread tapes; a sampling smoke test.
* `examples/bench.rs` - per-call cost and paired sampling runs; writes
  `artifacts/bench.json` (`--quick` for a short run).

Build and test with the GNU toolchain used across the repository:

```
RUSTUP_TOOLCHAIN=1.88.0-x86_64-pc-windows-gnu cargo test --release
RUSTUP_TOOLCHAIN=1.88.0-x86_64-pc-windows-gnu cargo run --release --example bench
```
