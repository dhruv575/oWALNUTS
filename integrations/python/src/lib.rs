//! Thin PyO3 wrapper over the public `owalnuts::walnutpie` facade.
//!
//! Every sampling call goes through the public facade; nothing here touches
//! kernel internals. The Python thread releases the GIL for the duration of a
//! run (`Python::detach`), and each target callback re-attaches from whichever
//! Rust worker thread executes it, so Python targets are serialised by the GIL
//! while native built-in targets run fully parallel.

use std::num::NonZeroUsize;
use std::sync::Mutex;
use std::sync::atomic::{AtomicU64, AtomicUsize, Ordering};
use std::time::Instant;

use numpy::{
    IntoPyArray, PyArray1, PyArray2, PyArrayMethods, PyReadonlyArray1, PyReadonlyArray2,
    PyReadonlyArray3,
};
use owalnuts::diagnostics::ParameterSummary;
use owalnuts::sampler::uniform_starts;
use owalnuts::walnutpie::{
    ALGORITHM_REVISION, ChainOutput, DiagonalMass, Error, KernelTuning, MultiChainOutput,
    PAPER_ADAPTATION_REVISION, PaperAdaptationConfig, PaperRestartPolicy, PaperStepStatistic,
    RawTarget, RawTargetFn, RunConfig, RunControl, StopReason, StructuredBlockMass,
    StructuredCovarianceBlock, StructuredMetricRefresh, StructuredRefreshConfig,
    StructuredRefreshRestartPolicy, Target, TargetError, TargetEvaluationAdmissionLimit,
    TargetEvaluationBudget, WarmupConfig, WindowSummary, WorkTotals, preflight_chains,
    preflight_chains_structured, preflight_chains_with_target_budget, sample_chains,
    sample_chains_structured, sample_chains_structured_refresh, sample_chains_with_target_budget,
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

enum Mass {
    Diagonal(DiagonalMass),
    Structured(StructuredBlockMass),
}

struct Run {
    config: RunConfig,
    mass: Mass,
    threads: NonZeroUsize,
    budget: Option<NonZeroUsize>,
}

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

fn parse_mass(py: Python<'_>, dimension: usize, spec: Option<Bound<'_, PyAny>>) -> PyResult<Mass> {
    let Some(spec) = spec else {
        return Ok(Mass::Diagonal(DiagonalMass::identity(nonzero(
            dimension,
            "dimension",
        )?)));
    };
    if spec.is_none() {
        return Ok(Mass::Diagonal(DiagonalMass::identity(nonzero(
            dimension,
            "dimension",
        )?)));
    }
    if let Ok(diagonal) = spec.extract::<PyReadonlyArray1<'_, f64>>() {
        let diagonal = diagonal.as_slice()?.to_vec();
        return DiagonalMass::from_diagonal(diagonal)
            .map(Mass::Diagonal)
            .map_err(facade_error);
    }
    let blocks = spec.cast::<PyList>().map_err(|_| {
        value_error("mass must be None, a 1-D float64 array, or a list of block dicts")
    })?;
    let parsed = parse_blocks(blocks)?;
    let _ = py;
    StructuredBlockMass::new(parsed)
        .map(Mass::Structured)
        .map_err(facade_error)
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

fn parse_run(
    py: Python<'_>,
    dimension: usize,
    chains: usize,
    cfg: &Bound<'_, PyDict>,
    refresh_active: bool,
) -> PyResult<Run> {
    let discarded: usize = required(cfg, "warmup")?;
    let retained: usize = required(cfg, "draws")?;
    let seed: u64 = required(cfg, "seed")?;
    let threads: usize = get(cfg, "threads")?.unwrap_or(1);
    // Defaults match `owalnuts::sampler::Tuning::default()`.
    let step_size: f64 = get(cfg, "step_size")?.unwrap_or(0.5);
    let max_depth: usize = get(cfg, "max_depth")?.unwrap_or(10);
    let min_micro_steps: usize = get(cfg, "min_micro_steps")?.unwrap_or(1);
    let max_refinement_levels: usize = get(cfg, "max_refinement_levels")?.unwrap_or(4);
    let max_error: f64 = get(cfg, "max_error")?.unwrap_or(1.0);
    let divergence_threshold: f64 = get(cfg, "divergence_threshold")?.unwrap_or(1000.0);
    let max_depth_stop_limit: Option<usize> = get(cfg, "max_depth_stop_limit")?;
    let budget: Option<NonZeroUsize> = match get::<usize>(cfg, "max_target_evaluations")? {
        Some(b) => Some(nonzero(b, "max_target_evaluations")?),
        None => None,
    };

    let tuning = KernelTuning::new(
        step_size,
        nonzero(max_depth, "max_depth")?,
        nonzero(min_micro_steps, "min_micro_steps")?,
        nonzero(max_refinement_levels, "max_refinement_levels")?,
        max_error,
    )
    .and_then(|t| t.with_divergence_threshold(divergence_threshold))
    .map_err(facade_error)?;

    let mut config =
        RunConfig::new(discarded, nonzero(retained, "draws")?, seed).with_tuning(tuning);
    if let Some(limit) = max_depth_stop_limit {
        config = config.with_maximum_depth_stop_limit(limit);
    }
    let mass = parse_mass(py, dimension, cfg.get_item("mass")?)?;

    // `admit_worst_case` (default) mirrors `sampler::Limits::admit_worst_case`:
    // when the conservative default admission ceiling would reject the run,
    // admit it with its exact worst-case evaluation count instead. Needed
    // at the sampler defaults (depth 10, four refinement levels) for four
    // chains of a few thousand transitions.
    let admit_worst_case: bool = get(cfg, "admit_worst_case")?.unwrap_or(true);
    let chains = nonzero(chains, "chains")?;
    let budget = match budget {
        Some(budget) => Some(budget),
        None if admit_worst_case => {
            let worst = config
                .worst_case_target_evaluations(chains)
                .map_err(facade_error)?;
            (worst > owalnuts::walnutpie::CONSERVATIVE_MAX_TARGET_EVALUATIONS)
                .then(|| nonzero(worst, "worst_case_target_evaluations"))
                .transpose()?
        }
        None => None,
    };
    if let (Some(budget), Mass::Structured(_)) = (budget, &mass) {
        // Structured-mass runs have no budgeted entry point: raise the
        // constructor admission ceiling to the budget instead (bounded by
        // the facade's hard research maximum). Diagonal runs go through the
        // budgeted entry point with an explicit admission limit and must
        // not also carry a research limit.
        let ceiling = budget
            .get()
            .min(owalnuts::walnutpie::RESEARCH_MAX_TARGET_EVALUATIONS);
        let limit = owalnuts::walnutpie::ResearchTargetEvaluationLimit::new(
            NonZeroUsize::new(ceiling).expect("nonzero ceiling"),
        )
        .map_err(facade_error)?;
        config = config.with_research_target_evaluation_limit(limit);
    }

    let adapt: bool = get(cfg, "adapt")?.unwrap_or(true);
    if adapt {
        let target_accept: f64 = get(cfg, "target_accept")?.unwrap_or(0.8);
        let adapt_step: bool = get(cfg, "adapt_step_size")?.unwrap_or(true);
        let adapt_mass_requested: bool = get(cfg, "adapt_mass")?.unwrap_or(true);
        let adapt_mass =
            adapt_mass_requested && (matches!(mass, Mass::Diagonal(_)) || refresh_active);
        let mut warmup = WarmupConfig::new(target_accept)
            .map_err(facade_error)?
            .with_step_size_adaptation(adapt_step)
            .with_mass_adaptation(adapt_mass);
        if let Some(paper) = cfg.get_item("paper_adaptation")? {
            if !paper.is_none() {
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
                    paper_config =
                        paper_config.with_minimum_orbits(nonzero(min_orbits, "minimum_orbits")?);
                }
                if let Some(statistic) = get::<String>(paper, "step_statistic")? {
                    paper_config = paper_config.with_step_statistic(match statistic.as_str() {
                        "per_transition" => PaperStepStatistic::PerTransition,
                        "cumulative" => PaperStepStatistic::Cumulative,
                        other => {
                            return Err(value_error(format!("unknown step_statistic {other:?}")));
                        }
                    });
                }
                if let Some(policy) = get::<String>(paper, "restart_policy")? {
                    paper_config = paper_config.with_restart_policy(match policy.as_str() {
                        "restart" => PaperRestartPolicy::RestartOnLocalErrorInstall,
                        "continue" => PaperRestartPolicy::ContinueThroughLocalErrorInstall,
                        other => {
                            return Err(value_error(format!("unknown restart_policy {other:?}")));
                        }
                    });
                }
                warmup = warmup.with_paper_adaptation(paper_config);
            }
        }
        config = config.with_warmup(warmup);
    }

    Ok(Run {
        config,
        mass,
        threads: nonzero(threads, "threads")?,
        budget,
    })
}

