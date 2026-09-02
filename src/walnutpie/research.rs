//! Research-only facades and controls.
//!
//! Everything in this module is compiled into the crate unconditionally, but
//! it is exported from [`walnutpie`](super) only with the `research` Cargo
//! feature. These items may change or disappear between minor versions.

#![cfg_attr(not(feature = "research"), allow(dead_code))]

use super::*;

/// Execution revision for explicitly original-coordinate metric APIs.
///
/// This stream is deterministic within the same build and lockfile, but is
/// intentionally not bit-compatible with the legacy Cholesky-coordinate
/// wrappers.
pub const DIRECT_ORIGINAL_Q_REVISION: &str = "walnutpie-direct-original-q-mass-operator-v2";

/// Execution revision for projected arrowhead warmup in original coordinates.
pub const PROJECTED_ARROWHEAD_REVISION: &str = "walnutpie-projected-arrowhead-warmup-v2";

/// Research-only outer-orbit selection ablation. Production defaults to
/// [`OuterOrbitSelection::BiasedProgressive`].
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum OuterOrbitSelection {
    BiasedProgressive,
    ExactNormalizedMultinomial,
}

impl From<OuterOrbitSelection> for OuterSelectionPolicy {
    fn from(value: OuterOrbitSelection) -> Self {
        match value {
            OuterOrbitSelection::BiasedProgressive => Self::BiasedProgressive,
            OuterOrbitSelection::ExactNormalizedMultinomial => Self::NormalizedMultinomial,
        }
    }
}

/// Hard ceiling for explicit research-only target-evaluation opt-ins.
pub const RESEARCH_MAX_TARGET_EVALUATIONS: usize = 1_000_000_000;

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
#[non_exhaustive]
pub enum ResearchRestartReferenceMultiplier {
    One,
    Ten,
}

impl ResearchRestartReferenceMultiplier {
    pub fn value(self) -> f64 {
        match self {
            Self::One => 1.0,
            Self::Ten => 10.0,
        }
    }
}

/// Metric accepted by the versioned direct-original-q execution APIs.
#[derive(Clone, Debug, PartialEq)]
#[non_exhaustive]
pub enum DirectOriginalQMass {
    Dense(DenseMass),
    BlockDiagonal(BlockDiagonalMass),
    StructuredPath(StructuredBlockMass),
    LowRankArrowhead(LowRankArrowheadMass),
}

impl DirectOriginalQMass {
    pub fn dimension(&self) -> usize {
        MassOperator::dimension(self)
    }
}

impl MassOperator for DirectOriginalQMass {
    fn dimension(&self) -> usize {
        match self {
            Self::Dense(value) => value.dimension(),
            Self::BlockDiagonal(value) => value.dimension(),
            Self::StructuredPath(value) => value.dimension(),
            Self::LowRankArrowhead(value) => value.dimension(),
        }
    }
    fn sample_momentum(&self, rng: &mut dyn rand::RngCore) -> Result<Vec<f64>, ValidationError> {
        match self {
            Self::Dense(value) => MassOperator::sample_momentum(value, rng),
            Self::BlockDiagonal(value) => MassOperator::sample_momentum(value, rng),
            Self::StructuredPath(value) => MassOperator::sample_momentum(value, rng),
            Self::LowRankArrowhead(value) => MassOperator::sample_momentum(value, rng),
        }
    }
    fn velocity(&self, momentum: &[f64]) -> Vec<f64> {
        match self {
            Self::Dense(value) => MassOperator::velocity(value, momentum),
            Self::BlockDiagonal(value) => MassOperator::velocity(value, momentum),
            Self::StructuredPath(value) => MassOperator::velocity(value, momentum),
            Self::LowRankArrowhead(value) => MassOperator::velocity(value, momentum),
        }
    }
    fn kinetic_energy(&self, momentum: &[f64]) -> f64 {
        match self {
            Self::Dense(value) => MassOperator::kinetic_energy(value, momentum),
            Self::BlockDiagonal(value) => MassOperator::kinetic_energy(value, momentum),
            Self::StructuredPath(value) => MassOperator::kinetic_energy(value, momentum),
            Self::LowRankArrowhead(value) => MassOperator::kinetic_energy(value, momentum),
        }
    }
    fn is_valid(&self) -> bool {
        true
    }
}

/// Explicit research-only opt-in that raises only the target-evaluation bound.
///
/// Values must exceed [`CONSERVATIVE_MAX_TARGET_EVALUATIONS`] and cannot exceed
/// the hard [`RESEARCH_MAX_TARGET_EVALUATIONS`] ceiling. All arithmetic used to
/// calculate the preflight bound remains checked. This opt-in does not change
/// any other [`ResourceLimits`] field or runtime control behavior.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct ResearchTargetEvaluationLimit {
    pub(super) max_target_evaluations: usize,
}

