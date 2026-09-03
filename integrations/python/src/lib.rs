//! Thin PyO3 wrapper over the public `owalnuts::sampler` API.
//!
//! Every sampling call builds an `owalnuts::sampler::Sampler` from the Python
//! arguments, so the package inherits the sampler's defaults (tuning, kernel
//! rules, warmup exhaustion, metric regularisation, cached initial evaluation,
//! worst-case admission) instead of restating them; `DEFAULTS` reports them
//! read-only. Nothing here touches kernel internals. The Python thread
//! releases the GIL for the duration of a run (`Python::detach`), and each
//! target callback re-attaches from whichever Rust worker thread executes it,
//! so Python targets are serialised by the GIL while native built-in targets
//! run fully parallel.

use std::num::NonZeroUsize;
use std::sync::Mutex;
use std::sync::atomic::{AtomicU64, AtomicUsize, Ordering};
use std::time::Instant;

use numpy::{
    IntoPyArray, PyArray1, PyArray2, PyArray3, PyArrayMethods, PyReadonlyArray1, PyReadonlyArray2,
    PyReadonlyArray3,
};
use owalnuts::diagnostics::ParameterSummary;
use owalnuts::sampler::{
    Adaptation, DEFAULT_METRIC_REGULARIZATION, DEFAULT_WARMUP_EXHAUSTION, Init, Limits, Metric,
    Posterior, Sampler, Tuning, uniform_starts,
};
use owalnuts::walnutpie::{
    ALGORITHM_REVISION, CONSERVATIVE_MAX_TARGET_EVALUATIONS, ChainOutput,
    DiagonalMetricRegularization, Error, ExhaustionRule, KernelOptions, MultiChainOutput,
    PAPER_ADAPTATION_REVISION, PaperAdaptationConfig, PaperRestartPolicy, PaperStepStatistic,
    RESEARCH_MAX_TARGET_EVALUATIONS, RawTarget, RawTargetFn, StopReason, StructuredBlockMass,
    StructuredCovarianceBlock, StructuredMetricRefresh, StructuredRefreshConfig,
    StructuredRefreshRestartPolicy, Target, TargetError, UTurnRule, WarmupConfig, WindowSummary,
    WorkTotals,
};
use pyo3::exceptions::{PyRuntimeError, PyValueError};
use pyo3::prelude::*;
use pyo3::types::{PyDict, PyList, PyTuple};

// ── Errors ───────────────────────────────────────────────────────────────

fn facade_error(error: Error) -> PyErr {
    PyRuntimeError::new_err(format!("owalnuts {:?}: {}", error.kind(), error))
}

fn value_error(message: impl Into<String>) -> PyErr {
    PyValueError::new_err(message.into())
}

fn nonzero(value: usize, name: &str) -> PyResult<NonZeroUsize> {
    NonZeroUsize::new(value).ok_or_else(|| value_error(format!("{name} must be positive")))
}

// ── Python callable target ───────────────────────────────────────────────

#[derive(Clone, Copy)]
enum NonFinitePolicy {
    /// `-inf`, `nan`, or nonfinite gradients define a zero-density point and
    /// follow the facade's recoverable path (refine, then zero weight).
    ZeroDensity,
    /// Any nonfinite output fails the whole run.
    Fatal,
}

impl NonFinitePolicy {
    fn parse(text: &str) -> PyResult<Self> {
        match text {
            "zero_density" => Ok(Self::ZeroDensity),
            "fatal" => Ok(Self::Fatal),
            other => Err(value_error(format!(
                "nonfinite must be 'zero_density' or 'fatal', got {other:?}"
            ))),
        }
    }
}

/// A `Callable[[np.ndarray], tuple[float, np.ndarray]]` seen as a facade target.
struct PyTarget {
    callable: Py<PyAny>,
    dimension: usize,
    policy: NonFinitePolicy,
    calls: AtomicUsize,
    recoverable: AtomicUsize,
    attached_nanos: AtomicU64,
    /// First fatal target message; the facade's `Error` does not carry it.
    last_fatal: Mutex<Option<String>>,
}

/// Exception classes that describe a deterministic zero-density region.
const RECOVERABLE_EXCEPTIONS: [&str; 5] = [
    "ZeroDensityError",
    "FloatingPointError",
    "OverflowError",
    "ZeroDivisionError",
    "ValueError",
];

impl PyTarget {
    fn classify_exception(&self, py: Python<'_>, error: PyErr) -> TargetError {
        let type_name = error
            .get_type(py)
            .name()
            .map(|n| n.to_string())
            .unwrap_or_default();
        let message = format!("{type_name}: {}", error.value(py));
        match self.policy {
            NonFinitePolicy::ZeroDensity
                if RECOVERABLE_EXCEPTIONS
                    .iter()
                    .any(|name| type_name.ends_with(name)) =>
            {
                self.recoverable.fetch_add(1, Ordering::Relaxed);
                TargetError::recoverable(message)
            }
            _ => {
                self.record_fatal(&message);
                TargetError::new(message)
            }
        }
    }

    fn record_fatal(&self, message: &str) {
        if let Ok(mut slot) = self.last_fatal.lock() {
            slot.get_or_insert_with(|| message.to_string());
        }
    }

    fn fatal_error(&self, error: Error) -> PyErr {
        let detail = self.last_fatal.lock().ok().and_then(|s| s.clone());
        match detail {
            Some(detail) => PyRuntimeError::new_err(format!(
                "owalnuts {:?}: {} ({detail})",
                error.kind(),
                error
            )),
            None => facade_error(error),
        }
    }
}

impl Target for PyTarget {
    fn dimension(&self) -> usize {
        self.dimension
    }

    fn log_density_gradient(
        &self,
        position: &[f64],
        gradient: &mut [f64],
    ) -> Result<f64, TargetError> {
        self.calls.fetch_add(1, Ordering::Relaxed);
        let started = Instant::now();
        let value = Python::attach(|py| -> Result<f64, TargetError> {
            let array = PyArray1::from_slice(py, position);
            let result = self
                .callable
                .call1(py, (array,))
                .map_err(|e| self.classify_exception(py, e))?;
            let bound = result.into_bound(py);
            let tuple = bound
                .cast::<PyTuple>()
                .map_err(|_| TargetError::new("target must return (log_density, gradient)"))?;
            if tuple.len() != 2 {
                return Err(TargetError::new("target must return a 2-tuple"));
            }
            let value: f64 = tuple
                .get_item(0)
                .and_then(|v| v.extract())
                .map_err(|e| TargetError::new(format!("log density is not a float: {e}")))?;
            let grad_obj = tuple
                .get_item(1)
                .map_err(|e| TargetError::new(format!("missing gradient: {e}")))?;
            let grad: PyReadonlyArray1<'_, f64> = grad_obj.extract().map_err(|e| {
                TargetError::new(format!(
                    "gradient must be a contiguous float64 numpy array: {e}"
                ))
            })?;
            let slice = grad
                .as_slice()
                .map_err(|e| TargetError::new(format!("gradient is not contiguous: {e}")))?;
            if slice.len() != gradient.len() {
                return Err(TargetError::new(format!(
                    "gradient length {} does not match dimension {}",
                    slice.len(),
                    gradient.len()
                )));
            }
            gradient.copy_from_slice(slice);
            Ok(value)
        });
        self.attached_nanos
            .fetch_add(started.elapsed().as_nanos() as u64, Ordering::Relaxed);
        let value = value?;
        let gradient_finite = gradient.iter().all(|x| x.is_finite());
        if value.is_finite() && gradient_finite {
            return Ok(value);
        }
        match self.policy {
            NonFinitePolicy::ZeroDensity => {
                self.recoverable.fetch_add(1, Ordering::Relaxed);
                Err(TargetError::recoverable(if value == f64::NEG_INFINITY {
                    "log density is -inf"
                } else {
                    "nonfinite log density or gradient"
                }))
            }
            NonFinitePolicy::Fatal => {
                let message = "nonfinite log density or gradient with nonfinite='fatal'";
                self.record_fatal(message);
                Err(TargetError::new(message))
            }
        }
    }
}

