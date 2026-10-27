//! Resident warm-continuation session (WP91): one worker thread that owns
//! the target, keeps a pool of `threads` Rayon workers and every per-chain
//! configuration, mass and position alive across calls, and runs `draws`
//! warm transitions per chain on request. Each call is bit-identical to
//! `sampler::Sampler::run_warm` under the seed rule documented on
//! [`WarmSession`]. Like [`super::session`], no borrowed state leaves the
//! worker stack and the target drops on the worker thread after its last
//! callback has returned.
//!
//! Streaming functionals (WP95): [`WarmSession::refresh_functionals`] and
//! `Sampler::run_warm_functionals` evaluate caller-supplied
//! [`Functional`]s on every retained draw inside the chain loop and keep
//! the functional values (and their running moments) instead of the
//! draws, so the memory a quote needs is `draws * outputs` per chain
//! rather than `draws * dimension`. The kernel never sees the functionals:
//! the chain is advanced one transition at a time through the same
//! `ChainRun::advance` the plain call uses, so draws and diagnostics are
//! bit-identical with and without them (`tests/warm_functionals.rs`).
use super::*;
use std::cell::Cell;
use std::ops::Range;
use std::sync::atomic::AtomicBool;
use std::sync::{Arc, Mutex, mpsc};
use std::thread::JoinHandle;

use crate::sampler::{WarmChain, WarmRecipe, WarmState};

thread_local! { static WARM_WORKER: Cell<usize> = const { Cell::new(0) }; }

/// One chain's draws and diagnostics from one [`WarmSession::refresh`].
///
/// `samples` and `diagnostics` are the kernel's own per-chain buffers for
/// the call (`draws * dimension` values, draw-major `[draw][parameter]`, and
/// one record per transition), handed over without copying.
#[derive(Clone, Debug, PartialEq)]
pub struct WarmChainChunk {
    /// Retained draws of this call, draw-major `[draw][parameter]`.
    pub samples: Vec<f64>,
    /// One record per transition of this call.
    pub diagnostics: Vec<TransitionDiagnostics>,
    /// Telemetry of this call only (not cumulative).
    pub telemetry: RunTelemetry,
    /// The chain's step size; carried unchanged (nothing adapts).
    pub step_size: f64,
    /// The chain's diagonal mass `M`; carried unchanged (a copy).
    pub mass_diagonal: Vec<f64>,
    /// `splitmix64(seed + chain)` for the call's `seed`.
    pub effective_seed: u64,
}

/// The draws of one [`WarmSession::refresh`] call, every chain in
/// chain-index order.
#[derive(Clone, Debug, PartialEq)]
pub struct WarmChunk {
    pub chains: Vec<WarmChainChunk>,
    pub dimension: usize,
    /// Transitions per chain in this call.
    pub draws: usize,
    /// The call's base seed (`WarmSession::seed_for_call(call_index)`).
    pub seed: u64,
    /// Zero-based index of the call in the session.
    pub call_index: usize,
    /// Target calls of this call, summed over chains (the kernel's own
    /// count, `RunTelemetry::total().target_calls_total()`).
    pub target_calls: usize,
}

impl WarmChunk {
    /// Draws of `chain`, draw-major `[draw][parameter]`.
    pub fn chain_draws(&self, chain: usize) -> Option<&[f64]> {
        self.chains.get(chain).map(|c| c.samples.as_slice())
    }

    /// One draw of one chain.
    pub fn draw(&self, chain: usize, draw: usize) -> Option<&[f64]> {
        let start = draw.checked_mul(self.dimension)?;
        let end = start.checked_add(self.dimension)?;
        self.chains.get(chain)?.samples.get(start..end)
    }

    /// The warm state at the end of this call: per chain, its last draw,
    /// its step size and its diagonal mass (what [`WarmSession::state`]
    /// holds after the call).
    pub fn warm_state(&self) -> Result<WarmState, Error> {
        let chains = self
            .chains
            .iter()
            .enumerate()
            .map(|(index, chain)| {
                let draws = chain.samples.len() / self.dimension.max(1);
                if draws == 0 || self.dimension == 0 {
                    return Err(Error::configuration(format!(
                        "warm chunk chain {index} has no draw"
                    )));
                }
                Ok(WarmChain {
                    position: chain.samples[(draws - 1) * self.dimension..].to_vec(),
                    step_size: chain.step_size,
                    mass_diagonal: chain.mass_diagonal.clone(),
                })
            })
            .collect::<Result<Vec<_>, Error>>()?;
        WarmState::new(chains)
    }
}

/// A function of the position, evaluated on every retained draw of a warm
/// refresh inside the chain loop ([`WarmSession::refresh_functionals`],
/// [`crate::sampler::Sampler::run_warm_functionals`]) so that the draws
/// themselves need not be retained. [`FunctionalFn`] adapts a closure and
/// [`RawFunctional`] a C-ABI callback.
///
/// `evaluate` runs on the chain's worker thread, once per retained draw,
/// concurrently for different chains, and must be deterministic in the
/// position (the values are reported as the functional of the draws). It
/// must not call back into the session. An error (or a panic) ends the call
/// as an execution error: the session becomes terminal, like a fatal
/// target error.
pub trait Functional: Send + Sync {
    /// The number of outputs: the length of `out` in [`Functional::evaluate`].
    fn dimension(&self) -> usize;

    /// Write the outputs for `position` (one retained draw, the target's
    /// dimension) into `out` (`self.dimension()` values, write-only; stale
    /// values from earlier draws may be present).
    fn evaluate(&self, position: &[f64], out: &mut [f64]) -> Result<(), FunctionalError>;
}

/// A [`Functional::evaluate`] failure; ends the call that evaluated it.
#[derive(Clone, Debug, Eq, PartialEq)]
pub struct FunctionalError {
    message: Box<str>,
}

impl FunctionalError {
    pub fn new(message: impl Into<Box<str>>) -> Self {
        Self {
            message: message.into(),
        }
    }

    pub fn message(&self) -> &str {
        &self.message
    }
}

impl fmt::Display for FunctionalError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        f.write_str(&self.message)
    }
}

impl std::error::Error for FunctionalError {}

/// A [`Functional`] over a closure `f(position, out)` with a fixed number
/// of outputs.
pub struct FunctionalFn<F> {
    outputs: usize,
    function: F,
}

impl<F: Fn(&[f64], &mut [f64]) + Send + Sync> FunctionalFn<F> {
    /// `function` writes `outputs` values into its second argument.
    pub fn new(outputs: usize, function: F) -> Self {
        Self { outputs, function }
    }
}