impl ResearchTargetEvaluationLimit {
    pub fn new(max_target_evaluations: NonZeroUsize) -> Result<Self, Error> {
        let value = max_target_evaluations.get();
        if value <= CONSERVATIVE_MAX_TARGET_EVALUATIONS {
            return Err(Error::configuration(
                "research target-evaluation limit must exceed the conservative default",
            ));
        }
        if value > RESEARCH_MAX_TARGET_EVALUATIONS {
            return Err(Error::configuration(
                "research target-evaluation limit exceeds the hard research ceiling",
            ));
        }
        Ok(Self {
            max_target_evaluations: value,
        })
    }

    pub fn max_target_evaluations(&self) -> usize {
        self.max_target_evaluations
    }
}

/// Sample with a fixed metric directly in the target's original `q`
/// coordinates. This API uses [`DIRECT_ORIGINAL_Q_REVISION`].
pub fn sample_direct_original_q<T: Target>(
    target: &T,
    initial_position: &[f64],
    mass: &DirectOriginalQMass,
    config: &RunConfig,
) -> Result<ChainOutput, Error> {
    sample_direct_original_q_with_control(
        target,
        initial_position,
        mass,
        config,
        &RunControl::new(),
    )
}

pub fn sample_direct_original_q_with_control<T: Target>(
    target: &T,
    initial_position: &[f64],
    mass: &DirectOriginalQMass,
    config: &RunConfig,
    control: &RunControl<'_>,
) -> Result<ChainOutput, Error> {
    sample_operator_fixed_with_control(target, initial_position, mass, config, control)
}

/// Deterministic projected-covariance adaptation for one global/path
/// arrowhead mass. Coordinates must be `[globals, path]`; projections are
/// columns of an orthonormal basis in the base-whitened path coordinates
/// `y = P' q_path`.
#[derive(Clone, Debug, PartialEq)]
pub struct ProjectedArrowheadWarmup {
    basis: Vec<Vec<f64>>,
    minimum_samples: usize,
    shrinkage: f64,
    ridge: f64,
    maximum_condition: f64,
}

impl ProjectedArrowheadWarmup {
    pub fn new(
        basis: Vec<Vec<f64>>,
        minimum_samples: NonZeroUsize,
        shrinkage: f64,
        ridge: f64,
        maximum_condition: f64,
    ) -> Result<Self, Error> {
        let rank = basis.first().map_or(0, Vec::len);
        if basis.is_empty()
            || rank == 0
            || rank > LowRankArrowheadMass::MAX_RANK
            || basis
                .iter()
                .any(|row| row.len() != rank || row.iter().any(|value| !value.is_finite()))
            || !shrinkage.is_finite()
            || !(0.0..=1.0).contains(&shrinkage)
            || !ridge.is_finite()
            || ridge <= 0.0
            || !maximum_condition.is_finite()
            || maximum_condition < 1.0
        {
            return Err(Error::configuration(
                "invalid projected arrowhead warmup configuration",
            ));
        }
        for i in 0..rank {
            for j in 0..rank {
                let dot = basis.iter().map(|row| row[i] * row[j]).sum::<f64>();
                if (dot - usize::from(i == j) as f64).abs() > 1.0e-10 {
                    return Err(Error::configuration(
                        "projected warmup basis must be orthonormal",
                    ));
                }
            }
        }
        Ok(Self {
            basis,
            minimum_samples: minimum_samples.get(),
            shrinkage,
            ridge,
            maximum_condition,
        })
    }

    pub fn rank(&self) -> usize {
        self.basis[0].len()
    }
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
#[non_exhaustive]
pub enum ProjectedMetricOutcome {
    Installed,
    InsufficientSamples,
    NonfiniteFallback,
    FactorizationFallback,
    IllConditionedFallback,
}

#[derive(Clone, Debug, PartialEq)]
pub struct ProjectedMetricUpdate {
    window_index: usize,
    transition: usize,
    sample_count: usize,
    generation: usize,
    rank: usize,
    outcome: ProjectedMetricOutcome,
    shrinkage: f64,
    ridge: f64,
    condition_estimate: Option<f64>,
    factorization_failures: usize,
    step_before: f64,
    step_after_restart: Option<f64>,
}

impl ProjectedMetricUpdate {
    pub fn window_index(&self) -> usize {
        self.window_index
    }
    pub fn transition(&self) -> usize {
        self.transition
    }
    pub fn sample_count(&self) -> usize {
        self.sample_count
    }
    pub fn generation(&self) -> usize {
        self.generation
    }
    pub fn rank(&self) -> usize {
        self.rank
    }
    pub fn outcome(&self) -> ProjectedMetricOutcome {
        self.outcome
    }
    pub fn shrinkage(&self) -> f64 {
        self.shrinkage
    }
    pub fn ridge(&self) -> f64 {
        self.ridge
    }
    pub fn condition_estimate(&self) -> Option<f64> {
        self.condition_estimate
    }
    pub fn factorization_failures(&self) -> usize {
        self.factorization_failures
    }
    pub fn step_before(&self) -> f64 {
        self.step_before
    }
    pub fn step_after_restart(&self) -> Option<f64> {
        self.step_after_restart
    }
}

#[derive(Clone, Debug, PartialEq)]
pub struct ProjectedArrowheadOutput {
    chain: ChainOutput,
    metric_updates: Vec<ProjectedMetricUpdate>,
    final_mass: LowRankArrowheadMass,
}

#[derive(Clone, Debug, PartialEq)]
pub struct PooledProjectedArrowheadOutput {
    chains: MultiChainOutput,
    metric_updates: Vec<ProjectedMetricUpdate>,
    final_mass: LowRankArrowheadMass,
    final_steps: Vec<f64>,
}

impl PooledProjectedArrowheadOutput {
    pub fn chains(&self) -> &MultiChainOutput {
        &self.chains
    }
    pub fn metric_updates(&self) -> &[ProjectedMetricUpdate] {
        &self.metric_updates
    }
    pub fn final_mass(&self) -> &LowRankArrowheadMass {
        &self.final_mass
    }
    pub fn final_steps(&self) -> &[f64] {
        &self.final_steps
    }
}

impl ProjectedArrowheadOutput {
    pub fn chain(&self) -> &ChainOutput {
        &self.chain
    }
    pub fn metric_updates(&self) -> &[ProjectedMetricUpdate] {
        &self.metric_updates
    }
    pub fn final_mass(&self) -> &LowRankArrowheadMass {
        &self.final_mass
    }
}

struct ProjectedCovariance {
    covariance: DenseCovariance,
    global_dimension: usize,
    basis: Vec<Vec<f64>>,
    path: StructuredCovarianceBlock,
}

impl ProjectedCovariance {
    fn new(
        global_dimension: usize,
        specification: &ProjectedArrowheadWarmup,
        path: &StructuredCovarianceBlock,
    ) -> Self {
        Self {
            covariance: DenseCovariance::new(global_dimension + specification.rank()),
            global_dimension,
            basis: specification.basis.clone(),
            path: path.clone(),
        }
    }