fn parse_starts(starts: PyReadonlyArray2<'_, f64>) -> PyResult<Vec<Vec<f64>>> {
    let view = starts.as_array();
    Ok(view.outer_iter().map(|row| row.to_vec()).collect())
}

// ── Execution ────────────────────────────────────────────────────────────

/// Admission ceiling used with an explicit runtime budget: the exact shared
/// callback budget is authoritative, so the conservative constructor bound is
/// only required to be representable.
const BUDGETED_ADMISSION_LIMIT: usize = 1 << 50;

fn admission() -> TargetEvaluationAdmissionLimit {
    TargetEvaluationAdmissionLimit::new(
        NonZeroUsize::new(BUDGETED_ADMISSION_LIMIT).expect("nonzero"),
    )
}

fn execute<T: Target>(
    target: &T,
    starts: &[Vec<f64>],
    run: &Run,
) -> Result<MultiChainOutput, Error> {
    match (&run.mass, run.budget) {
        (Mass::Diagonal(mass), None) => {
            sample_chains(target, starts, mass, &run.config, run.threads)
        }
        (Mass::Diagonal(mass), Some(budget)) => sample_chains_with_target_budget(
            target,
            starts,
            mass,
            &run.config,
            run.threads,
            admission(),
            &TargetEvaluationBudget::new(budget),
        ),
        (Mass::Structured(mass), _) => {
            sample_chains_structured(target, starts, mass, &run.config, run.threads)
        }
    }
}