impl<F: Fn(&[f64], &mut [f64]) + Send + Sync> Functional for FunctionalFn<F> {
    fn dimension(&self) -> usize {
        self.outputs
    }

    fn evaluate(&self, position: &[f64], out: &mut [f64]) -> Result<(), FunctionalError> {
        (self.function)(position, out);
        Ok(())
    }
}

impl<F> fmt::Debug for FunctionalFn<F> {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        f.debug_struct("FunctionalFn")
            .field("outputs", &self.outputs)
            .finish_non_exhaustive()
    }
}

/// The C ABI of a [`RawFunctional`] callback: `dimension` is the length of
/// `position`, `outputs` the length of `out` (the functional's
/// [`Functional::dimension`]); the callback writes every element of
/// `out[..outputs]` and reads `position[..dimension]` only. numba
/// signature: `void(intp, double*, double*, intp, void*)`.
pub type RawFunctionalFn = unsafe extern "C" fn(
    dimension: usize,
    position: *const f64,
    out: *mut f64,
    outputs: usize,
    user_data: *mut core::ffi::c_void,
);

/// A [`Functional`] over a raw C-ABI callback (a numba or Cython `cfunc`,
/// a C function), the functional counterpart of [`RawTarget`]: GIL-free, so
/// chains evaluate it in parallel.
pub struct RawFunctional {
    outputs: usize,
    function: RawFunctionalFn,
    user_data: *mut core::ffi::c_void,
}

// SAFETY: asserted by the `RawFunctional::new` caller: the callback and its
// `user_data` are thread-safe and reentrant for the life of the value.
unsafe impl Send for RawFunctional {}
// SAFETY: as above; shared `&RawFunctional` calls are concurrent callback
// calls, which the constructor contract requires to be safe.
unsafe impl Sync for RawFunctional {}

impl RawFunctional {
    /// Wrap a raw callback as a functional with `outputs` outputs.
    ///
    /// # Safety
    ///
    /// The caller asserts, for the entire lifetime of the returned value:
    /// `function` is safe to call concurrently from multiple threads with
    /// this `user_data`; it only reads `position[..dimension]` and only
    /// writes `out[..outputs]`; it neither unwinds across the FFI boundary
    /// nor stores the passed pointers beyond the call; and `user_data`
    /// remains valid.
    pub unsafe fn new(
        outputs: usize,
        function: RawFunctionalFn,
        user_data: *mut core::ffi::c_void,
    ) -> Self {
        Self {
            outputs,
            function,
            user_data,
        }
    }
}

impl Functional for RawFunctional {
    fn dimension(&self) -> usize {
        self.outputs
    }

    fn evaluate(&self, position: &[f64], out: &mut [f64]) -> Result<(), FunctionalError> {
        // SAFETY: the `RawFunctional::new` contract; `position` and `out`
        // are live slices of the stated lengths for the duration of the
        // call.
        unsafe {
            (self.function)(
                position.len(),
                position.as_ptr(),
                out.as_mut_ptr(),
                out.len(),
                self.user_data,
            );
        }
        Ok(())
    }
}

impl fmt::Debug for RawFunctional {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        f.debug_struct("RawFunctional")
            .field("outputs", &self.outputs)
            .finish_non_exhaustive()
    }
}

/// The functionals of one call, in order, with their output layout: output
/// `j` of functional `k` is output `offset_k + j` of the call, where
/// `offset_k` is the sum of the earlier functionals' dimensions
/// ([`Functionals::output_range`]). `retain_draws` also keeps the position
/// draws in the chunk (off by default: not keeping them is the point).
#[derive(Clone)]
pub struct Functionals {
    items: Vec<Arc<dyn Functional>>,
    offsets: Vec<usize>,
    retain_draws: bool,
}

impl Default for Functionals {
    fn default() -> Self {
        Self::new()
    }
}

impl Functionals {
    pub fn new() -> Self {
        Self {
            items: Vec::new(),
            offsets: vec![0],
            retain_draws: false,
        }
    }

    /// Append a functional.
    pub fn with(self, functional: impl Functional + 'static) -> Self {
        self.with_arc(Arc::new(functional))
    }

    /// Append a shared functional.
    pub fn with_arc(mut self, functional: Arc<dyn Functional>) -> Self {
        let end = self.outputs().saturating_add(functional.dimension());
        self.items.push(functional);
        self.offsets.push(end);
        self
    }

    /// Also keep the position draws in the chunk.
    pub fn retain_draws(mut self, retain: bool) -> Self {
        self.retain_draws = retain;
        self
    }

    pub fn retains_draws(&self) -> bool {
        self.retain_draws
    }

    pub fn functionals(&self) -> &[Arc<dyn Functional>] {
        &self.items
    }

    pub fn len(&self) -> usize {
        self.items.len()
    }

    pub fn is_empty(&self) -> bool {
        self.items.is_empty()
    }

    /// Outputs of the call: the sum of the functionals' dimensions.
    pub fn outputs(&self) -> usize {
        self.offsets.last().copied().unwrap_or(0)
    }

    /// The call outputs written by functional `functional`.
    pub fn output_range(&self, functional: usize) -> Option<Range<usize>> {
        Some(*self.offsets.get(functional)?..*self.offsets.get(functional + 1)?)
    }

    fn ranges(&self) -> impl Iterator<Item = Range<usize>> + '_ {
        self.offsets.windows(2).map(|w| w[0]..w[1])
    }
}

impl fmt::Debug for Functionals {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        f.debug_struct("Functionals")
            .field("functionals", &self.items.len())
            .field("outputs", &self.outputs())
            .field("retain_draws", &self.retain_draws)
            .finish()
    }
}

/// Running moments of one functional output over one chain's draws
/// (Welford's update, so `mean` and `m2 = sum (x - mean)^2` are accumulated
/// in one pass): `count` draws, their `mean`, `m2`, `min` and `max`.
#[derive(Clone, Copy, Debug, PartialEq)]
pub struct OutputMoments {
    pub count: usize,
    pub mean: f64,
    pub m2: f64,
    pub min: f64,
    pub max: f64,
}

impl Default for OutputMoments {
    fn default() -> Self {
        Self {
            count: 0,
            mean: 0.0,
            m2: 0.0,
            min: f64::INFINITY,
            max: f64::NEG_INFINITY,
        }
    }
}