    fn update(&mut self, position: &[f64]) {
        let whitened = self
            .path
            .multiply_lower_transpose(&position[self.global_dimension..]);
        let rank = self.basis[0].len();
        let mut selected = position[..self.global_dimension].to_vec();
        selected.extend((0..rank).map(|k| {
            self.basis
                .iter()
                .zip(&whitened)
                .map(|(row, y)| row[k] * y)
                .sum::<f64>()
        }));
        self.covariance.update(&selected);
    }

    fn candidate(
        &self,
        specification: &ProjectedArrowheadWarmup,
    ) -> (
        ProjectedMetricOutcome,
        Option<LowRankArrowheadMass>,
        Option<f64>,
        usize,
    ) {
        if self.covariance.count < specification.minimum_samples {
            return (ProjectedMetricOutcome::InsufficientSamples, None, None, 0);
        }
        let dimension = self.covariance.mean.len();
        let denominator = (self.covariance.count - 1) as f64;
        let mut covariance: Vec<f64> = self.covariance.m2.iter().map(|x| x / denominator).collect();
        if covariance.iter().any(|x| !x.is_finite()) {
            return (ProjectedMetricOutcome::NonfiniteFallback, None, None, 0);
        }
        for i in 0..dimension {
            for j in 0..dimension {
                if i != j {
                    covariance[i * dimension + j] *= 1.0 - specification.shrinkage;
                }
            }
            covariance[i * dimension + i] =
                covariance[i * dimension + i].max(MIN_ADAPTATION_VARIANCE) + specification.ridge;
        }
        let Some(covariance_chol) = cholesky(&covariance, dimension) else {
            return (ProjectedMetricOutcome::FactorizationFallback, None, None, 1);
        };
        let minimum = (0..dimension)
            .map(|i| covariance_chol[i * dimension + i])
            .fold(f64::INFINITY, f64::min);
        let maximum = (0..dimension)
            .map(|i| covariance_chol[i * dimension + i])
            .fold(0.0_f64, f64::max);
        let condition = (maximum / minimum).powi(2);
        if !condition.is_finite() || condition > specification.maximum_condition {
            return (
                ProjectedMetricOutcome::IllConditionedFallback,
                None,
                Some(condition),
                0,
            );
        }
        let Some(precision) = inverse_from_cholesky(&covariance_chol, dimension) else {
            return (
                ProjectedMetricOutcome::FactorizationFallback,
                None,
                Some(condition),
                1,
            );
        };
        let Some(lower) = cholesky(&precision, dimension) else {
            return (
                ProjectedMetricOutcome::FactorizationFallback,
                None,
                Some(condition),
                1,
            );
        };
        let global = self.global_dimension;
        let rank = specification.rank();
        let global_lower = (0..global)
            .map(|i| {
                (0..global)
                    .map(|j| {
                        if j <= i {
                            lower[i * dimension + j]
                        } else {
                            0.0
                        }
                    })
                    .collect()
            })
            .collect();
        let subspace_lower = (0..rank)
            .map(|i| {
                (0..rank)
                    .map(|j| {
                        if j <= i {
                            lower[(global + i) * dimension + global + j]
                        } else {
                            0.0
                        }
                    })
                    .collect()
            })
            .collect();
        let global_factors = (0..global)
            .map(|j| {
                (0..rank)
                    .map(|k| lower[(global + k) * dimension + j])
                    .collect()
            })
            .collect();
        let candidate = LowRankArrowheadMass::new_with_path_subspace(
            global_lower,
            self.path.clone(),
            specification.basis.clone(),
            global_factors,
            specification.basis.clone(),
            subspace_lower,
        )
        .ok();
        match candidate {
            Some(value) => (
                ProjectedMetricOutcome::Installed,
                Some(value),
                Some(condition),
                0,
            ),
            None => (
                ProjectedMetricOutcome::FactorizationFallback,
                None,
                Some(condition),
                1,
            ),
        }
    }
}

/// Run per-chain projected arrowhead adaptation at exact slow-window
/// boundaries. Every segment ends at a transition boundary; therefore
/// momentum is discarded while numeric `q` is copied unchanged. Candidate
/// construction and fallback consume neither target calls nor random draws.
pub fn sample_projected_arrowhead<T: Target>(
    target: &T,
    initial_position: &[f64],
    initial_mass: &LowRankArrowheadMass,
    specification: &ProjectedArrowheadWarmup,
    config: &RunConfig,
    control: &RunControl<'_>,
) -> Result<ProjectedArrowheadOutput, Error> {
    let warmup = config
        .warmup
        .as_ref()
        .ok_or_else(|| Error::configuration("projected arrowhead adaptation requires warmup"))?;
    reject_paper_adaptation(config, "projected arrowhead")?;
    if !warmup.adapt_mass {
        return Err(Error::configuration(
            "projected arrowhead mass adaptation is disabled",
        ));
    }
    let global = initial_mass.global_lower.len();
    if global != 6
        || specification.basis.len() != initial_mass.path.dimension()
        || initial_position.len() != initial_mass.dimension()
        || target.dimension() != initial_mass.dimension()
    {
        return Err(Error::configuration(
            "projected arrowhead warmup requires six leading globals and a matching path basis",
        ));
    }
    let schedule = warmup_schedule(config.discarded, &warmup.windows)?;
    let selected = global
        .checked_add(specification.rank())
        .ok_or_else(Error::overflow)?;
    let workspace = selected
        .checked_mul(selected)
        .and_then(|x| x.checked_mul(size_of::<f64>() * 4))
        .and_then(|x| {
            x.checked_add(initial_mass.dimension() * specification.rank() * size_of::<f64>() * 2)
        })
        .ok_or_else(Error::overflow)?;
    if workspace > config.limits.max_working_bytes {
        return Err(Error::resource(
            "projected adaptation workspace exceeds its resource limit",
        ));
    }
    let identity = DiagonalMass::identity(NonZeroUsize::new(initial_mass.dimension()).unwrap());
    validate(
        target,
        1,
        std::iter::once(initial_position),
        &identity,
        config,
    )?;

    let transitions = config
        .discarded
        .checked_add(config.retained)
        .ok_or_else(Error::overflow)?;
    let mut position = initial_position.to_vec();
    let mut active_mass = initial_mass.clone();
    let mut active_step = config.tuning.step_size;
    let mut dual = warmup
        .adapt_step_size
        .then(|| DualAveraging::new(active_step, warmup.target_acceptance));
    let mut updates = Vec::with_capacity(schedule.windows.len());
    let mut accumulator: Option<ProjectedCovariance> = None;
    let mut generation = 0usize;
    let mut combined: Option<ChainOutput> = None;
    let mut step_searches = Vec::new();
    let boundary_control = ExecutionControl {
        public: control,
        failed_chain: None,
        chain: 0,
    };
    let mut persistent = PersistentChainContext::new(chain_seed(config.seed, 0));

    for transition in 0..transitions {
        let window_index = schedule
            .windows
            .iter()
            .position(|w| transition >= w.start && transition < w.end);
        if window_index.is_some() && accumulator.is_none() {
            accumulator = Some(ProjectedCovariance::new(
                global,
                specification,
                active_mass.path(),
            ));
        }
        let mut one = config.clone();
        one.discarded = 0;
        one.retained = 1;
        one.warmup = None;
        one.capture_acceptance = true;
        one.tuning.step_size = active_step;
        let direct = DirectOriginalQMass::LowRankArrowhead(active_mass.clone());
        let mut output = run_chain(
            target,
            initial_mass.dimension(),
            &position,
            &identity,
            Some(&direct),
            false,
            &one,
            chain_seed(config.seed, 0),
            1,
            &boundary_control,
            None,
            Some(&mut persistent),
        )
        .map_err(|error| error.at_transition(transition))?;
        let mut transition_work = output.telemetry.total.clone();
        let next = output.samples.clone();
        position.copy_from_slice(&next);
        if let Some(value) = &mut accumulator {
            value.update(&position);
        }
        if let (Some(dual), Some(acceptance)) = (&mut dual, output.telemetry.acceptance_values[0]) {
            active_step = dual.update(acceptance);
        }
        if let Some(index) = window_index
            && schedule.windows[index].end == transition + 1
        {
            boundary_control.check().map_err(control_error)?;
            let collector = accumulator.take().expect("slow-window accumulator");
            let step_before = active_step;
            let sample_count = collector.covariance.count;
            let (outcome, candidate, condition, failures) = collector.candidate(specification);
            boundary_control.check().map_err(control_error)?;
            if let Some(candidate) = candidate {
                active_mass = candidate;
                generation += 1;
                if warmup.adapt_step_size && transition + 1 < config.discarded {
                    if let Some(search) = &warmup.initial_step_search {
                        let cached = persistent.cached_state.as_ref().ok_or_else(|| {
                            Error::new(
                                ErrorKind::Internal,
                                "projected boundary lost its evaluated state",
                            )
                        })?;
                        let direct = DirectOriginalQMass::LowRankArrowhead(active_mass.clone());
                        let momentum = direct
                            .sample_momentum(&mut persistent.rng)
                            .map_err(Error::internal)?;
                        let (step, diagnostics) = search_step_from_evaluated(
                            target,
                            EvaluatedTransitionInput {
                                theta: cached.theta.clone(),
                                rho: momentum,
                                log_prob: cached.log_prob,
                                grad: cached.grad.clone(),
                            },
                            &direct,
                            KernelTuning {
                                step_size: active_step,
                                ..config.tuning
                            },
                            warmup.target_acceptance,
                            search,
                            &mut persistent.rng,
                            &boundary_control,
                            transition,
                            true,
                            &mut transition_work,
                        )
                        .map_err(|error| error.at_transition(transition))?;
                        active_step = step;
                        step_searches.push(StepSearchEvent {
                            reason: StepSearchReason::MetricUpdate {
                                window_index: index,
                            },
                            search: diagnostics,
                        });
                    }
                    dual = Some(DualAveraging::restart(
                        active_step,
                        warmup.target_acceptance,
                        warmup.restart_reference_multiplier(),
                    ));
                }
            }
            updates.push(ProjectedMetricUpdate {
                window_index: index,
                transition,
                sample_count,
                generation,
                rank: specification.rank(),
                outcome,
                shrinkage: specification.shrinkage,
                ridge: specification.ridge,
                condition_estimate: condition,
                factorization_failures: failures,
                step_before,
                step_after_restart: dual.as_ref().map(|_| active_step),
            });
        }
        if transition + 1 == config.discarded
            && let Some(value) = &dual
        {
            active_step = value.final_step();
        }
        if let Some(total) = &mut combined {
            total.diagnostics.append(&mut output.diagnostics);
            if transition >= config.discarded {
                total.samples.extend_from_slice(&next);
                total.retained += 1;
            }
            add_work(&mut total.telemetry.total, &transition_work)?;
            if transition < config.discarded {
                add_work(&mut total.telemetry.discarded, &transition_work)?;
            } else {
                add_work(&mut total.telemetry.retained, &transition_work)?;
            }
        } else {
            if transition < config.discarded {
                output.samples.clear();
                output.retained = 0;
                output.telemetry.discarded = transition_work.clone();
                output.telemetry.retained = WorkTotals::default();
            } else {
                output.retained = 1;
                output.telemetry.discarded = WorkTotals::default();
                output.telemetry.retained = transition_work.clone();
            }
            output.telemetry.total = transition_work;
            combined = Some(output);
        }
    }
    let mut chain =
        combined.ok_or_else(|| Error::configuration("run requires at least one transition"))?;
    chain.metadata.algorithm_revision = PROJECTED_ARROWHEAD_REVISION;
    chain.metadata.step_size = active_step;
    chain.metadata.tuning.step_size = active_step;
    chain.metadata.discarded = config.discarded;
    chain.metadata.retained = config.retained;
    chain.telemetry.step_searches = step_searches;
    Ok(ProjectedArrowheadOutput {
        chain,
        metric_updates: updates,
        final_mass: active_mass,
    })
}

struct PooledProjectedChain {
    position: Vec<f64>,
    persistent: PersistentChainContext,
    active_step: f64,
    dual: Option<DualAveraging>,
    accumulator: Option<ProjectedCovariance>,
    output: Option<ChainOutput>,
}

/// Pooled projected-arrowhead adaptation with a deterministic window barrier.
///
/// Chains own independent RNG/cache/dual-averaging state. At each common
/// slow-window boundary their Welford summaries are merged in chain-index
/// order and exactly one metric generation is installed for all chains.
#[allow(clippy::too_many_arguments)]
pub fn sample_chains_projected_arrowhead<T: Target>(
    target: &T,
    initial_positions: &[Vec<f64>],
    initial_mass: &LowRankArrowheadMass,
    specification: &ProjectedArrowheadWarmup,
    config: &RunConfig,
    max_threads: NonZeroUsize,
    run_control: &RunControl<'_>,
) -> Result<PooledProjectedArrowheadOutput, Error> {
    let warmup = config
        .warmup
        .as_ref()
        .ok_or_else(|| Error::configuration("pooled projected adaptation requires warmup"))?;
    reject_paper_adaptation(config, "pooled projected arrowhead")?;
    if !warmup.adapt_mass || initial_positions.is_empty() {
        return Err(Error::configuration(
            "pooled projected adaptation requires chains and mass adaptation",
        ));
    }
    let chains = initial_positions.len();
    if chains > config.limits.max_chains {
        return Err(Error::resource("chain count exceeds its resource limit"));
    }
    let dimension = initial_mass.dimension();
    let global = initial_mass.global_lower.len();
    if global != 6
        || target.dimension() != dimension
        || specification.basis.len() != initial_mass.path.dimension()
        || initial_positions
            .iter()
            .any(|position| position.len() != dimension)
    {
        return Err(Error::configuration(
            "pooled projected dimensions are incompatible",
        ));
    }
    let schedule = warmup_schedule(config.discarded, &warmup.windows)?;
    let selected = global
        .checked_add(specification.rank())
        .ok_or_else(Error::overflow)?;
    let per_chain_workspace = selected
        .checked_mul(selected)
        .and_then(|x| x.checked_mul(size_of::<f64>() * 4))
        .and_then(|x| {
            x.checked_add(
                dimension
                    .checked_mul(specification.rank())?
                    .checked_mul(size_of::<f64>() * 2)?,
            )
        })
        .ok_or_else(Error::overflow)?;
    if per_chain_workspace
        .checked_mul(chains)
        .ok_or_else(Error::overflow)?
        > config.limits.max_working_bytes
    {
        return Err(Error::resource(
            "pooled projected adaptation workspace exceeds its resource limit",
        ));
    }
    let identity = DiagonalMass::identity(NonZeroUsize::new(dimension).unwrap());
    validate(
        target,
        chains,
        initial_positions.iter().map(Vec::as_slice),
        &identity,
        config,
    )?;
    let transitions = config
        .discarded
        .checked_add(config.retained)
        .ok_or_else(Error::overflow)?;
    let failed_chain = AtomicUsize::new(usize::MAX);
    let threads = max_threads.get().min(chains);
    let pool = (threads > 1)
        .then(|| {
            rayon::ThreadPoolBuilder::new()
                .num_threads(threads)
                .build()
                .map_err(|_| Error::resource("could not create bounded Rayon pool"))
        })
        .transpose()?;
    let mut states = initial_positions
        .iter()
        .enumerate()
        .map(|(chain, position)| PooledProjectedChain {
            position: position.clone(),
            persistent: PersistentChainContext::new(chain_seed(config.seed, chain)),
            active_step: config.tuning.step_size,
            dual: warmup
                .adapt_step_size
                .then(|| DualAveraging::new(config.tuning.step_size, warmup.target_acceptance)),
            accumulator: None,
            output: None,
        })
        .collect::<Vec<_>>();
    let mut active_mass = initial_mass.clone();
    let mut updates = Vec::with_capacity(schedule.windows.len());
    let mut generation = 0usize;

    for transition in 0..transitions {
        run_control_check(run_control)?;
        let window_index = schedule
            .windows
            .iter()
            .position(|window| transition >= window.start && transition < window.end);
        for state in &mut states {
            if window_index.is_some() && state.accumulator.is_none() {
                state.accumulator = Some(ProjectedCovariance::new(
                    global,
                    specification,
                    active_mass.path(),
                ));
            }
        }
        let mass = DirectOriginalQMass::LowRankArrowhead(active_mass.clone());
        let execute = |(chain, state): (usize, &mut PooledProjectedChain)| {
            let control = ExecutionControl {
                public: run_control,
                failed_chain: Some(&failed_chain),
                chain,
            };
            let mut one = config.clone();
            one.discarded = 0;
            one.retained = 1;
            one.warmup = None;
            one.capture_acceptance = true;
            one.tuning.step_size = state.active_step;
            let result = run_chain(
                target,
                dimension,
                &state.position,
                &identity,
                Some(&mass),
                false,
                &one,
                chain_seed(config.seed, chain),
                threads,
                &control,
                None,
                Some(&mut state.persistent),
            )
            .map_err(|error| error.at_chain(chain).at_transition(transition));
            if result.is_err() {
                failed_chain.fetch_min(chain, Ordering::AcqRel);
            }
            result
        };
        let results: Vec<Result<ChainOutput, Error>> = if let Some(pool) = &pool {
            pool.install(|| states.par_iter_mut().enumerate().map(execute).collect())
        } else {
            states.iter_mut().enumerate().map(execute).collect()
        };
        for (chain, result) in results.into_iter().enumerate() {
            let output = result?;
            let state = &mut states[chain];
            let work = output.telemetry.total.clone();
            state.position.copy_from_slice(&output.samples);
            if let Some(accumulator) = &mut state.accumulator {
                accumulator.update(&state.position);
            }
            if let (Some(dual), Some(acceptance)) =
                (&mut state.dual, output.telemetry.acceptance_values[0])
            {
                state.active_step = dual.update(acceptance);
            }
            append_projected_transition(
                &mut state.output,
                output,
                transition,
                config.discarded,
                &work,
            )?;
        }

        if let Some(index) = window_index
            && schedule.windows[index].end == transition + 1
        {
            run_control_check(run_control)?;
            let mut pooled = ProjectedCovariance::new(global, specification, active_mass.path());
            for state in &mut states {
                let summary = state.accumulator.take().expect("window accumulator exists");
                pooled.covariance.merge(&summary.covariance)?;
            }
            let sample_count = pooled.covariance.count;
            let step_before = states[0].active_step;
            let (outcome, candidate, condition, failures) = pooled.candidate(specification);
            run_control_check(run_control)?;
            if let Some(candidate) = candidate {
                active_mass = candidate;
                generation += 1;
                if warmup.adapt_step_size && transition + 1 < config.discarded {
                    for (chain, state) in states.iter_mut().enumerate() {
                        if let Some(search) = &warmup.initial_step_search {
                            let control = ExecutionControl {
                                public: run_control,
                                failed_chain: Some(&failed_chain),
                                chain,
                            };
                            let cached =
                                state.persistent.cached_state.as_ref().ok_or_else(|| {
                                    Error::new(
                                        ErrorKind::Internal,
                                        "pooled barrier lost cached state",
                                    )
                                })?;
                            let direct = DirectOriginalQMass::LowRankArrowhead(active_mass.clone());
                            let momentum = direct
                                .sample_momentum(&mut state.persistent.rng)
                                .map_err(Error::internal)?;
                            let mut search_work = WorkTotals::default();
                            let (step, diagnostics) = search_step_from_evaluated(
                                target,
                                EvaluatedTransitionInput {
                                    theta: cached.theta.clone(),
                                    rho: momentum,
                                    log_prob: cached.log_prob,
                                    grad: cached.grad.clone(),
                                },
                                &direct,
                                KernelTuning {
                                    step_size: state.active_step,
                                    ..config.tuning
                                },
                                warmup.target_acceptance,
                                search,
                                &mut state.persistent.rng,
                                &control,
                                transition,
                                true,
                                &mut search_work,
                            )
                            .map_err(|error| error.at_chain(chain).at_transition(transition))?;
                            state.active_step = step;
                            let output = state.output.as_mut().expect("chain has transitioned");
                            add_work(&mut output.telemetry.total, &search_work)?;
                            add_work(&mut output.telemetry.discarded, &search_work)?;
                            output.telemetry.step_searches.push(StepSearchEvent {
                                reason: StepSearchReason::MetricUpdate {
                                    window_index: index,
                                },
                                search: diagnostics,
                            });
                        }
                        state.dual = Some(DualAveraging::restart(
                            state.active_step,
                            warmup.target_acceptance,
                            warmup.restart_reference_multiplier(),
                        ));
                    }
                }
            }
            updates.push(ProjectedMetricUpdate {
                window_index: index,
                transition,
                sample_count,
                generation,
                rank: specification.rank(),
                outcome,
                shrinkage: specification.shrinkage,
                ridge: specification.ridge,
                condition_estimate: condition,
                factorization_failures: failures,
                step_before,
                step_after_restart: states.first().map(|state| state.active_step),
            });
        }
        if transition + 1 == config.discarded {
            for state in &mut states {
                if let Some(dual) = &state.dual {
                    state.active_step = dual.final_step();
                }
            }
        }
    }
    let mut outputs = Vec::with_capacity(chains);
    let mut final_steps = Vec::with_capacity(chains);
    for (chain, state) in states.into_iter().enumerate() {
        let mut output = state
            .output
            .ok_or_else(|| Error::configuration("run requires at least one transition"))?;
        output.metadata.algorithm_revision = PROJECTED_ARROWHEAD_REVISION;
        output.metadata.base_seed = config.seed;
        output.metadata.effective_seed = chain_seed(config.seed, chain);
        output.metadata.thread_count = threads;
        output.metadata.step_size = state.active_step;
        output.metadata.tuning.step_size = state.active_step;
        output.metadata.discarded = config.discarded;
        output.metadata.retained = config.retained;
        final_steps.push(state.active_step);
        outputs.push(output);
    }
    Ok(PooledProjectedArrowheadOutput {
        chains: MultiChainOutput {
            chains: outputs,
            base_seed: config.seed,
            algorithm_revision: PROJECTED_ARROWHEAD_REVISION,
        },
        metric_updates: updates,
        final_mass: active_mass,
        final_steps,
    })
}

pub fn preflight_chains_projected_arrowhead<T: Target>(
    target: &T,
    initial_positions: &[Vec<f64>],
    initial_mass: &LowRankArrowheadMass,
    specification: &ProjectedArrowheadWarmup,
    config: &RunConfig,
) -> Result<PreflightReport, Error> {
    if initial_positions.is_empty()
        || target.dimension() != initial_mass.dimension()
        || specification.basis.len() != initial_mass.path.dimension()
        || initial_positions
            .iter()
            .any(|position| position.len() != initial_mass.dimension())
    {
        return Err(Error::configuration(
            "pooled projected preflight dimensions are incompatible",
        ));
    }
    let identity = DiagonalMass::identity(NonZeroUsize::new(initial_mass.dimension()).unwrap());
    preflight_chains(target, initial_positions, &identity, config)
}

fn run_control_check(control: &RunControl<'_>) -> Result<(), Error> {
    ExecutionControl {
        public: control,
        failed_chain: None,
        chain: 0,
    }
    .check()
    .map_err(control_error)
}

pub fn preflight_direct_original_q<T: Target>(
    target: &T,
    initial_positions: &[Vec<f64>],
    mass: &DirectOriginalQMass,
    config: &RunConfig,
) -> Result<PreflightReport, Error> {
    if config
        .warmup
        .as_ref()
        .is_some_and(|warmup| warmup.adapt_mass)
    {
        return Err(Error::configuration(
            "direct fixed-metric API does not permit mass adaptation",
        ));
    }
    let identity =
        DiagonalMass::identity(NonZeroUsize::new(mass.dimension()).ok_or_else(Error::overflow)?);
    preflight_chains(target, initial_positions, &identity, config)
}

pub fn preflight_direct_original_q_with_target_budget<T: Target>(
    target: &T,
    initial_positions: &[Vec<f64>],
    mass: &DirectOriginalQMass,
    config: &RunConfig,
    admission_limit: TargetEvaluationAdmissionLimit,
    budget: &TargetEvaluationBudget,
) -> Result<PreflightReport, Error> {
    if budget.maximum() > admission_limit.maximum() {
        return Err(Error::configuration(
            "runtime target-evaluation budget exceeds its admission ceiling",
        ));
    }
    let identity =
        DiagonalMass::identity(NonZeroUsize::new(mass.dimension()).ok_or_else(Error::overflow)?);
    let (dimension, _, total_transitions) = validate_with_admission(
        target,
        initial_positions.len(),
        initial_positions.iter().map(Vec::as_slice),
        &identity,
        config,
        Some(admission_limit.maximum()),
    )?;
    Ok(PreflightReport {
        dimension,
        chains: initial_positions.len(),
        total_transitions,
        worst_case_target_evaluations: config.worst_case_target_evaluations(
            NonZeroUsize::new(initial_positions.len()).ok_or_else(Error::overflow)?,
        )?,
        admission_ceiling: admission_limit.maximum(),
    })
}

pub fn sample_direct_original_q_with_target_budget_and_control<T: Target>(
    target: &T,
    initial_position: &[f64],
    mass: &DirectOriginalQMass,
    config: &RunConfig,
    admission_limit: TargetEvaluationAdmissionLimit,
    budget: &TargetEvaluationBudget,
    control: &RunControl<'_>,
) -> Result<ChainOutput, Error> {
    if budget.started() != 0 {
        return Err(Error::configuration(
            "runtime target-evaluation budget must be fresh",
        ));
    }
    preflight_direct_original_q_with_target_budget(
        target,
        &[initial_position.to_vec()],
        mass,
        config,
        admission_limit,
        budget,
    )?;
    let wrapped = budget.wrap(target);
    sample_direct_original_q_with_control(&wrapped, initial_position, mass, config, control)
}

/// Deterministic chain-index ordered direct-original-q execution.
pub fn sample_chains_direct_original_q<T: Target>(
    target: &T,
    initial_positions: &[Vec<f64>],
    mass: &DirectOriginalQMass,
    config: &RunConfig,
    max_threads: NonZeroUsize,
) -> Result<MultiChainOutput, Error> {
    let report = preflight_direct_original_q(target, initial_positions, mass, config)?;
    let threads = max_threads.get().min(report.chains());
    let execute = |chain: usize, position: &Vec<f64>| {
        let mut chain_config = config.clone();
        chain_config.seed = config.seed.wrapping_add(chain as u64);
        sample_direct_original_q(target, position, mass, &chain_config)
            .map(|mut output| {
                output.metadata.base_seed = config.seed;
                output.metadata.effective_seed = chain_seed(config.seed, chain);
                output.metadata.thread_count = threads;
                output
            })
            .map_err(|error| error.at_chain(chain))
    };
    let results = if threads == 1 {
        initial_positions
            .iter()
            .enumerate()
            .map(|(chain, position)| execute(chain, position))
            .collect::<Vec<_>>()
    } else {
        let pool = rayon::ThreadPoolBuilder::new()
            .num_threads(threads)
            .build()
            .map_err(|_| Error::resource("could not create bounded Rayon pool"))?;
        catch_unwind(AssertUnwindSafe(|| {
            pool.install(|| {
                initial_positions
                    .par_iter()
                    .enumerate()
                    .map(|(chain, position)| execute(chain, position))
                    .collect::<Vec<_>>()
            })
        }))
        .map_err(|_| Error::new(ErrorKind::Panic, "Rayon pool panicked"))?
    };
    let mut chains = Vec::with_capacity(results.len());
    for result in results {
        chains.push(result?);
    }
    Ok(MultiChainOutput {
        chains,
        base_seed: config.seed,
        algorithm_revision: DIRECT_ORIGINAL_Q_REVISION,
    })
}