// ── Built-in native targets (benchmark references) ───────────────────────

const LOG_2PI: f64 = 1.837_877_066_409_345_3;

fn normal_log_density(x: f64, mean: f64, sd: f64) -> f64 {
    -0.5 * LOG_2PI - sd.ln() - 0.5 * ((x - mean) / sd).powi(2)
}

/// Noncentered Eight Schools in the v38 unconstrained coordinates
/// `(mu, log tau, z_1..z_8)`; verbatim mathematics of the frozen benchmark.
struct EightSchools {
    y: Vec<f64>,
    se: Vec<f64>,
    calls: AtomicUsize,
}

impl Target for EightSchools {
    fn dimension(&self) -> usize {
        2 + self.y.len()
    }
    fn log_density_gradient(&self, q: &[f64], g: &mut [f64]) -> Result<f64, TargetError> {
        self.calls.fetch_add(1, Ordering::Relaxed);
        let mu = q[0];
        let log_tau = q[1];
        let tau = log_tau.exp();
        let z = &q[2..];
        let mut value = normal_log_density(mu, 0., 5.)
            + (2. / (std::f64::consts::PI * 5. * (1. + (tau / 5.).powi(2)))).ln()
            + log_tau;
        g.fill(0.);
        g[0] = -mu / 25.;
        g[1] = 1. - 2. * tau * tau / (25. + tau * tau);
        for j in 0..self.y.len() {
            let theta = mu + tau * z[j];
            let residual = self.y[j] - theta;
            let likelihood_gradient = residual / self.se[j].powi(2);
            value +=
                normal_log_density(self.y[j], theta, self.se[j]) + normal_log_density(z[j], 0., 1.);
            g[0] += likelihood_gradient;
            g[1] += likelihood_gradient * tau * z[j];
            g[j + 2] = -z[j] + likelihood_gradient * tau;
        }
        if value.is_finite() && g.iter().all(|x| x.is_finite()) {
            Ok(value)
        } else {
            Err(TargetError::new("nonfinite target evaluation"))
        }
    }
}

/// Centered Gaussian local-level path with fixed globals (WP4 target):
/// `x_1 ~ N(m0, tau0^2)`, `x_t = x_{t-1} + mu + N(0, sigma_x^2)`,
/// `y_t ~ N(x_t, r_t)`.
struct LocalLevel {
    y: Vec<f64>,
    r: Vec<f64>,
    m0: f64,
    tau0: f64,
    mu: f64,
    sigma_x: f64,
    calls: AtomicUsize,
}

impl Target for LocalLevel {
    fn dimension(&self) -> usize {
        self.y.len()
    }
    fn log_density_gradient(&self, q: &[f64], g: &mut [f64]) -> Result<f64, TargetError> {
        self.calls.fetch_add(1, Ordering::Relaxed);
        let t = q.len();
        let s2 = 1.0 / (self.sigma_x * self.sigma_x);
        let mut lp = 0.0;
        g.iter_mut().for_each(|x| *x = 0.0);
        let d0 = q[0] - self.m0;
        lp -= 0.5 * d0 * d0 / (self.tau0 * self.tau0);
        g[0] -= d0 / (self.tau0 * self.tau0);
        for i in 1..t {
            let inn = q[i] - q[i - 1] - self.mu;
            lp -= 0.5 * inn * inn * s2;
            g[i] -= inn * s2;
            g[i - 1] += inn * s2;
        }
        for i in 0..t {
            let res = self.y[i] - q[i];
            let ri = 1.0 / self.r[i];
            lp -= 0.5 * res * res * ri;
            g[i] += res * ri;
        }
        Ok(lp)
    }
}

// ── Configuration parsing ────────────────────────────────────────────────
//
// Every key is optional except `warmup`, `draws` and `seed`: an absent key
// leaves the corresponding `owalnuts::sampler` default in place, so the
// package never restates a sampler default.

fn get<'py, T>(dict: &Bound<'py, PyDict>, key: &str) -> PyResult<Option<T>>
where
    T: for<'a> FromPyObject<'a, 'py>,
    for<'a> <T as FromPyObject<'a, 'py>>::Error: Into<PyErr>,
{
    match dict.get_item(key)? {
        Some(v) if !v.is_none() => Ok(Some(v.extract().map_err(Into::into)?)),
        _ => Ok(None),
    }
}

fn required<'py, T>(dict: &Bound<'py, PyDict>, key: &str) -> PyResult<T>
where
    T: for<'a> FromPyObject<'a, 'py>,
    for<'a> <T as FromPyObject<'a, 'py>>::Error: Into<PyErr>,
{
    get(dict, key)?.ok_or_else(|| value_error(format!("missing config key {key:?}")))
}

// Python-facing names of the kernel rule and regularisation variants. The
// `DEFAULTS` dict reports the sampler defaults through the same names.

fn u_turn_name(rule: UTurnRule) -> &'static str {
    match rule {
        UTurnRule::Endpoints => "endpoints",
        UTurnRule::EndpointsWithCross => "endpoints_with_cross",
        UTurnRule::MomentumSum => "momentum_sum",
    }
}

fn parse_u_turn(name: &str) -> PyResult<UTurnRule> {
    match name {
        "endpoints" => Ok(UTurnRule::Endpoints),
        "endpoints_with_cross" => Ok(UTurnRule::EndpointsWithCross),
        "momentum_sum" => Ok(UTurnRule::MomentumSum),
        other => Err(value_error(format!(
            "unknown u_turn_rule {other:?} (endpoints | endpoints_with_cross | momentum_sum)"
        ))),
    }
}

fn exhaustion_name(rule: ExhaustionRule) -> &'static str {
    match rule {
        ExhaustionRule::Stop => "stop",
        ExhaustionRule::AcceptBelowDivergenceThreshold => "accept_below_divergence_threshold",
        ExhaustionRule::AcceptUnlessDivergent => "accept_unless_divergent",
    }
}

fn parse_exhaustion(name: &str) -> PyResult<ExhaustionRule> {
    match name {
        "stop" => Ok(ExhaustionRule::Stop),
        "accept_below_divergence_threshold" => Ok(ExhaustionRule::AcceptBelowDivergenceThreshold),
        "accept_unless_divergent" => Ok(ExhaustionRule::AcceptUnlessDivergent),
        other => Err(value_error(format!(
            "unknown exhaustion_rule {other:?} (stop | accept_below_divergence_threshold | \
             accept_unless_divergent)"
        ))),
    }
}