impl OutputMoments {
    /// Add one value.
    pub fn push(&mut self, value: f64) {
        self.count += 1;
        let delta = value - self.mean;
        self.mean += delta / self.count as f64;
        self.m2 += delta * (value - self.mean);
        self.min = self.min.min(value);
        self.max = self.max.max(value);
    }

    /// The moments of the union of two samples (Chan, Golub and LeVeque).
    pub fn merge(&self, other: &Self) -> Self {
        if self.count == 0 {
            return *other;
        }
        if other.count == 0 {
            return *self;
        }
        let (a, b) = (self.count as f64, other.count as f64);
        let count = a + b;
        let delta = other.mean - self.mean;
        Self {
            count: self.count + other.count,
            mean: self.mean + delta * b / count,
            m2: self.m2 + other.m2 + delta * delta * a * b / count,
            min: self.min.min(other.min),
            max: self.max.max(other.max),
        }
    }

    /// The sample variance (`m2 / (count - 1)`); `None` below two values.
    pub fn variance(&self) -> Option<f64> {
        (self.count >= 2).then(|| self.m2 / (self.count - 1) as f64)
    }
}

/// One chain's functional values and diagnostics from one
/// [`WarmSession::refresh_functionals`] (or
/// [`crate::sampler::Sampler::run_warm_functionals`]).
#[derive(Clone, Debug, PartialEq)]
pub struct FunctionalChainChunk {
    /// The functional values of every retained draw, draw-major
    /// `[draw][output]` (`draws * outputs` values).
    pub values: Vec<f64>,
    /// Running moments per output over this chain's draws.
    pub moments: Vec<OutputMoments>,
    /// The chain's last draw (its position after the call).
    pub position: Vec<f64>,
    /// The retained draws, draw-major `[draw][parameter]`, when
    /// [`Functionals::retain_draws`] was set; `None` otherwise.
    pub samples: Option<Vec<f64>>,
    /// One record per transition of this call.
    pub diagnostics: Vec<TransitionDiagnostics>,
    /// Telemetry of this call only (not cumulative).
    pub telemetry: RunTelemetry,
    /// The chain's step size; carried unchanged (nothing adapts).
    pub step_size: f64,
    /// The chain's diagonal mass `M`; carried unchanged (a copy).
    pub mass_diagonal: Vec<f64>,
    /// `splitmix64(seed + chain)` for the call's `seed`.
    pub effective_seed: u64,
}

/// The functional values of one warm call, every chain in chain-index
/// order: what [`WarmChunk`] is for the draws. The pooled statistics
/// ([`FunctionalChunk::mean`], [`FunctionalChunk::variance`],
/// [`FunctionalChunk::quantile`]) treat every chain's draws as one sample;
/// the per-chain ones take a chain index.
#[derive(Clone, Debug, PartialEq)]
pub struct FunctionalChunk {
    pub chains: Vec<FunctionalChainChunk>,
    /// The target's dimension.
    pub dimension: usize,
    /// Outputs per draw (the sum of the functionals' dimensions).
    pub outputs: usize,
    /// `offsets[k]..offsets[k + 1]` are the outputs of functional `k`.
    pub offsets: Vec<usize>,
    /// Transitions per chain in this call.
    pub draws: usize,
    /// The call's base seed.
    pub seed: u64,
    /// Zero-based index of the call in the session (0 for a one-shot run).
    pub call_index: usize,
    /// Target calls of this call, summed over chains.
    pub target_calls: usize,
}

impl FunctionalChunk {
    /// The call outputs written by functional `functional`.
    pub fn output_range(&self, functional: usize) -> Option<Range<usize>> {
        Some(*self.offsets.get(functional)?..*self.offsets.get(functional + 1)?)
    }

    /// Functional values of `chain`, draw-major `[draw][output]`.
    pub fn chain_values(&self, chain: usize) -> Option<&[f64]> {
        self.chains.get(chain).map(|c| c.values.as_slice())
    }

    /// One output of one draw of one chain.
    pub fn value(&self, chain: usize, draw: usize, output: usize) -> Option<f64> {
        if output >= self.outputs {
            return None;
        }
        let index = draw.checked_mul(self.outputs)?.checked_add(output)?;
        self.chains.get(chain)?.values.get(index).copied()
    }

    /// Output `output` over the draws of `chain`, in draw order.
    pub fn chain_output(&self, chain: usize, output: usize) -> impl Iterator<Item = f64> + '_ {
        let step = self.outputs.max(1);
        let valid = output < self.outputs;
        self.chains
            .get(chain)
            .into_iter()
            .filter(move |_| valid)
            .flat_map(move |c| c.values.iter().skip(output).step_by(step).copied())
    }

    /// Output `output` over every chain's draws, chain by chain.
    pub fn output(&self, output: usize) -> impl Iterator<Item = f64> + '_ {
        (0..self.chains.len()).flat_map(move |chain| self.chain_output(chain, output))
    }

    /// The running moments of `output` over the draws of `chain`.
    pub fn chain_moments(&self, chain: usize, output: usize) -> Option<&OutputMoments> {
        self.chains.get(chain)?.moments.get(output)
    }

    /// The moments of `output` pooled over every chain.
    pub fn moments(&self, output: usize) -> Option<OutputMoments> {
        if output >= self.outputs {
            return None;
        }
        Some(
            self.chains
                .iter()
                .filter_map(|c| c.moments.get(output))
                .fold(OutputMoments::default(), |pooled, m| pooled.merge(m)),
        )
    }

    /// The pooled mean of `output`.
    pub fn mean(&self, output: usize) -> Option<f64> {
        self.moments(output).filter(|m| m.count > 0).map(|m| m.mean)
    }

    /// The pooled sample variance of `output`.
    pub fn variance(&self, output: usize) -> Option<f64> {
        self.moments(output)?.variance()
    }

    /// The pooled `q`-quantile of `output` (`0 <= q <= 1`), by linear
    /// interpolation between order statistics as NumPy's default
    /// (`numpy.quantile(values, q)` on the pooled values), so a Python
    /// caller can check it bit for bit.
    pub fn quantile(&self, output: usize, q: f64) -> Option<f64> {
        if output >= self.outputs {
            return None;
        }
        let mut values: Vec<f64> = self.output(output).collect();
        quantile_in_place(&mut values, q)
    }

    /// The `q`-quantile of `output` over the draws of `chain`.
    pub fn chain_quantile(&self, chain: usize, output: usize, q: f64) -> Option<f64> {
        if chain >= self.chains.len() || output >= self.outputs {
            return None;
        }
        let mut values: Vec<f64> = self.chain_output(chain, output).collect();
        quantile_in_place(&mut values, q)
    }

    /// The retained draws of `chain` when [`Functionals::retain_draws`]
    /// was set.
    pub fn chain_draws(&self, chain: usize) -> Option<&[f64]> {
        self.chains.get(chain)?.samples.as_deref()
    }

    /// The warm state at the end of this call: per chain, its last draw,
    /// its step size and its diagonal mass.
    pub fn warm_state(&self) -> Result<WarmState, Error> {
        let chains = self
            .chains
            .iter()
            .enumerate()
            .map(|(index, chain)| {
                if chain.position.len() != self.dimension || self.dimension == 0 {
                    return Err(Error::configuration(format!(
                        "functional chunk chain {index} has no draw"
                    )));
                }
                Ok(WarmChain {
                    position: chain.position.clone(),
                    step_size: chain.step_size,
                    mass_diagonal: chain.mass_diagonal.clone(),
                })
            })
            .collect::<Result<Vec<_>, Error>>()?;
        WarmState::new(chains)
    }
}

