//! Resident warm-continuation session (WP91): one worker thread that owns
//! the target, keeps a pool of `threads` Rayon workers and every per-chain
//! configuration, mass and position alive across calls, and runs `draws`
//! warm transitions per chain on request. Each call is bit-identical to
//! `sampler::Sampler::run_warm` under the seed rule documented on
//! [`WarmSession`]. Like [`super::session`], no borrowed state leaves the
//! worker stack and the target drops on the worker thread after its last
//! callback has returned.
use super::*;
use std::cell::Cell;
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
        reply: mpsc::Sender<Result<WarmChunk, Failure>>,
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
                self.state.set_positions_from_last_draws(&chunk);
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
    samples: Vec<f64>,
    diagnostics: Vec<TransitionDiagnostics>,
    telemetry: RunTelemetry,
    step_size: f64,
    mass_diagonal: Vec<f64>,
    effective_seed: u64,
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
                    reply,
                }) => {
                    let result =
                        self.refresh(draws, seed, call_index, deadline, cancellation, pool);
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

    fn refresh(
        &mut self,
        draws: usize,
        seed: u64,
        call_index: usize,
        deadline: Option<Instant>,
        cancellation: &WarmCancellation,
        pool: Option<&rayon::ThreadPool>,
    ) -> Result<WarmChunk, Failure> {
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
                run_chains(&wrapped, &self.plan, threads, &control, pool)
            }
            None => run_chains(&self.target, &self.plan, threads, &control, pool),
        }
        .map_err(|error| Failure {
            error,
            terminal: true,
        })?;
        let dimension = self.plan.dimension;
        let mut target_calls = 0usize;
        let mut chains = Vec::with_capacity(results.len());
        for (position, result) in self.plan.positions.iter_mut().zip(results) {
            position.copy_from_slice(&result.samples[(draws - 1) * dimension..]);
            target_calls =
                target_calls.saturating_add(result.telemetry.total().target_calls_total());
            chains.push(WarmChainChunk {
                samples: result.samples,
                diagnostics: result.diagnostics,
                telemetry: result.telemetry,
                step_size: result.step_size,
                mass_diagonal: result.mass_diagonal,
                effective_seed: result.effective_seed,
            });
        }
        Ok(WarmChunk {
            chains,
            dimension,
            draws,
            seed,
            call_index,
            target_calls,
        })
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

fn run_one<U: Target>(
    target: &U,
    dimension: usize,
    position: &[f64],
    mass: &DiagonalMass,
    config: &RunConfig,
    threads: usize,
    control: &ExecutionControl<'_>,
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
    run.advance(run.transitions)?;
    // As `ChainRun::finish`: a final control check, then the retained-draw
    // window summary.
    control.check().map_err(control_error)?;
    let telemetry = run.telemetry_snapshot();
    Ok(ChainResult {
        samples: std::mem::take(&mut run.samples),
        diagnostics: std::mem::take(&mut run.diagnostics),
        telemetry,
        step_size: run.active_tuning.step_size,
        mass_diagonal: run.active_mass.diagonal.clone(),
        effective_seed: run.seed,
    })
}