fn regularization_name(regularization: DiagonalMetricRegularization) -> &'static str {
    match regularization {
        DiagonalMetricRegularization::TowardUnit => "toward_unit",
        DiagonalMetricRegularization::Stan => "stan",
        _ => "unknown",
    }
}

fn parse_regularization(name: &str) -> PyResult<DiagonalMetricRegularization> {
    match name {
        "toward_unit" => Ok(DiagonalMetricRegularization::TowardUnit),
        "stan" => Ok(DiagonalMetricRegularization::Stan),
        other => Err(value_error(format!(
            "unknown metric_regularization {other:?} (toward_unit | stan)"
        ))),
    }
}

/// `owalnuts::sampler::Tuning::default()` with the keys present in `cfg`
/// applied on top.
fn parse_tuning(cfg: &Bound<'_, PyDict>) -> PyResult<Tuning> {
    let mut tuning = Tuning::new();
    if let Some(v) = get::<f64>(cfg, "step_size")? {
        tuning = tuning.step_size(v);
    }
    if let Some(v) = get::<usize>(cfg, "max_depth")? {
        tuning = tuning.max_depth(v);
    }
    if let Some(v) = get::<usize>(cfg, "min_micro_steps")? {
        tuning = tuning.min_micro_steps(v);
    }
    if let Some(v) = get::<usize>(cfg, "max_refinement_levels")? {
        tuning = tuning.max_refinement_levels(v);
    }
    if let Some(v) = get::<f64>(cfg, "max_error")? {
        tuning = tuning.max_error(v);
    }
    if let Some(v) = get::<f64>(cfg, "divergence_threshold")? {
        tuning = tuning.divergence_threshold(v);
    }
    let u_turn: Option<String> = get(cfg, "u_turn_rule")?;
    let exhaustion: Option<String> = get(cfg, "exhaustion_rule")?;
    if u_turn.is_some() || exhaustion.is_some() {
        let defaults = default_kernel_options()?;
        tuning = tuning.kernel_options(KernelOptions {
            u_turn: u_turn
                .as_deref()
                .map(parse_u_turn)
                .transpose()?
                .unwrap_or(defaults.u_turn),
            exhaustion: exhaustion
                .as_deref()
                .map(parse_exhaustion)
                .transpose()?
                .unwrap_or(defaults.exhaustion),
        });
    }
    Ok(tuning)
}

/// The kernel options of `owalnuts::sampler::Tuning::default()`.
fn default_kernel_options() -> PyResult<KernelOptions> {
    Ok(Tuning::default()
        .to_kernel()
        .map_err(facade_error)?
        .options())
}

/// The target acceptance of `owalnuts::sampler::Adaptation::default()`.
fn default_target_accept() -> PyResult<f64> {
    match Adaptation::default() {
        Adaptation::DualAveraging { target_accept } => Ok(target_accept),
        other => Err(PyRuntimeError::new_err(format!(
            "owalnuts sampler default adaptation is not dual averaging: {other:?}"
        ))),
    }
}

fn parse_paper(cfg: &Bound<'_, PyDict>) -> PyResult<Option<PaperAdaptationConfig>> {
    let Some(paper) = cfg.get_item("paper_adaptation")? else {
        return Ok(None);
    };
    if paper.is_none() {
        return Ok(None);
    }
    let paper = paper
        .cast::<PyDict>()
        .map_err(|_| value_error("paper_adaptation must be a dict or None"))?;
    let delta: f64 = get(paper, "global_energy_bound")?.unwrap_or(2.0);
    let p_a: f64 = get(paper, "quantile_probability")?.unwrap_or(0.95);
    let gamma: f64 = get(paper, "unrefined_fraction_target")?.unwrap_or(0.8);
    let adapt_local_error: bool = get(paper, "adapt_local_error")?.unwrap_or(true);
    let mut paper_config = PaperAdaptationConfig::new(delta, p_a, gamma)
        .map_err(facade_error)?
        .with_local_error_adaptation(adapt_local_error);
    if let Some(min_orbits) = get::<usize>(paper, "minimum_orbits")? {
        paper_config = paper_config.with_minimum_orbits(nonzero(min_orbits, "minimum_orbits")?);
    }
    if let Some(statistic) = get::<String>(paper, "step_statistic")? {
        paper_config = paper_config.with_step_statistic(match statistic.as_str() {
            "per_transition" => PaperStepStatistic::PerTransition,
            "cumulative" => PaperStepStatistic::Cumulative,
            other => return Err(value_error(format!("unknown step_statistic {other:?}"))),
        });
    }
    if let Some(policy) = get::<String>(paper, "restart_policy")? {
        paper_config = paper_config.with_restart_policy(match policy.as_str() {
            "restart" => PaperRestartPolicy::RestartOnLocalErrorInstall,
            "continue" => PaperRestartPolicy::ContinueThroughLocalErrorInstall,
            other => return Err(value_error(format!("unknown restart_policy {other:?}"))),
        });
    }
    Ok(Some(paper_config))
}

/// The sampler's own adaptation modes (`DualAveraging`, `Paper`) whenever the
/// configuration is expressible through them; `Adaptation::Custom` only for
/// `adapt_step_size=False` or an explicit `metric_regularization`, built with
/// the same `DEFAULT_WARMUP_EXHAUSTION` / `DEFAULT_METRIC_REGULARIZATION` the
/// sampler applies to its own modes.
fn parse_adaptation(cfg: &Bound<'_, PyDict>) -> PyResult<Adaptation> {
    let adapt: bool = get(cfg, "adapt")?.unwrap_or(true);
    if !adapt {
        return Ok(Adaptation::None);
    }
    let target_accept: f64 = match get(cfg, "target_accept")? {
        Some(value) => value,
        None => default_target_accept()?,
    };
    let adapt_step: bool = get(cfg, "adapt_step_size")?.unwrap_or(true);
    let regularization: Option<String> = get(cfg, "metric_regularization")?;
    let paper = parse_paper(cfg)?;
    if adapt_step && regularization.is_none() {
        return Ok(match paper {
            Some(paper) => Adaptation::Paper(paper),
            None => Adaptation::DualAveraging { target_accept },
        });
    }
    let warmup = match paper {
        Some(paper) => WarmupConfig::default().with_paper_adaptation(paper),
        None => WarmupConfig::new(target_accept).map_err(facade_error)?,
    };
    let regularization = regularization
        .as_deref()
        .map(parse_regularization)
        .transpose()?
        .unwrap_or(DEFAULT_METRIC_REGULARIZATION);
    Ok(Adaptation::Custom(
        warmup
            .with_step_size_adaptation(adapt_step)
            .with_warmup_exhaustion_rule(DEFAULT_WARMUP_EXHAUSTION)
            .with_metric_regularization(regularization),
    ))
}