/// NumPy's default (`method="linear"`) quantile of `values`, which are
/// sorted in place: the virtual index `q * (n - 1)`, its floor and the
/// lerp `a + (b - a) * g`, or `b - (b - a) * (1 - g)` from `g >= 0.5`, as
/// `numpy.lib._function_base_impl._lerp` computes it.
fn quantile_in_place(values: &mut [f64], q: f64) -> Option<f64> {
    if values.is_empty() || !(0.0..=1.0).contains(&q) {
        return None;
    }
    values.sort_unstable_by(f64::total_cmp);
    let last = values.len() - 1;
    let virtual_index = q * last as f64;
    let floor = virtual_index.floor();
    let gamma = virtual_index - floor;
    let lower = (floor as usize).min(last);
    let upper = (lower + 1).min(last);
    let (a, b) = (values[lower], values[upper]);
    let difference = b - a;
    Some(if gamma >= 0.5 {
        b - difference * (1.0 - gamma)
    } else {
        a + difference * gamma
    })
}

/// How each refresh call admits and caps its target evaluations: the
/// sampler's [`crate::sampler::Limits`] read per call.
#[derive(Clone, Copy, Debug)]
pub(crate) enum WarmBudget {
    /// No budget: the conservative admission ceiling only.
    Unbudgeted,
    /// `Limits::max_target_evaluations`: a fresh shared budget of this size
    /// per call.
    Fixed(NonZeroUsize),
    /// `Limits::admit_worst_case`: a fresh shared budget of the call's exact
    /// worst case.
    WorstCase,
}

/// Everything a session needs from the sampler.
pub(crate) struct WarmSessionSetup {
    pub threads: usize,
    pub base_seed: u64,
    pub budget: WarmBudget,
    pub deadline: Option<Instant>,
    pub timeout: Option<Duration>,
    pub external_cancellation: Option<Arc<dyn Cancellation>>,
    pub recipe: WarmRecipe,
}

/// The per-chain kernel inputs of one target and state, built by
/// [`WarmRecipe::plan`] and owned by the worker.
pub(crate) struct WarmPlan {
    /// Per chain: discarded 0, the chain's step, the sampler's tuning,
    /// limits and cache setting. `retained` and `seed` are set per call.
    pub configs: Vec<RunConfig>,
    pub masses: Vec<DiagonalMass>,
    /// The admission configuration (`retained` set per call).
    pub whole_run: RunConfig,
    pub positions: Vec<Vec<f64>>,
    pub dimension: usize,
}

struct WarmCancellation {
    local: Arc<AtomicBool>,
    external: Option<Arc<dyn Cancellation>>,
}

impl Cancellation for WarmCancellation {
    fn is_cancelled(&self) -> bool {
        self.local.load(Ordering::Acquire)
            || self.external.as_ref().is_some_and(|c| c.is_cancelled())
    }
}

enum Request<T> {
    Refresh {
        draws: usize,
        seed: u64,
        call_index: usize,
        deadline: Option<Instant>,
        functionals: Option<Functionals>,
        reply: mpsc::Sender<Result<RawChunk, Failure>>,
    },
    Retarget(Box<Retarget<T>>),
    Close,
}

struct Retarget<T> {
    target: T,
    plan: WarmPlan,
    reply: mpsc::Sender<Result<(), Error>>,
}

/// A failed refresh: `terminal` when the worker has stopped serving.
struct Failure {
    error: Error,
    terminal: bool,
}

/// A resident warm-continuation session: the target, a pool of `threads`
/// workers, and every per-chain configuration, mass and position stay
/// alive across [`WarmSession::refresh`] calls, so a call pays for its
/// transitions and the kernel's per-call buffers only.
///
/// Created by [`crate::sampler::Sampler::start_warm_session`]. The sampler
/// supplies the base seed, `threads`, tuning, limits and cached-initial-
/// evaluation setting; its `draws`, `warmup`, `metric` and `adaptation`
/// are ignored (`draws` is per call; nothing adapts).
///
/// # Seed rule
///
/// Call `n` (zero-based, [`WarmSession::calls`] before the call) uses the
/// base seed `seed_n = base_seed + n * chains` (wrapping), and chain `c` of
/// that call runs with seed `seed_n + c`, so its kernel RNG is
/// `splitmix64(seed_n + c)`. Call `n` is therefore bit-identical to
/// `Sampler::new().draws(k).seed(seed_n).run_warm(&target, &state)` with the
/// same tuning and limits, where `state` is [`WarmSession::state`] before
/// the call (`tests/warm_session.rs`). Successive calls never reuse a chain
/// seed; [`WarmSession::retarget`] does not reset the counter.
///
/// # Allocation
///
/// Per call, per chain, the kernel allocates its draw buffer
/// (`draws * dimension` values) and its diagnostics vector once, as it does
/// for `run_warm`; the [`WarmChunk`] hands those buffers over without
/// copying, plus a copy of the chain's mass diagonal and the call's
/// telemetry. No pool is built, no `Posterior` or metadata is assembled,
/// and no configuration, mass or start is re-validated beyond the per-call
/// admission checks `run_warm` makes (dimension, transition, result-size
/// and evaluation ceilings; no target call).
///
/// # Limits
///
/// `Limits::max_target_evaluations` and `Limits::admit_worst_case` apply
/// per call (a fresh shared budget each call); `Limits::timeout` is taken
/// from the start of each call; `Limits::deadline` and the cancellation
/// hook apply to every call. An execution error (budget exhausted,
/// deadline, cancellation, target failure, panic) makes the session
/// terminal: the worker exits, drops the target, and every later call
/// errors. An error before any target call ([`WarmSession::refresh`] with
/// zero draws or refused at admission, a [`WarmSession::retarget`] whose
/// state does not fit its target) is reported without touching the
/// session.
///
/// # Lifetime
///
/// [`WarmSession::close`] cancels and joins the worker; dropping the handle
/// cancels and detaches, so a target callback that never returns cannot
/// block a destructor. The worker keeps the target until its last callback
/// has returned.
pub struct WarmSession<T: Target + 'static> {
    requests: mpsc::Sender<Request<T>>,
    cancellation: Arc<AtomicBool>,
    worker: Mutex<Option<JoinHandle<()>>>,
    worker_id: std::thread::ThreadId,
    state: WarmState,
    recipe: WarmRecipe,
    base_seed: u64,
    threads: usize,
    deadline: Option<Instant>,
    timeout: Option<Duration>,
    calls: usize,
    terminal: bool,
}

