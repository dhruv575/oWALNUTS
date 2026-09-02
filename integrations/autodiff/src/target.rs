//! [`Model`] and the [`AutodiffTarget`] adapter to `owalnuts::walnutpie::Target`.

use crate::tape::with_tape;
use crate::{Scalar, Var};
use owalnuts::walnutpie::{Target, TargetError};

/// A log density written once, generically over [`Scalar`].
///
/// Data lives in the model as `f64`; the parameters arrive as `&[S]` in
/// unconstrained coordinates, and the returned value must include any
/// log-Jacobian terms. Return `S::from_f64(f64::NEG_INFINITY)` to signal a
/// zero-density point.
pub trait Model: Send + Sync {
    /// Number of unconstrained parameters.
    fn dimension(&self) -> usize;

    /// The log density (up to a constant) at `q`.
    fn log_density<S: Scalar>(&self, q: &[S]) -> S;

    /// Optional parameter names, forwarded to [`Target::parameter_names`].
    fn parameter_names(&self) -> Option<Vec<String>> {
        None
    }
}

/// Evaluate `f` on tape inputs `q`, writing `d f / d q` into `gradient` and
/// returning the value. The thread-local tape is reset first and reused.
pub fn gradient_with<F: FnOnce(&[Var]) -> Var>(q: &[f64], gradient: &mut [f64], f: F) -> f64 {
    assert_eq!(q.len(), gradient.len(), "gradient buffer must match q");
    let mut inputs = with_tape(|t| t.begin(q));
    let out = f(&inputs);
    with_tape(|t| {
        t.gradient(out.index, gradient);
        inputs.clear();
        t.return_inputs(inputs);
    });
    out.value
}

/// Statistics of the last tape recorded on this thread.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct TapeStats {
    /// Operations recorded (inputs and the constant slot excluded).
    pub nodes: usize,
    /// Partials stored by fused nodes.
    pub partials: usize,
    /// Scattered parent indices stored by fused nodes (contiguous operands
    /// store none).
    pub indices: usize,
}

/// Node and side-array counts of the most recent evaluation on this thread.
pub fn last_tape_stats() -> TapeStats {
    with_tape(|t| TapeStats {
        nodes: t.len(),
        partials: t.partials_len(),
        indices: t.indices_len(),
    })
}

/// How non-finite values or gradients are reported to the sampler.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum NonfinitePolicy {
    /// Any non-finite value or gradient is a recoverable zero-density point
    /// (the kernel refines through it). This is the default and matches the
    /// BridgeStan and Python facades' treatment of domain errors.
    Recoverable,
    /// `-inf` values are recoverable; NaN, `+inf` or a non-finite gradient at a
    /// finite value is fatal.
    StrictFatal,
}

/// A [`Target`] backed by a [`Model`] and the thread-local tape.
///
/// Each worker thread owns its own tape (a `thread_local!`), so one
/// `AutodiffTarget` serves any number of parallel chains without locking.
/// After the first call on a thread the tape's buffers are reused and no
/// allocation happens per call (the model itself may still allocate
/// temporaries, e.g. a `Vec<S>` for `cumsum`).
#[derive(Clone, Debug)]
pub struct AutodiffTarget<M> {
    model: M,
    policy: NonfinitePolicy,
}

impl<M: Model> AutodiffTarget<M> {
    /// Wrap a model with the default [`NonfinitePolicy::Recoverable`].
    pub fn new(model: M) -> Self {
        Self {
            model,
            policy: NonfinitePolicy::Recoverable,
        }
    }

    /// Set the non-finite policy.
    pub fn with_nonfinite_policy(mut self, policy: NonfinitePolicy) -> Self {
        self.policy = policy;
        self
    }

    /// The wrapped model.
    pub fn model(&self) -> &M {
        &self.model
    }

    /// Unwrap the model.
    pub fn into_model(self) -> M {
        self.model
    }

    /// Value-only evaluation (plain `f64`, no tape).
    pub fn value(&self, q: &[f64]) -> f64 {
        self.model.log_density(q)
    }

    /// Value and gradient with no error mapping (non-finite results are
    /// returned as they are).
    pub fn value_and_gradient(&self, q: &[f64], gradient: &mut [f64]) -> f64 {
        gradient_with(q, gradient, |vars| self.model.log_density(vars))
    }
}

impl<M: Model> Target for AutodiffTarget<M> {
    fn dimension(&self) -> usize {
        self.model.dimension()
    }

    fn log_density_gradient(&self, q: &[f64], gradient: &mut [f64]) -> Result<f64, TargetError> {
        if q.len() != self.model.dimension() || gradient.len() != q.len() {
            return Err(TargetError::new("autodiff target: dimension mismatch"));
        }
        let value = self.value_and_gradient(q, gradient);
        if value.is_finite() && gradient.iter().all(|g| g.is_finite()) {
            return Ok(value);
        }
        match self.policy {
            NonfinitePolicy::Recoverable => Err(TargetError::recoverable(
                "autodiff target: non-finite log density or gradient",
            )),
            NonfinitePolicy::StrictFatal => {
                if value == f64::NEG_INFINITY {
                    Err(TargetError::recoverable(
                        "autodiff target: log density is -inf",
                    ))
                } else {
                    Err(TargetError::new(
                        "autodiff target: NaN or non-finite gradient at a finite value",
                    ))
                }
            }
        }
    }

    fn parameter_names(&self) -> Option<Vec<String>> {
        self.model.parameter_names()
    }
}