fn parse_blocks(blocks: &Bound<'_, PyList>) -> PyResult<Vec<StructuredCovarianceBlock>> {
    let mut parsed = Vec::with_capacity(blocks.len());
    for block in blocks.iter() {
        let block = block
            .cast::<PyDict>()
            .map_err(|_| value_error("mass block must be a dict"))?;
        let kind: String = required(block, "type")?;
        match kind.as_str() {
            "diagonal" => {
                let diagonal: PyReadonlyArray1<'_, f64> = required(block, "diagonal")?;
                let diagonal = diagonal.as_slice()?;
                if diagonal.iter().any(|x| !x.is_finite() || *x <= 0.0) {
                    return Err(value_error(
                        "diagonal mass block must be finite and positive",
                    ));
                }
                parsed.push(StructuredCovarianceBlock::BidiagonalCholesky {
                    diagonal: diagonal.iter().map(|x| x.sqrt()).collect(),
                    subdiagonal: vec![0.0; diagonal.len().saturating_sub(1)],
                });
            }
            "bidiagonal_cholesky" => {
                let diagonal: PyReadonlyArray1<'_, f64> = required(block, "diagonal")?;
                let subdiagonal: PyReadonlyArray1<'_, f64> = required(block, "subdiagonal")?;
                parsed.push(StructuredCovarianceBlock::BidiagonalCholesky {
                    diagonal: diagonal.as_slice()?.to_vec(),
                    subdiagonal: subdiagonal.as_slice()?.to_vec(),
                });
            }
            "scaled_ar1" => {
                let scale: PyReadonlyArray1<'_, f64> = required(block, "scale")?;
                let rho: f64 = required(block, "rho")?;
                parsed.push(StructuredCovarianceBlock::ScaledAr1 {
                    scale: scale.as_slice()?.to_vec(),
                    rho,
                });
            }
            other => {
                return Err(value_error(format!(
                    "unknown mass block type {other:?} (diagonal | bidiagonal_cholesky | scaled_ar1)"
                )));
            }
        }
    }
    Ok(parsed)
}

/// Python slow-window refresh callback for structured-mass runs.
struct PyRefresh {
    callable: Py<PyAny>,
}

impl StructuredMetricRefresh for PyRefresh {
    fn refresh(
        &self,
        summary: &WindowSummary,
        current: &StructuredBlockMass,
    ) -> Result<StructuredBlockMass, Error> {
        Python::attach(|py| {
            let mean = PyArray1::from_slice(py, summary.mean());
            let variance = PyArray1::from_slice(py, summary.variance());
            let result = self
                .callable
                .bind(py)
                .call1((
                    summary.window_index(),
                    summary.transition(),
                    summary.sample_count(),
                    mean,
                    variance,
                ))
                .map_err(|e| Error::metric_candidate(format!("refresh callback raised: {e}")))?;
            if result.is_none() {
                return Ok(current.clone());
            }
            let list = result.cast::<PyList>().map_err(|_| {
                Error::metric_candidate(
                    "refresh callback must return None or a list of mass blocks",
                )
            })?;
            let blocks = parse_blocks(list)
                .map_err(|e| Error::metric_candidate(format!("refresh blocks invalid: {e}")))?;
            StructuredBlockMass::new(blocks)
        })
    }
}

/// Structured-refresh request: the Python callback and its restart policy.
struct Refresh {
    callable: Py<PyAny>,
    restart: StructuredRefreshRestartPolicy,
}

fn parse_refresh(callable: Option<Py<PyAny>>, restart: &str) -> PyResult<Option<Refresh>> {
    let Some(callable) = callable else {
        return Ok(None);
    };
    let restart = match restart {
        "continue" => StructuredRefreshRestartPolicy::ContinueDualAveraging,
        "restart" => StructuredRefreshRestartPolicy::RestartDualAveraging,
        other => return Err(value_error(format!("unknown refresh_restart {other:?}"))),
    };
    Ok(Some(Refresh { callable, restart }))
}

/// `mass=None` is the identity diagonal, a 1-D array a diagonal, a list of
/// block dicts a structured mass (`Metric::Structured`, or
/// `Metric::StructuredRefresh` with a refresh callback). `adapt_mass` applies
/// to the diagonal metrics only; a structured mass is fixed unless refreshed.
fn parse_metric(
    spec: Option<Bound<'_, PyAny>>,
    adapt_mass: bool,
    refresh: Option<Refresh>,
) -> PyResult<Metric> {
    let spec = spec.filter(|spec| !spec.is_none());
    let blocks = match spec {
        None => None,
        Some(spec) => {
            if let Ok(diagonal) = spec.extract::<PyReadonlyArray1<'_, f64>>() {
                if refresh.is_some() {
                    return Err(value_error("refresh requires a structured mass"));
                }
                return Ok(Metric::Diagonal {
                    adapt: adapt_mass,
                    initial: Some(diagonal.as_slice()?.to_vec()),
                });
            }
            let list = spec.cast::<PyList>().map_err(|_| {
                value_error("mass must be None, a 1-D float64 array, or a list of block dicts")
            })?;
            Some(StructuredBlockMass::new(parse_blocks(list)?).map_err(facade_error)?)
        }
    };
    match (blocks, refresh) {
        (None, Some(_)) => Err(value_error("refresh requires a structured mass")),
        (None, None) => Ok(Metric::Diagonal {
            adapt: adapt_mass,
            initial: None,
        }),
        (Some(mass), None) => Ok(Metric::Structured(mass)),
        (Some(mass), Some(refresh)) => Ok(Metric::StructuredRefresh {
            initial: mass,
            refresh: Box::new(PyRefresh {
                callable: refresh.callable,
            }),
            config: StructuredRefreshConfig::default().with_restart_policy(refresh.restart),
        }),
    }
}

fn parse_limits(cfg: &Bound<'_, PyDict>) -> PyResult<Limits> {
    let mut limits = Limits::new();
    if let Some(budget) = get::<usize>(cfg, "max_target_evaluations")? {
        nonzero(budget, "max_target_evaluations")?;
        limits = limits.max_target_evaluations(budget);
    }
    if let Some(false) = get::<bool>(cfg, "admit_worst_case")? {
        limits = limits.admit_conservative();
    }
    if let Some(stops) = get::<usize>(cfg, "max_depth_stop_limit")? {
        limits = limits.max_depth_stops(stops);
    }
    Ok(limits)
}

/// One configured run: the `owalnuts::sampler::Sampler` plus what the
/// zero-callback preflight needs to reproduce its admission decision.
struct Run {
    sampler: Sampler,
    structured: bool,
    max_target_evaluations: Option<usize>,
    admit_worst_case: bool,
}

/// Build the sampler from the Python configuration dict.
fn parse_run(cfg: &Bound<'_, PyDict>, refresh: Option<Refresh>) -> PyResult<Run> {
    let warmup: usize = required(cfg, "warmup")?;
    let draws: usize = required(cfg, "draws")?;
    let seed: u64 = required(cfg, "seed")?;
    let adapt: bool = get(cfg, "adapt")?.unwrap_or(true);
    let adapt_mass = adapt && get::<bool>(cfg, "adapt_mass")?.unwrap_or(true);
    let metric = parse_metric(cfg.get_item("mass")?, adapt_mass, refresh)?;
    let structured = matches!(
        metric,
        Metric::Structured(_) | Metric::StructuredRefresh { .. }
    );
    let max_target_evaluations: Option<usize> = get(cfg, "max_target_evaluations")?;
    let admit_worst_case: bool = get(cfg, "admit_worst_case")?.unwrap_or(true);
    let mut sampler = Sampler::new()
        .warmup(warmup)
        .draws(draws)
        .seed(seed)
        .tuning(parse_tuning(cfg)?)
        .adaptation(parse_adaptation(cfg)?)
        .metric(metric)
        .limits(parse_limits(cfg)?);
    if let Some(threads) = get::<usize>(cfg, "threads")? {
        sampler = sampler.threads(threads);
    }
    if let Some(cache) = get::<bool>(cfg, "cache_initial_evaluation")? {
        sampler = sampler.cache_initial_evaluation(cache);
    }
    Ok(Run {
        sampler,
        structured,
        max_target_evaluations,
        admit_worst_case,
    })
}