impl<T: Target + 'static> WarmSession<T> {
    /// Run `draws` transitions per chain from the current state and return
    /// them. See the type documentation for the seed rule, the allocation
    /// behaviour and the limits.
    pub fn refresh(&mut self, draws: usize) -> Result<WarmChunk, Error> {
        self.refresh_raw(draws, None).map(RawChunk::into_warm_chunk)
    }

    /// Run `draws` transitions per chain as [`WarmSession::refresh`] does,
    /// evaluating `functionals` on every retained draw inside the chain
    /// loop and keeping the values (with running moments per output and
    /// per chain) instead of the draws; the state advances as for
    /// `refresh`. The call takes the same seed under the seed rule, so the
    /// values are the functionals of the draws `refresh` would return, bit
    /// for bit, and the draws and diagnostics are unaffected by the
    /// functionals (`tests/warm_functionals.rs`). With
    /// [`Functionals::retain_draws`] the chunk also holds the draws.
    ///
    /// Allocation per chain per call: `draws * outputs` values plus the
    /// per-output moments, instead of `draws * dimension` draws (the
    /// kernel's draw buffer is released at the start of the call and one
    /// draw is kept at a time); the diagnostics vector as for `refresh`.
    /// A functional error or panic is an execution error (the session
    /// becomes terminal).
    pub fn refresh_functionals(
        &mut self,
        draws: usize,
        functionals: &Functionals,
    ) -> Result<FunctionalChunk, Error> {
        self.refresh_raw(draws, Some(functionals.clone()))
            .map(|raw| raw.into_functional_chunk(functionals))
    }

    fn refresh_raw(
        &mut self,
        draws: usize,
        functionals: Option<Functionals>,
    ) -> Result<RawChunk, Error> {
        if draws == 0 {
            return Err(Error::configuration("draws must be nonzero"));
        }
        if self.terminal {
            return Err(Error::configuration("warm session is terminal"));
        }
        let deadline = match self.timeout {
            Some(timeout) => Some(
                Instant::now()
                    .checked_add(timeout)
                    .ok_or_else(|| Error::configuration("timeout overflows deadline"))?,
            ),
            None => self.deadline,
        };
        let call_index = self.calls;
        let seed = self.seed_for_call(call_index);
        let (tx, rx) = mpsc::channel();
        let sent = self.requests.send(Request::Refresh {
            draws,
            seed,
            call_index,
            deadline,
            functionals,
            reply: tx,
        });
        if sent.is_err() {
            self.terminal = true;
            return Err(Error::configuration("warm session is terminal"));
        }
        let result = rx.recv().unwrap_or_else(|_| {
            Err(Failure {
                error: Error::new(ErrorKind::Panic, "warm session worker disconnected"),
                terminal: true,
            })
        });
        match result {
            Ok(chunk) => {
                self.calls += 1;
                self.state
                    .set_positions(chunk.chains.iter().map(|c| c.last_position.as_slice()));
                Ok(chunk)
            }
            Err(Failure { error, terminal }) => {
                self.terminal |= terminal;
                Err(error)
            }
        }
    }

    /// The current state: every chain's position after the last call (or
    /// the state the session started from, or was retargeted to), with the
    /// carried step sizes and masses.
    pub fn state(&self) -> &WarmState {
        &self.state
    }

    /// Replace the target and the state (a new dimension is allowed, the
    /// chain count must be the session's). This is the per-tick "new
    /// observation" call: the caller builds the new target and the
    /// extended or remapped state ([`WarmState::extend_to`],
    /// [`WarmState::remap`], [`WarmState::shift_window`]). The old target
    /// drops on the worker thread. The call counter and therefore the seed
    /// sequence continue. Errors (`ErrorKind::Configuration`: the state's
    /// chain count or dimension does not fit) leave the session as it was.
    pub fn retarget(&mut self, target: T, state: WarmState) -> Result<(), Error> {
        if self.terminal {
            return Err(Error::configuration("warm session is terminal"));
        }
        if state.chain_count() != self.state.chain_count() {
            return Err(Error::configuration(format!(
                "warm state has {} chains; the session has {}",
                state.chain_count(),
                self.state.chain_count()
            )));
        }
        let plan = self.recipe.plan(&state)?;
        let (tx, rx) = mpsc::channel();
        let sent = self.requests.send(Request::Retarget(Box::new(Retarget {
            target,
            plan,
            reply: tx,
        })));
        if sent.is_err() {
            self.terminal = true;
            return Err(Error::configuration("warm session is terminal"));
        }
        match rx.recv() {
            Ok(Ok(())) => {
                self.state = state;
                Ok(())
            }
            Ok(Err(error)) => Err(error),
            Err(_) => {
                self.terminal = true;
                Err(Error::new(
                    ErrorKind::Panic,
                    "warm session worker disconnected",
                ))
            }
        }
    }

    /// Calls completed so far (the index of the next call).
    pub fn calls(&self) -> usize {
        self.calls
    }

    /// The base seed of call `call` under the seed rule:
    /// `base_seed + call * chains` (wrapping).
    pub fn seed_for_call(&self, call: usize) -> u64 {
        self.base_seed
            .wrapping_add((call as u64).wrapping_mul(self.state.chain_count() as u64))
    }

    /// The base seed the next call will use.
    pub fn next_seed(&self) -> u64 {
        self.seed_for_call(self.calls)
    }

    /// The sampler's base seed.
    pub fn base_seed(&self) -> u64 {
        self.base_seed
    }

    /// Resident worker threads (at most the chain count).
    pub fn threads(&self) -> usize {
        self.threads
    }

    /// Whether an execution error has ended the session.
    pub fn is_terminal(&self) -> bool {
        self.terminal
    }

    /// Request cooperative cancellation and the worker's exit without
    /// waiting. A running call returns `ErrorKind::Cancelled` at its next
    /// check and the session becomes terminal.
    pub fn cancel(&self) {
        self.cancellation.store(true, Ordering::Release);
        let _ = self.requests.send(Request::Close);
    }

    /// Cancel and join the worker. Errors when called from the worker or
    /// one of its pool threads (a target callback), where joining would
    /// deadlock; cancellation is still requested.
    pub fn close(&self) -> Result<(), Error> {
        self.cancel();
        if std::thread::current().id() == self.worker_id
            || WARM_WORKER.with(|id| id.get() == Arc::as_ptr(&self.cancellation) as usize)
        {
            return Err(Error::configuration(
                "cannot join a warm session from its own worker; cancellation was requested, close from another thread",
            ));
        }
        if let Some(worker) = self.worker.lock().unwrap_or_else(|p| p.into_inner()).take() {
            worker
                .join()
                .map_err(|_| Error::new(ErrorKind::Panic, "warm session worker panicked"))?;
        }
        Ok(())
    }
}