fn preflight<T: Target>(
    target: &T,
    starts: &[Vec<f64>],
    run: &Run,
) -> Result<(usize, usize, usize), Error> {
    let report = match (&run.mass, run.budget) {
        (Mass::Diagonal(mass), None) => preflight_chains(target, starts, mass, &run.config)?,
        (Mass::Diagonal(mass), Some(budget)) => preflight_chains_with_target_budget(
            target,
            starts,
            mass,
            &run.config,
            admission(),
            &TargetEvaluationBudget::new(budget),
        )?,
        (Mass::Structured(mass), _) => {
            preflight_chains_structured(target, starts, mass, &run.config)?
        }
    };
    Ok((
        report.total_transitions(),
        report.worst_case_target_evaluations(),
        report.admission_ceiling(),
    ))
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
    let run = parse_run(py, dimension, starts.len(), config, refresh.is_some())?;
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
    if let Some(callback) = refresh {
        let Mass::Structured(mass) = &run.mass else {
            return Err(value_error("refresh requires a structured mass"));
        };
        let policy = match refresh_restart {
            "continue" => StructuredRefreshRestartPolicy::ContinueDualAveraging,
            "restart" => StructuredRefreshRestartPolicy::RestartDualAveraging,
            other => return Err(value_error(format!("unknown refresh_restart {other:?}"))),
        };
        let adapter = PyRefresh { callable: callback };
        let refresh_config = StructuredRefreshConfig::default().with_restart_policy(policy);
        let control = RunControl::new();
        let output = py
            .detach(|| {
                sample_chains_structured_refresh(
                    &py_target,
                    &starts,
                    mass,
                    &adapter,
                    &refresh_config,
                    &run.config,
                    run.threads,
                    &control,
                )
            })
            .map_err(|e| py_target.fatal_error(e))?;
        let wall = started.elapsed().as_secs_f64();
        let dict = output_dict(
            py,
            output.chains(),
            wall,
            py_target.calls.load(Ordering::Relaxed),
            py_target.recoverable.load(Ordering::Relaxed),
            py_target.attached_nanos.load(Ordering::Relaxed) as f64 * 1e-9,
        )?;
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
        return Ok(dict);
    }
    let output = py
        .detach(|| execute(&py_target, &starts, &run))
        .map_err(|e| py_target.fatal_error(e))?;
    let wall = started.elapsed().as_secs_f64();
    output_dict(
        py,
        &output,
        wall,
        py_target.calls.load(Ordering::Relaxed),
        py_target.recoverable.load(Ordering::Relaxed),
        py_target.attached_nanos.load(Ordering::Relaxed) as f64 * 1e-9,
    )
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
    let run = parse_run(py, dimension, starts.len(), config, false)?;
    struct Never(usize);
    impl Target for Never {
        fn dimension(&self) -> usize {
            self.0
        }
        fn log_density_gradient(&self, _: &[f64], _: &mut [f64]) -> Result<f64, TargetError> {
            Err(TargetError::new("preflight target must not be evaluated"))
        }
    }
    let (transitions, worst, ceiling) =
        preflight(&Never(dimension), &starts, &run).map_err(facade_error)?;
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
    let run = parse_run(py, target.dimension(), starts.len(), config, false)?;
    let started = Instant::now();
    let output = py
        .detach(|| execute(&target, &starts, &run))
        .map_err(facade_error)?;
    let wall = started.elapsed().as_secs_f64();
    output_dict(
        py,
        &output,
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
    let run = parse_run(py, target.dimension(), starts.len(), config, false)?;
    let started = Instant::now();
    let output = py
        .detach(|| execute(&target, &starts, &run))
        .map_err(facade_error)?;
    let wall = started.elapsed().as_secs_f64();
    output_dict(
        py,
        &output,
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
    let run = parse_run(py, dimension, starts.len(), config, false)?;
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
    let calls = output
        .chains()
        .iter()
        .map(|c| c.telemetry().total().target_calls_total())
        .sum();
    output_dict(py, &output, wall, calls, 0, 0.0)
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
    Ok(())
}