fn parse_starts(starts: PyReadonlyArray2<'_, f64>) -> PyResult<Vec<Vec<f64>>> {
    let view = starts.as_array();
    Ok(view.outer_iter().map(|row| row.to_vec()).collect())
}

// ── Execution ────────────────────────────────────────────────────────────

fn execute<T: Target>(target: &T, starts: &[Vec<f64>], run: &Run) -> Result<Posterior, Error> {
    run.sampler.run(target, starts)
}

/// Zero-callback admission report: transitions, the exact worst-case
/// evaluation count (`Sampler::worst_case_target_evaluations`), and the
/// ceiling the run is admitted against — the explicit budget, the worst case
/// itself under `admit_worst_case` (capped at the research maximum on the
/// structured paths, which have no budgeted admission variant), or the
/// conservative `walnutpie` ceiling.
fn preflight(chains: usize, transitions: usize, run: &Run) -> PyResult<(usize, usize, usize)> {
    let worst = run
        .sampler
        .worst_case_target_evaluations(chains)
        .map_err(facade_error)?;
    let ceiling = match (run.max_target_evaluations, run.admit_worst_case) {
        (Some(budget), _) => budget,
        (None, true) if run.structured => worst.min(RESEARCH_MAX_TARGET_EVALUATIONS),
        (None, true) => worst,
        (None, false) => CONSERVATIVE_MAX_TARGET_EVALUATIONS,
    };
    if worst > ceiling {
        return Err(PyRuntimeError::new_err(format!(
            "owalnuts ResourceLimit: worst-case target evaluations ({worst}) exceed the \
             admission ceiling ({ceiling}), a resource limit"
        )));
    }
    let total_transitions = transitions
        .checked_mul(chains)
        .ok_or_else(|| value_error("transition count overflows"))?;
    Ok((total_transitions, worst, ceiling))
}

fn stop_code(stop: StopReason) -> u8 {
    match stop {
        StopReason::OuterUTurn => 0,
        StopReason::RecursiveUTurn => 1,
        StopReason::MaximumDepth => 2,
        StopReason::RefinementExhausted => 3,
        StopReason::ReverseCoarserAccepted => 4,
        StopReason::InvalidEvaluation => 5,
        _ => 255,
    }
}

fn work_totals<'py>(py: Python<'py>, totals: &WorkTotals) -> PyResult<Bound<'py, PyDict>> {
    let d = PyDict::new(py);
    d.set_item("transitions", totals.transitions())?;
    d.set_item("target_calls_total", totals.target_calls_total())?;
    d.set_item("target_calls_forward", totals.target_calls_forward())?;
    d.set_item("target_calls_reverse", totals.target_calls_reverse())?;
    d.set_item("leaves_attempted", totals.leaves_attempted())?;
    d.set_item("leaves_built", totals.leaves_built())?;
    d.set_item(
        "forward_micro_steps_executed",
        totals.forward_micro_steps_executed(),
    )?;
    d.set_item(
        "reverse_micro_steps_executed",
        totals.reverse_micro_steps_executed(),
    )?;
    d.set_item("maximum_depth_stops", totals.maximum_depth_stops())?;
    d.set_item("divergences", totals.divergences())?;
    d.set_item(
        "invalid_evaluation_stops",
        totals.invalid_evaluation_stops(),
    )?;
    d.set_item(
        "refinement_exhaustion_stops",
        totals.refinement_exhaustion_stops(),
    )?;
    d.set_item("reverse_coarser_stops", totals.reverse_coarser_stops())?;
    d.set_item(
        "recoverable_target_failures",
        totals.recoverable_target_failures(),
    )?;
    d.set_item(
        "zero_density_evaluations",
        totals.zero_density_evaluations(),
    )?;
    Ok(d)
}

fn chain_dict<'py>(py: Python<'py>, chain: &ChainOutput) -> PyResult<Bound<'py, PyDict>> {
    let d = PyDict::new(py);
    let diagnostics = chain.diagnostics();
    let n = diagnostics.len();
    let mut depth = Vec::with_capacity(n);
    let mut stop = Vec::with_capacity(n);
    let mut calls = Vec::with_capacity(n);
    let mut divergent = Vec::with_capacity(n);
    let mut energy_error = Vec::with_capacity(n);
    let mut leaves_built = Vec::with_capacity(n);
    let mut level = Vec::with_capacity(n);
    let mut zero_density = Vec::with_capacity(n);
    let mut macro_length = Vec::with_capacity(n);
    for t in diagnostics {
        depth.push(t.depth() as u32);
        stop.push(stop_code(t.stop()));
        calls.push(t.target_evaluations() as u32);
        divergent.push(t.divergent());
        energy_error.push(t.maximum_absolute_energy_error());
        leaves_built.push(t.leaves_built() as u32);
        level.push(
            t.selected_refinement_level()
                .map(|l| l as i32)
                .unwrap_or(-1),
        );
        zero_density.push(t.zero_density_evaluations() as u32);
        macro_length.push(t.trajectory_macro_length());
    }
    d.set_item("depth", depth.into_pyarray(py))?;
    d.set_item("stop", stop.into_pyarray(py))?;
    d.set_item("target_evaluations", calls.into_pyarray(py))?;
    d.set_item("divergent", divergent.into_pyarray(py))?;
    d.set_item("max_abs_energy_error", energy_error.into_pyarray(py))?;
    d.set_item("leaves_built", leaves_built.into_pyarray(py))?;
    d.set_item("selected_refinement_level", level.into_pyarray(py))?;
    d.set_item("zero_density_evaluations", zero_density.into_pyarray(py))?;
    d.set_item("trajectory_macro_length", macro_length.into_pyarray(py))?;

    let telemetry = chain.telemetry();
    d.set_item("work_retained", work_totals(py, telemetry.retained())?)?;
    d.set_item("work_discarded", work_totals(py, telemetry.discarded())?)?;
    d.set_item("work_total", work_totals(py, telemetry.total())?)?;

    let paper = PyList::empty(py);
    for update in telemetry.paper_adaptation_updates() {
        let u = PyDict::new(py);
        u.set_item("transition", update.transition())?;
        u.set_item("window_index", update.window_index())?;
        u.set_item("orbits", update.orbits())?;
        u.set_item("max_error_before", update.max_error_before())?;
        u.set_item("max_error_after", update.max_error_after())?;
        u.set_item("step_before", update.step_before())?;
        u.set_item("step_after", update.step_after())?;
        u.set_item("unrefined_fraction_mean", update.unrefined_fraction_mean())?;
        u.set_item("inflation_quantile", update.inflation_quantile())?;
        u.set_item("outcome", format!("{:?}", update.outcome()))?;
        paper.append(u)?;
    }
    d.set_item("paper_adaptation_updates", paper)?;

    let meta = chain.metadata();
    let m = PyDict::new(py);
    m.set_item("effective_seed", meta.effective_seed())?;
    m.set_item("final_step_size", meta.tuning().step_size())?;
    m.set_item("final_max_error", meta.tuning().max_error())?;
    m.set_item("initial_step_size", meta.initial_tuning().step_size())?;
    m.set_item("max_depth", meta.max_depth())?;
    m.set_item("max_refinement_levels", meta.max_refinement_levels())?;
    m.set_item("min_micro_steps", meta.min_micro_steps())?;
    m.set_item(
        "mass_diagonal",
        meta.mass_diagonal().to_vec().into_pyarray(py),
    )?;
    m.set_item("thread_count", meta.thread_count())?;
    d.set_item("metadata", m)?;
    Ok(d)
}