impl<T: Target + 'static> Drop for WarmSession<T> {
    fn drop(&mut self) {
        self.cancel();
    }
}

impl<T: Target + 'static> fmt::Debug for WarmSession<T> {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        f.debug_struct("WarmSession")
            .field("chains", &self.state.chain_count())
            .field("dimension", &self.state.dimension())
            .field("threads", &self.threads)
            .field("base_seed", &self.base_seed)
            .field("calls", &self.calls)
            .field("terminal", &self.terminal)
            .finish_non_exhaustive()
    }
}

pub(crate) fn spawn<T: Target + 'static>(
    target: T,
    state: WarmState,
    setup: WarmSessionSetup,
) -> Result<WarmSession<T>, Error> {
    let chains = state.chain_count();
    let threads = setup.threads.min(chains);
    if threads == 0 {
        return Err(Error::configuration("thread count must be nonzero"));
    }
    let mut plan = setup.recipe.plan(&state)?;
    // Admit the starting target and state as a retarget would, before any
    // thread exists.
    admit(&target, &mut plan, 1, setup.budget).map(drop)?;
    let (tx, rx) = mpsc::channel();
    let cancellation = Arc::new(AtomicBool::new(false));
    let worker_cancel = Arc::clone(&cancellation);
    let worker = std::thread::Builder::new()
        .name("owalnuts-warm-session".into())
        .spawn(move || {
            let session_id = Arc::as_ptr(&worker_cancel) as usize;
            WARM_WORKER.with(|id| id.set(session_id));
            let cancellation = WarmCancellation {
                local: worker_cancel,
                external: setup.external_cancellation,
            };
            let mut worker = Worker {
                target,
                plan,
                budget: setup.budget,
                threads,
                requests: rx,
            };
            let _ = catch_unwind(AssertUnwindSafe(|| {
                if threads == 1 {
                    worker.serve(&cancellation, None);
                    Ok(())
                } else {
                    with_scoped_pool_using(
                        threads,
                        |thread| {
                            WARM_WORKER.with(|id| id.set(session_id));
                            thread.run();
                            WARM_WORKER.with(|id| id.set(0));
                        },
                        |pool| worker.serve(&cancellation, Some(pool)),
                    )
                }
            }));
            // `worker` (and the target) drop here, after every chain run
            // and pool thread has finished.
        })
        .map_err(|e| Error::resource(format!("could not spawn warm session worker: {e}")))?;
    let worker_id = worker.thread().id();
    Ok(WarmSession {
        requests: tx,
        cancellation,
        worker: Mutex::new(Some(worker)),
        worker_id,
        state,
        recipe: setup.recipe,
        base_seed: setup.base_seed,
        threads,
        deadline: setup.deadline,
        timeout: setup.timeout,
        calls: 0,
        terminal: false,
    })
}

/// Per-call admission, as `Sampler::run_warm` admits a call: the
/// transition, dimension, chain, result-size and evaluation ceilings over
/// every chain, and the shared budget when one is configured. Returns the
/// call's budget size.
fn admit<T: Target>(
    target: &T,
    plan: &mut WarmPlan,
    draws: usize,
    budget: WarmBudget,
) -> Result<Option<NonZeroUsize>, Error> {
    let chains = NonZeroUsize::new(plan.positions.len())
        .ok_or_else(|| Error::configuration("warm state has no chains"))?;
    plan.whole_run.retained = draws;
    let whole_run = &plan.whole_run;
    let size = match budget {
        WarmBudget::Unbudgeted => None,
        WarmBudget::Fixed(size) => Some(size),
        WarmBudget::WorstCase => Some(
            NonZeroUsize::new(whole_run.worst_case_target_evaluations(chains)?)
                .ok_or_else(|| Error::configuration("worst case is zero"))?,
        ),
    };
    match size {
        Some(size) => {
            let budget = TargetEvaluationBudget::new(size);
            preflight_chains_with_target_budget(
                target,
                &plan.positions,
                &plan.masses[0],
                whole_run,
                TargetEvaluationAdmissionLimit::new(size),
                &budget,
            )?;
        }
        None => {
            preflight_chains(target, &plan.positions, &plan.masses[0], whole_run)?;
        }
    }
    Ok(size)
}

struct Worker<T: Target> {
    target: T,
    plan: WarmPlan,
    budget: WarmBudget,
    threads: usize,
    requests: mpsc::Receiver<Request<T>>,
}

/// What one chain run hands back to the worker.
struct ChainResult {
    /// The kernel's retained draws; empty on the functional path unless
    /// the draws are retained.
    samples: Vec<f64>,
    /// Functional values, draw-major `[draw][output]` (empty without
    /// functionals).
    values: Vec<f64>,
    moments: Vec<OutputMoments>,
    /// The chain's last draw.
    last_position: Vec<f64>,
    diagnostics: Vec<TransitionDiagnostics>,
    telemetry: RunTelemetry,
    step_size: f64,
    mass_diagonal: Vec<f64>,
    effective_seed: u64,
}

/// One call's chain results before they become a [`WarmChunk`] or a
/// [`FunctionalChunk`].
pub(crate) struct RawChunk {
    chains: Vec<ChainResult>,
    dimension: usize,
    draws: usize,
    seed: u64,
    call_index: usize,
    target_calls: usize,
}

impl RawChunk {
    fn into_warm_chunk(self) -> WarmChunk {
        WarmChunk {
            chains: self
                .chains
                .into_iter()
                .map(|result| WarmChainChunk {
                    samples: result.samples,
                    diagnostics: result.diagnostics,
                    telemetry: result.telemetry,
                    step_size: result.step_size,
                    mass_diagonal: result.mass_diagonal,
                    effective_seed: result.effective_seed,
                })
                .collect(),
            dimension: self.dimension,
            draws: self.draws,
            seed: self.seed,
            call_index: self.call_index,
            target_calls: self.target_calls,
        }
    }

    pub(crate) fn into_functional_chunk(self, functionals: &Functionals) -> FunctionalChunk {
        let retain = functionals.retains_draws();
        FunctionalChunk {
            chains: self
                .chains
                .into_iter()
                .map(|result| FunctionalChainChunk {
                    values: result.values,
                    moments: result.moments,
                    position: result.last_position,
                    samples: retain.then_some(result.samples),
                    diagnostics: result.diagnostics,
                    telemetry: result.telemetry,
                    step_size: result.step_size,
                    mass_diagonal: result.mass_diagonal,
                    effective_seed: result.effective_seed,
                })
                .collect(),
            dimension: self.dimension,
            outputs: functionals.outputs(),
            offsets: functionals.offsets.clone(),
            draws: self.draws,
            seed: self.seed,
            call_index: self.call_index,
            target_calls: self.target_calls,
        }
    }
}

/// Every chain of `plan` once, on a scoped pool of `threads` workers or
/// the calling thread.
fn run_chains_once<U: Target>(
    target: &U,
    plan: &WarmPlan,
    threads: usize,
    control: &RunControl<'_>,
    functionals: &Functionals,
) -> Result<Vec<ChainResult>, Error> {
    if threads == 1 {
        run_chains(target, plan, threads, control, None, Some(functionals))
    } else {
        with_scoped_pool(threads, |pool| {
            run_chains(
                target,
                plan,
                threads,
                control,
                Some(pool),
                Some(functionals),
            )
        })?
    }
}

/// Assemble a call's results and advance the plan's positions to the
/// chains' last draws.
fn assemble(
    plan: &mut WarmPlan,
    results: Vec<ChainResult>,
    draws: usize,
    seed: u64,
    call_index: usize,
) -> RawChunk {
    let mut target_calls = 0usize;
    for (position, result) in plan.positions.iter_mut().zip(&results) {
        position.copy_from_slice(&result.last_position);
        target_calls = target_calls.saturating_add(result.telemetry.total().target_calls_total());
    }
    RawChunk {
        chains: results,
        dimension: plan.dimension,
        draws,
        seed,
        call_index,
        target_calls,
    }
}

/// One-shot `Sampler::run_warm_functionals`: admit, run every chain once
/// on a scoped pool (or the calling thread), and assemble the chunk, as
/// call 0 of a session would (`seed` is the base seed, chain `c` runs on
/// `seed + c`).
pub(crate) fn run_warm_functionals_once<T: Target>(
    target: &T,
    state: &WarmState,
    setup: WarmSessionSetup,
    draws: usize,
    functionals: &Functionals,
) -> Result<FunctionalChunk, Error> {
    if draws == 0 {
        return Err(Error::configuration("draws must be nonzero"));
    }
    let threads = setup.threads.min(state.chain_count());
    if threads == 0 {
        return Err(Error::configuration("thread count must be nonzero"));
    }
    let mut plan = setup.recipe.plan(state)?;
    let size = admit(target, &mut plan, draws, setup.budget)?;
    for (chain, config) in plan.configs.iter_mut().enumerate() {
        config.retained = draws;
        config.seed = setup.base_seed.wrapping_add(chain as u64);
    }
    let deadline = match setup.timeout {
        Some(timeout) => Some(
            Instant::now()
                .checked_add(timeout)
                .ok_or_else(|| Error::configuration("timeout overflows deadline"))?,
        ),
        None => setup.deadline,
    };
    let mut control = RunControl::new();
    if let Some(cancellation) = &setup.external_cancellation {
        control = control.with_cancellation(&**cancellation);
    }
    if let Some(deadline) = deadline {
        control = control.with_deadline(deadline);
    }
    let results = match size {
        Some(size) => {
            let budget = TargetEvaluationBudget::new(size);
            let wrapped = budget.wrap(target);
            run_chains_once(&wrapped, &plan, threads, &control, functionals)
        }
        None => run_chains_once(target, &plan, threads, &control, functionals),
    }?;
    let raw = assemble(&mut plan, results, draws, setup.base_seed, 0);
    Ok(raw.into_functional_chunk(functionals))
}

impl<T: Target> Worker<T> {
    fn serve(&mut self, cancellation: &WarmCancellation, pool: Option<&rayon::ThreadPool>) {
        loop {
            match self.requests.recv() {
                Ok(Request::Refresh {
                    draws,
                    seed,
                    call_index,
                    deadline,
                    functionals,
                    reply,
                }) => {
                    let result = self.refresh(
                        draws,
                        seed,
                        call_index,
                        deadline,
                        functionals.as_ref(),
                        cancellation,
                        pool,
                    );
                    let terminal = result.as_ref().is_err_and(|failure| failure.terminal);
                    if reply.send(result).is_err() || terminal {
                        return;
                    }
                }
                Ok(Request::Retarget(request)) => {
                    let Retarget {
                        target,
                        mut plan,
                        reply,
                    } = *request;
                    let admitted = catch_unwind(AssertUnwindSafe(|| {
                        admit(&target, &mut plan, 1, self.budget).map(drop)
                    }))
                    .unwrap_or_else(|_| {
                        Err(Error::new(
                            ErrorKind::Panic,
                            "target dimension callback panicked",
                        ))
                    });
                    let result = admitted.map(|()| {
                        self.target = target;
                        self.plan = plan;
                    });
                    if reply.send(result).is_err() {
                        return;
                    }
                }
                Ok(Request::Close) | Err(_) => return,
            }
        }
    }