fn output_dict<'py>(
    py: Python<'py>,
    output: &MultiChainOutput,
    wall_seconds: f64,
    calls: usize,
    recoverable: usize,
    attached_seconds: f64,
) -> PyResult<Bound<'py, PyDict>> {
    let chains = output.chains();
    let chain_count = chains.len();
    let retained = chains.first().map(|c| c.retained()).unwrap_or(0);
    let dimension = chains.first().map(|c| c.dimension()).unwrap_or(0);
    let mut flat = Vec::with_capacity(chain_count * retained * dimension);
    for chain in chains {
        flat.extend_from_slice(chain.samples());
    }
    let samples = flat
        .into_pyarray(py)
        .reshape([chain_count, retained, dimension])?;
    let d = PyDict::new(py);
    d.set_item("samples", samples)?;
    let per_chain = PyList::empty(py);
    for chain in chains {
        per_chain.append(chain_dict(py, chain)?)?;
    }
    d.set_item("chains", per_chain)?;
    d.set_item("algorithm_revision", output.algorithm_revision())?;
    d.set_item("paper_adaptation_revision", PAPER_ADAPTATION_REVISION)?;
    d.set_item("base_seed", output.base_seed())?;
    d.set_item("wall_seconds", wall_seconds)?;
    d.set_item("target_calls", calls)?;
    d.set_item("target_recoverable_failures", recoverable)?;
    d.set_item("target_attached_seconds", attached_seconds)?;
    Ok(d)
}

// ── Python API ───────────────────────────────────────────────────────────

/// Sample a Python callable target `f(q) -> (log_density, gradient)`.
#[pyfunction]
#[pyo3(signature = (target, starts, config, nonfinite="zero_density", refresh=None, refresh_restart="continue"))]
fn sample_callable<'py>(
    py: Python<'py>,
    target: Py<PyAny>,
    starts: PyReadonlyArray2<'py, f64>,
    config: &Bound<'py, PyDict>,
    nonfinite: &str,
    refresh: Option<Py<PyAny>>,
    refresh_restart: &str,
) -> PyResult<Bound<'py, PyDict>> {
    let starts = parse_starts(starts)?;
    let dimension = starts
        .first()
        .map(Vec::len)
        .ok_or_else(|| value_error("starts is empty"))?;
    let refreshed = refresh.is_some();
    let run = parse_run(config, parse_refresh(refresh, refresh_restart)?)?;
    let py_target = PyTarget {
        callable: target,
        dimension,
        policy: NonFinitePolicy::parse(nonfinite)?,
        calls: AtomicUsize::new(0),
        recoverable: AtomicUsize::new(0),
        attached_nanos: AtomicU64::new(0),
        last_fatal: Mutex::new(None),
    };
    let started = Instant::now();
    let output = py
        .detach(|| execute(&py_target, &starts, &run))
        .map_err(|e| py_target.fatal_error(e))?;
    let wall = started.elapsed().as_secs_f64();
    let dict = output_dict(
        py,
        output.inner(),
        wall,
        py_target.calls.load(Ordering::Relaxed),
        py_target.recoverable.load(Ordering::Relaxed),
        py_target.attached_nanos.load(Ordering::Relaxed) as f64 * 1e-9,
    )?;
    if refreshed {
        let updates = PyList::empty(py);
        for (chain, rows) in output.metric_updates().iter().enumerate() {
            for u in rows {
                let row = PyDict::new(py);
                row.set_item("chain", chain)?;
                row.set_item("window", u.window_index())?;
                row.set_item("transition", u.transition())?;
                row.set_item("outcome", format!("{:?}", u.outcome()))?;
                row.set_item("step_before", u.step_before())?;
                row.set_item("step_after_search", u.step_after_search())?;
                row.set_item("step_after_restart", u.step_after_restart())?;
                updates.append(row)?;
            }
        }
        dict.set_item("refresh_updates", updates)?;
    }
    Ok(dict)
}

/// Zero-callback admission preflight for a callable target of `dimension`.
#[pyfunction]
fn preflight_callable<'py>(
    py: Python<'py>,
    starts: PyReadonlyArray2<'py, f64>,
    config: &Bound<'py, PyDict>,
) -> PyResult<Bound<'py, PyDict>> {
    let starts = parse_starts(starts)?;
    let dimension = starts
        .first()
        .map(Vec::len)
        .ok_or_else(|| value_error("starts is empty"))?;
    nonzero(dimension, "dimension")?;
    let run = parse_run(config, None)?;
    let warmup: usize = required(config, "warmup")?;
    let draws: usize = required(config, "draws")?;
    let transitions = warmup
        .checked_add(draws)
        .ok_or_else(|| value_error("transition count overflows"))?;
    let (transitions, worst, ceiling) = preflight(starts.len(), transitions, &run)?;
    let d = PyDict::new(py);
    d.set_item("total_transitions", transitions)?;
    d.set_item("worst_case_target_evaluations", worst)?;
    d.set_item("admission_ceiling", ceiling)?;
    Ok(d)
}

/// Sample the built-in native noncentered Eight Schools target.
#[pyfunction]
fn sample_eight_schools<'py>(
    py: Python<'py>,
    y: PyReadonlyArray1<'py, f64>,
    se: PyReadonlyArray1<'py, f64>,
    starts: PyReadonlyArray2<'py, f64>,
    config: &Bound<'py, PyDict>,
) -> PyResult<Bound<'py, PyDict>> {
    let target = EightSchools {
        y: y.as_slice()?.to_vec(),
        se: se.as_slice()?.to_vec(),
        calls: AtomicUsize::new(0),
    };
    let starts = parse_starts(starts)?;
    let run = parse_run(config, None)?;
    let started = Instant::now();
    let output = py
        .detach(|| execute(&target, &starts, &run))
        .map_err(facade_error)?;
    let wall = started.elapsed().as_secs_f64();
    output_dict(
        py,
        output.inner(),
        wall,
        target.calls.load(Ordering::Relaxed),
        0,
        0.0,
    )
}

/// Sample the built-in native Gaussian local-level path target.
#[pyfunction]
#[pyo3(signature = (y, r, starts, config, m0=0.0, tau0=1.0, mu=0.01, sigma_x=0.08))]
#[allow(clippy::too_many_arguments)]
fn sample_local_level<'py>(
    py: Python<'py>,
    y: PyReadonlyArray1<'py, f64>,
    r: PyReadonlyArray1<'py, f64>,
    starts: PyReadonlyArray2<'py, f64>,
    config: &Bound<'py, PyDict>,
    m0: f64,
    tau0: f64,
    mu: f64,
    sigma_x: f64,
) -> PyResult<Bound<'py, PyDict>> {
    let target = LocalLevel {
        y: y.as_slice()?.to_vec(),
        r: r.as_slice()?.to_vec(),
        m0,
        tau0,
        mu,
        sigma_x,
        calls: AtomicUsize::new(0),
    };
    let starts = parse_starts(starts)?;
    let run = parse_run(config, None)?;
    let started = Instant::now();
    let output = py
        .detach(|| execute(&target, &starts, &run))
        .map_err(facade_error)?;
    let wall = started.elapsed().as_secs_f64();
    output_dict(
        py,
        output.inner(),
        wall,
        target.calls.load(Ordering::Relaxed),
        0,
        0.0,
    )
}

/// Sample a raw C-ABI callback given as an integer function address.
///
/// The callee must have the exact `RawTargetFn` ABI — in numba terms
/// `float64(intp, CPointer(float64), CPointer(float64), voidptr)` — be
/// thread-safe, reentrant, deterministic, and outlive the call (the Python
/// side keeps the compiled object alive). It runs with no interpreter
/// attachment, so `threads > 1` gives real parallel chains.
#[pyfunction]
#[pyo3(signature = (address, dimension, starts, config, user_data=0, parameter_names=None))]
fn sample_cfunc<'py>(
    py: Python<'py>,
    address: usize,
    dimension: usize,
    starts: PyReadonlyArray2<'py, f64>,
    config: &Bound<'py, PyDict>,
    user_data: usize,
    parameter_names: Option<Vec<String>>,
) -> PyResult<Bound<'py, PyDict>> {
    if address == 0 {
        return Err(value_error("address must be a nonzero cfunc address"));
    }
    let starts = parse_starts(starts)?;
    if starts.first().map(Vec::len) != Some(dimension) {
        return Err(value_error(format!(
            "starts must be (chains, {dimension}) to match the cfunc dimension"
        )));
    }
    let run = parse_run(config, None)?;
    // SAFETY: the caller passes the address of a compiled callback with the
    // documented `RawTargetFn` ABI and keeps it alive for the whole call; the
    // remaining contract is asserted through `RawTarget::new` below.
    let function: RawTargetFn = unsafe { std::mem::transmute::<usize, RawTargetFn>(address) };
    // SAFETY: thread-safety, reentrancy, determinism, buffer discipline, and
    // `user_data` validity are the documented `from_cfunc` contract.
    let mut target = unsafe {
        RawTarget::new(
            nonzero(dimension, "dimension")?,
            function,
            user_data as *mut core::ffi::c_void,
        )
    };
    if let Some(names) = parameter_names {
        target = target.with_parameter_names(names).map_err(facade_error)?;
    }
    let started = Instant::now();
    let output = py
        .detach(|| execute(&target, &starts, &run))
        .map_err(facade_error)?;
    let wall = started.elapsed().as_secs_f64();
    let calls = output.total_target_calls();
    output_dict(py, output.inner(), wall, calls, 0, 0.0)
}

/// Standard Gaussian reference target for the defaults-parity test: the log
/// density is accumulated as `s += x * x` in index order (no fused
/// multiply-add, no pairwise summation) so that a Python target written the
/// same way returns bit-identical values.
struct StandardGaussian(usize);

impl Target for StandardGaussian {
    fn dimension(&self) -> usize {
        self.0
    }
    fn log_density_gradient(&self, q: &[f64], g: &mut [f64]) -> Result<f64, TargetError> {
        let mut sum = 0.0;
        for (x, gradient) in q.iter().zip(g.iter_mut()) {
            *gradient = -x;
            sum += x * x;
        }
        Ok(-0.5 * sum)
    }
}

/// Draws of `owalnuts::sampler::Sampler::new().warmup(..).draws(..).seed(..)`
/// (every other setting at the sampler default) on the standard Gaussian,
/// as a `(chains, draws, dim)` array. The Python test suite checks that
/// `owalnuts.sample` with explicit arguments equal to `DEFAULTS` reproduces
/// these draws bit for bit.
#[pyfunction]
fn reference_gaussian_sampler_run<'py>(
    py: Python<'py>,
    starts: PyReadonlyArray2<'py, f64>,
    warmup: usize,
    draws: usize,
    seed: u64,
) -> PyResult<Bound<'py, PyArray3<f64>>> {
    let starts = parse_starts(starts)?;
    let dimension = starts
        .first()
        .map(Vec::len)
        .ok_or_else(|| value_error("starts is empty"))?;
    let target = StandardGaussian(dimension);
    let sampler = Sampler::new().warmup(warmup).draws(draws).seed(seed);
    let posterior = py
        .detach(|| sampler.run(&target, &starts))
        .map_err(facade_error)?;
    let chains = posterior.chain_count();
    let retained = posterior.draws_per_chain();
    let mut flat = Vec::with_capacity(chains * retained * dimension);
    for chain in posterior.chains() {
        flat.extend_from_slice(chain.samples());
    }
    flat.into_pyarray(py).reshape([chains, retained, dimension])
}

/// The `owalnuts::sampler` defaults the package inherits, read from the Rust
/// values (not restated): `Tuning::default()` through its validated kernel
/// tuning, the sampler's warmup exhaustion rule and metric regularisation,
/// `Adaptation::default()`, `Metric::default()`, `Init::default()`, and the
/// `Sampler` / `Limits` defaults (read from their `Debug` output, which is
/// the only public view of those two flags).
fn defaults<'py>(py: Python<'py>) -> PyResult<Bound<'py, PyDict>> {
    let tuning = Tuning::default().to_kernel().map_err(facade_error)?;
    let d = PyDict::new(py);
    d.set_item("algorithm_revision", ALGORITHM_REVISION)?;
    d.set_item("paper_adaptation_revision", PAPER_ADAPTATION_REVISION)?;
    d.set_item("step_size", tuning.step_size())?;
    d.set_item("max_depth", tuning.max_depth())?;
    d.set_item("min_micro_steps", tuning.min_micro_steps())?;
    d.set_item("max_refinement_levels", tuning.max_refinement_levels())?;
    d.set_item("max_error", tuning.max_error())?;
    d.set_item("divergence_threshold", tuning.divergence_threshold())?;
    d.set_item("u_turn_rule", u_turn_name(tuning.options().u_turn))?;
    d.set_item(
        "exhaustion_rule",
        exhaustion_name(tuning.options().exhaustion),
    )?;
    d.set_item(
        "warmup_exhaustion_rule",
        exhaustion_name(DEFAULT_WARMUP_EXHAUSTION),
    )?;
    d.set_item(
        "metric_regularization",
        regularization_name(DEFAULT_METRIC_REGULARIZATION),
    )?;
    d.set_item("target_accept", default_target_accept()?)?;
    d.set_item(
        "adapt_mass",
        matches!(Metric::default(), Metric::Diagonal { adapt: true, .. }),
    )?;
    match Init::default() {
        Init::Uniform {
            radius,
            max_attempts,
        } => {
            d.set_item("init_radius", radius)?;
            d.set_item("init_max_attempts", max_attempts)?;
        }
        other => {
            return Err(PyRuntimeError::new_err(format!(
                "owalnuts sampler default init is not uniform: {other:?}"
            )));
        }
    }
    let sampler = format!("{:?}", Sampler::default());
    d.set_item(
        "cache_initial_evaluation",
        sampler.contains("cache_initial_evaluation: true"),
    )?;
    let limits = format!("{:?}", Limits::default());
    d.set_item(
        "admit_worst_case",
        limits.contains("admit_worst_case: true"),
    )?;
    Ok(d)
}