    #[allow(clippy::too_many_arguments)]
    fn refresh(
        &mut self,
        draws: usize,
        seed: u64,
        call_index: usize,
        deadline: Option<Instant>,
        functionals: Option<&Functionals>,
        cancellation: &WarmCancellation,
        pool: Option<&rayon::ThreadPool>,
    ) -> Result<RawChunk, Failure> {
        let mut control = RunControl::new().with_cancellation(cancellation);
        if let Some(deadline) = deadline {
            control = control.with_deadline(deadline);
        }
        // Refused at admission: no target call was made and the state is
        // intact, so the session goes on.
        let size =
            admit(&self.target, &mut self.plan, draws, self.budget).map_err(|error| Failure {
                error,
                terminal: false,
            })?;
        for (chain, config) in self.plan.configs.iter_mut().enumerate() {
            config.retained = draws;
            config.seed = seed.wrapping_add(chain as u64);
        }
        let threads = self.threads;
        let results = match size {
            Some(size) => {
                let budget = TargetEvaluationBudget::new(size);
                let wrapped = budget.wrap(&self.target);
                run_chains(&wrapped, &self.plan, threads, &control, pool, functionals)
            }
            None => run_chains(
                &self.target,
                &self.plan,
                threads,
                &control,
                pool,
                functionals,
            ),
        }
        .map_err(|error| Failure {
            error,
            terminal: true,
        })?;
        Ok(assemble(&mut self.plan, results, draws, seed, call_index))
    }
}

/// Run every chain of the plan once, as `sample_chains_with_control` runs
/// a one-chain run per chain in `Sampler::run_warm`: a fresh `ChainRun`
/// from the chain's position with the chain's configuration and seed
/// `splitmix64(config.seed)`, advanced over its transitions.
fn run_chains<U: Target>(
    target: &U,
    plan: &WarmPlan,
    threads: usize,
    control: &RunControl<'_>,
    pool: Option<&rayon::ThreadPool>,
    functionals: Option<&Functionals>,
) -> Result<Vec<ChainResult>, Error> {
    let failed_chain = AtomicUsize::new(usize::MAX);
    let execute = |chain: usize| -> Result<ChainResult, Error> {
        let control = ExecutionControl {
            public: control,
            failed_chain: Some(&failed_chain),
            chain,
        };
        let result = catch_unwind(AssertUnwindSafe(|| {
            run_one(
                target,
                plan.dimension,
                &plan.positions[chain],
                &plan.masses[chain],
                &plan.configs[chain],
                threads,
                &control,
                functionals,
            )
        }))
        .unwrap_or_else(|_| Err(Error::new(ErrorKind::Panic, "warm session chain panicked")))
        .map_err(|error| error.at_chain(chain));
        if result.is_err() {
            failed_chain.fetch_min(chain, Ordering::AcqRel);
        }
        result
    };
    let chains = plan.positions.len();
    let results: Vec<Result<ChainResult, Error>> = match pool {
        Some(pool) => pool.install(|| (0..chains).into_par_iter().map(execute).collect()),
        None => (0..chains).map(execute).collect(),
    };
    results.into_iter().collect()
}

#[allow(clippy::too_many_arguments)]
fn run_one<U: Target>(
    target: &U,
    dimension: usize,
    position: &[f64],
    mass: &DiagonalMass,
    config: &RunConfig,
    threads: usize,
    control: &ExecutionControl<'_>,
    functionals: Option<&Functionals>,
) -> Result<ChainResult, Error> {
    // As `run_chain`: the kinetic-energy context is only needed by proposal
    // observers, which the warm path never attaches.
    let _context_kinetic = ContextKineticScope::new(control.public.proposal_observations.is_some());
    let mut run = ChainRun::start(
        target,
        dimension,
        position,
        mass,
        None,
        false,
        config,
        chain_seed(config.seed, 0),
        threads,
        control,
        None,
        None,
    )?;
    run.rescue_record = None;
    let mut last_position = vec![0.0; dimension];
    let mut values = Vec::new();
    let mut moments = Vec::new();
    match functionals {
        None => {
            run.advance(run.transitions)?;
            last_position.copy_from_slice(last_draw(&run.samples, dimension)?);
        }
        Some(functionals) => {
            // The streaming path: one transition at a time through the same
            // `advance`, the functionals on each new draw, and the kernel's
            // draw buffer released up front (one draw is kept at a time)
            // unless the draws are wanted too.
            let outputs = functionals.outputs();
            let transitions = run.transitions;
            values
                .try_reserve_exact(
                    transitions
                        .checked_mul(outputs)
                        .ok_or_else(Error::overflow)?,
                )
                .map_err(|_| Error::resource("functional value allocation failed"))?;
            moments.resize(outputs, OutputMoments::default());
            let retain = functionals.retains_draws();
            if !retain {
                let mut one_draw = Vec::new();
                one_draw
                    .try_reserve_exact(dimension)
                    .map_err(|_| Error::resource("draw allocation failed"))?;
                run.samples = one_draw;
            }
            for transition in 0..transitions {
                run.advance(transition + 1)?;
                let draw = last_draw(&run.samples, dimension)?;
                let start = values.len();
                values.resize(start + outputs, 0.0);
                let out = &mut values[start..];
                for (index, (functional, range)) in functionals
                    .functionals()
                    .iter()
                    .zip(functionals.ranges())
                    .enumerate()
                {
                    functional
                        .evaluate(draw, &mut out[range])
                        .map_err(|error| {
                            Error::new(
                                ErrorKind::Target,
                                format!("functional {index} failed: {}", error.message()),
                            )
                        })?;
                }
                for (moment, value) in moments.iter_mut().zip(&values[start..]) {
                    moment.push(*value);
                }
                if transition + 1 == transitions {
                    last_position.copy_from_slice(draw);
                }
                if !retain {
                    run.samples.clear();
                }
            }
        }
    }
    // As `ChainRun::finish`: a final control check, then the retained-draw
    // window summary.
    control.check().map_err(control_error)?;
    let telemetry = run.telemetry_snapshot();
    Ok(ChainResult {
        samples: std::mem::take(&mut run.samples),
        values,
        moments,
        last_position,
        diagnostics: std::mem::take(&mut run.diagnostics),
        telemetry,
        step_size: run.active_tuning.step_size,
        mass_diagonal: run.active_mass.diagonal.clone(),
        effective_seed: run.seed,
    })
}

/// The last `dimension` values of the kernel's draw buffer.
fn last_draw(samples: &[f64], dimension: usize) -> Result<&[f64], Error> {
    samples
        .len()
        .checked_sub(dimension)
        .filter(|_| dimension > 0)
        .and_then(|start| samples.get(start..))
        .ok_or_else(|| Error::new(ErrorKind::Internal, "warm chain retained no draw"))
}