/// Evaluate the built-in Eight Schools density once (for adapter tests).
#[pyfunction]
fn eight_schools_logp_grad<'py>(
    py: Python<'py>,
    y: PyReadonlyArray1<'py, f64>,
    se: PyReadonlyArray1<'py, f64>,
    q: PyReadonlyArray1<'py, f64>,
) -> PyResult<(f64, Bound<'py, PyArray1<f64>>)> {
    let target = EightSchools {
        y: y.as_slice()?.to_vec(),
        se: se.as_slice()?.to_vec(),
        calls: AtomicUsize::new(0),
    };
    let mut g = vec![0.0; target.dimension()];
    let v = target
        .log_density_gradient(q.as_slice()?, &mut g)
        .map_err(|e| PyRuntimeError::new_err(e.message().to_string()))?;
    Ok((v, g.into_pyarray(py)))
}

/// Uniform starts with retries (`owalnuts::sampler::uniform_starts`) for a
/// callable target: Stan's uniform(-radius, radius) rule, redrawn until the
/// log density and gradient are finite, deterministic given `seed`.
#[pyfunction]
#[allow(clippy::too_many_arguments)]
#[pyo3(signature = (target, dimension, chains, seed, radius=2.0, max_attempts=100, nonfinite="zero_density"))]
fn uniform_starts_callable<'py>(
    py: Python<'py>,
    target: Py<PyAny>,
    dimension: usize,
    chains: usize,
    seed: u64,
    radius: f64,
    max_attempts: usize,
    nonfinite: &str,
) -> PyResult<Bound<'py, PyArray2<f64>>> {
    let py_target = PyTarget {
        callable: target,
        dimension,
        policy: NonFinitePolicy::parse(nonfinite)?,
        calls: AtomicUsize::new(0),
        recoverable: AtomicUsize::new(0),
        attached_nanos: AtomicU64::new(0),
        last_fatal: Mutex::new(None),
    };
    let starts = py
        .detach(|| uniform_starts(&py_target, chains, seed, radius, max_attempts))
        .map_err(|e| py_target.fatal_error(e))?;
    starts_array(py, starts, dimension)
}

/// Uniform starts with retries for a GIL-free `cfunc` target.
#[pyfunction]
#[allow(clippy::too_many_arguments)]
#[pyo3(signature = (address, dimension, chains, seed, radius=2.0, max_attempts=100, user_data=0))]
fn uniform_starts_cfunc<'py>(
    py: Python<'py>,
    address: usize,
    dimension: usize,
    chains: usize,
    seed: u64,
    radius: f64,
    max_attempts: usize,
    user_data: usize,
) -> PyResult<Bound<'py, PyArray2<f64>>> {
    if address == 0 {
        return Err(value_error("address must be a nonzero cfunc address"));
    }
    // SAFETY: see `sample_cfunc`; the same `from_cfunc` contract applies.
    let function: RawTargetFn = unsafe { std::mem::transmute::<usize, RawTargetFn>(address) };
    // SAFETY: as in `sample_cfunc`.
    let target = unsafe {
        RawTarget::new(
            nonzero(dimension, "dimension")?,
            function,
            user_data as *mut core::ffi::c_void,
        )
    };
    let starts = py
        .detach(|| uniform_starts(&target, chains, seed, radius, max_attempts))
        .map_err(facade_error)?;
    starts_array(py, starts, dimension)
}

fn starts_array<'py>(
    py: Python<'py>,
    starts: Vec<Vec<f64>>,
    dimension: usize,
) -> PyResult<Bound<'py, PyArray2<f64>>> {
    let chains = starts.len();
    let flat: Vec<f64> = starts.into_iter().flatten().collect();
    flat.into_pyarray(py).reshape([chains, dimension])
}

/// Per-parameter summary rows (`owalnuts::diagnostics::ParameterSummary`)
/// for a `(chains, draws, dim)` array of retained draws.
#[pyfunction]
#[pyo3(signature = (samples, names=None))]
fn summary<'py>(
    py: Python<'py>,
    samples: PyReadonlyArray3<'py, f64>,
    names: Option<Vec<String>>,
) -> PyResult<Bound<'py, PyList>> {
    let view = samples.as_array();
    let (chains, draws, dimension) = view.dim();
    if chains == 0 || draws == 0 {
        return Err(value_error(
            "samples must have at least one chain and one draw",
        ));
    }
    let names = match names {
        Some(names) if names.len() != dimension => {
            return Err(value_error(format!(
                "names must have exactly {dimension} entries (got {})",
                names.len()
            )));
        }
        Some(names) => names,
        None => owalnuts::diagnostics::default_parameter_names(dimension),
    };
    let rows: Vec<ParameterSummary> = py.detach(|| {
        names
            .into_iter()
            .enumerate()
            .map(|(index, name)| {
                let columns: Vec<Vec<f64>> = (0..chains)
                    .map(|chain| (0..draws).map(|draw| view[[chain, draw, index]]).collect())
                    .collect();
                let views: Vec<&[f64]> = columns.iter().map(Vec::as_slice).collect();
                ParameterSummary::compute(name, &views)
            })
            .collect()
    });
    let out = PyList::empty(py);
    for row in rows {
        let d = PyDict::new(py);
        d.set_item("name", &row.name)?;
        d.set_item("mean", row.mean)?;
        d.set_item("sd", row.sd)?;
        d.set_item("mcse_mean", row.mcse_mean)?;
        d.set_item("q5", row.quantiles[0])?;
        d.set_item("q50", row.quantiles[1])?;
        d.set_item("q95", row.quantiles[2])?;
        d.set_item("ess_bulk", row.ess_bulk)?;
        d.set_item("ess_tail", row.ess_tail)?;
        d.set_item("rhat", row.rhat)?;
        out.append(d)?;
    }
    Ok(out)
}

#[pymodule]
fn _owalnuts(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add("ALGORITHM_REVISION", ALGORITHM_REVISION)?;
    m.add("PAPER_ADAPTATION_REVISION", PAPER_ADAPTATION_REVISION)?;
    m.add("DEFAULTS", defaults(m.py())?)?;
    m.add(
        "STOP_CODES",
        vec![
            "outer_uturn",
            "recursive_uturn",
            "maximum_depth",
            "refinement_exhausted",
            "reverse_coarser_accepted",
            "invalid_evaluation",
        ],
    )?;
    m.add(
        "RAW_CFUNC_SIGNATURE",
        "float64(intp, CPointer(float64), CPointer(float64), voidptr)",
    )?;
    m.add_function(wrap_pyfunction!(sample_cfunc, m)?)?;
    m.add_function(wrap_pyfunction!(sample_callable, m)?)?;
    m.add_function(wrap_pyfunction!(preflight_callable, m)?)?;
    m.add_function(wrap_pyfunction!(sample_eight_schools, m)?)?;
    m.add_function(wrap_pyfunction!(sample_local_level, m)?)?;
    m.add_function(wrap_pyfunction!(eight_schools_logp_grad, m)?)?;
    m.add_function(wrap_pyfunction!(uniform_starts_callable, m)?)?;
    m.add_function(wrap_pyfunction!(uniform_starts_cfunc, m)?)?;
    m.add_function(wrap_pyfunction!(summary, m)?)?;
    m.add_function(wrap_pyfunction!(reference_gaussian_sampler_run, m)?)?;
    Ok(())
}
