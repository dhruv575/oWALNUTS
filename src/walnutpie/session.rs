//! Owned coordinator and bounded parallel workers for additive continuation. No borrowed state leaves
//! the worker stack. This module deliberately does not reconstruct ChainRun.
use super::*;
use std::cell::Cell;
use std::sync::atomic::AtomicBool;
use std::sync::{Arc, Mutex, mpsc};
use std::thread::JoinHandle;
thread_local! { static SESSION_WORKER: Cell<usize> = const { Cell::new(0) }; }

#[derive(Clone, Debug)]
pub struct SessionChainChunk {
    pub samples: Vec<f64>,
    pub diagnostics: Vec<TransitionDiagnostics>,
    /// Cumulative telemetry since session initialization, never per-chunk.
    pub telemetry: RunTelemetry,
    pub mass_diagonal: Vec<f64>,
    pub tuning: KernelTuning,
    pub effective_seed: u64,
}

#[derive(Clone, Debug)]
pub struct SessionChunk {
    pub chains: Vec<SessionChainChunk>,
    pub dimension: usize,
    pub retained_start: usize,
    pub retained_end: usize,
    pub is_warmup: bool,
    pub target_calls: usize,
    pub cumulative_target_calls: usize,
    /// Subset of target_calls spent initializing the warmup request (including
    /// the shared initial-step search). Zero on retained chunks. Never add this
    /// field a second time when summing chunk target_calls.
    pub initialization_target_calls: usize,
}

#[derive(Clone, Debug, Default)]
/// Last completed-request/error snapshot. Counters and transition indices are
/// not refreshed inside an active adapt/draw request; this is not live progress.
pub struct SessionProgress {
    pub adapted: bool,
    pub closed: bool,
    pub failed: bool,
    pub error: Option<String>,
    pub completed_transitions: Vec<usize>,
    pub target_calls: usize,
}

struct SessionCancellation {
    local: Arc<AtomicBool>,
    external: Option<Arc<dyn Cancellation>>,
}
impl Cancellation for SessionCancellation {
    fn is_cancelled(&self) -> bool {
        self.local.load(Ordering::Acquire)
            || self.external.as_ref().is_some_and(|c| c.is_cancelled())
    }
}

enum Request {
    Adapt(mpsc::Sender<Result<SessionChunk, Error>>),
    Draw(usize, mpsc::Sender<Result<SessionChunk, Error>>),
    Close,
}

/// An owned continuation session. Explicit close joins; Drop cancels and detaches
/// so a nonreturning target cannot block a destructor. The worker retains all
/// target ownership until its last callback finishes.
pub struct SessionHandle {
    requests: mpsc::Sender<Request>,
    busy: Mutex<()>,
    cancellation: Arc<AtomicBool>,
    worker: Mutex<Option<JoinHandle<()>>>,
    worker_id: std::thread::ThreadId,
    progress: Arc<Mutex<SessionProgress>>,
}

impl SessionHandle {
    fn request(&self, draws: Option<usize>) -> Result<SessionChunk, Error> {
        let _guard = self
            .busy
            .try_lock()
            .map_err(|_| Error::configuration("session already has an active call"))?;
        let (tx, rx) = mpsc::channel();
        let request = match draws {
            Some(n) => Request::Draw(n, tx),
            None => Request::Adapt(tx),
        };
        self.requests
            .send(request)
            .map_err(|_| Error::configuration("session is terminal"))?;
        rx.recv()
            .map_err(|_| Error::new(ErrorKind::Panic, "session worker disconnected"))?
    }
    pub fn adapt(&self) -> Result<SessionChunk, Error> {
        self.request(None)
    }
    pub fn draw(&self, draws: usize) -> Result<SessionChunk, Error> {
        self.request(Some(draws))
    }
    pub fn cancel(&self) {
        self.cancellation.store(true, Ordering::Release);
        let _ = self.requests.send(Request::Close);
    }
    pub fn progress(&self) -> SessionProgress {
        self.progress
            .lock()
            .unwrap_or_else(|p| p.into_inner())
            .clone()
    }
    pub fn close(&self) -> Result<(), Error> {
        self.cancel();
        // Check before acquiring the join mutex: another thread can already
        // hold it while joining us. A callback must never wait on that join.
        if std::thread::current().id() == self.worker_id
            || SESSION_WORKER.with(|id| id.get() == Arc::as_ptr(&self.cancellation) as usize)
        {
            return Err(Error::configuration(
                "cannot join a session from its own worker; cancellation was requested, close from another thread",
            ));
        }
        if let Some(worker) = self.worker.lock().unwrap_or_else(|p| p.into_inner()).take() {
            worker
                .join()
                .map_err(|_| Error::new(ErrorKind::Panic, "session worker panicked"))?;
        }
        Ok(())
    }
}
impl Drop for SessionHandle {
    fn drop(&mut self) {
        self.cancel();
    }
}

pub(crate) struct SessionSetup {
    pub threads: usize,
    pub config: RunConfig,
    pub mass: DiagonalMass,
    pub budget: NonZeroUsize,
    pub explicit_admission: bool,
    pub deadline: Option<Instant>,
    pub external_cancellation: Option<Arc<dyn Cancellation>>,
}

pub(crate) fn spawn<T: Target + 'static>(
    target: T,
    starts: Vec<Vec<f64>>,
    setup: SessionSetup,
) -> Result<SessionHandle, Error> {
    if setup
        .config
        .warmup
        .as_ref()
        .is_some_and(|w| w.chain_rescue.is_some())
    {
        return Err(Error::configuration(
            "continuation does not support chain rescue",
        ));
    }
    let threads = setup.threads.min(starts.len());
    if threads == 0 || threads > setup.config.limits.max_chains {
        return Err(Error::configuration("invalid continuation thread count"));
    }
    let budget = TargetEvaluationBudget::new(setup.budget);
    let dimension = if setup.explicit_admission {
        preflight_chains_with_target_budget(
            &target,
            &starts,
            &setup.mass,
            &setup.config,
            TargetEvaluationAdmissionLimit::new(setup.budget),
            &budget,
        )?
        .dimension()
    } else {
        validate(
            &target,
            starts.len(),
            starts.iter().map(Vec::as_slice),
            &setup.mass,
            &setup.config,
        )?
        .0
    };
    if target.cancel_after_admission() {
        return Err(Error::new(
            ErrorKind::Cancelled,
            "execution cancelled after admission",
        ));
    }
    let (tx, rx) = mpsc::channel();
    let cancellation = Arc::new(AtomicBool::new(false));
    let worker_cancel = Arc::clone(&cancellation);
    let progress = Arc::new(Mutex::new(SessionProgress {
        completed_transitions: vec![0; starts.len()],
        ..SessionProgress::default()
    }));
    let worker_progress = Arc::clone(&progress);
    let worker = std::thread::Builder::new()
        .name("owalnuts-continuation".into())
        .spawn(move || {
            let session_id = Arc::as_ptr(&worker_cancel) as usize;
            SESSION_WORKER.with(|id| id.set(session_id));
            let cancellation = SessionCancellation {
                local: worker_cancel,
                external: setup.external_cancellation,
            };
            let mut control = RunControl::new().with_cancellation(&cancellation);
            if let Some(deadline) = setup.deadline {
                control = control.with_deadline(deadline);
            }
            let wrapped = budget.wrap(&target);
            let result = catch_unwind(AssertUnwindSafe(|| {
                if threads == 1 {
                    serve(
                        &wrapped,
                        &starts,
                        &setup.mass,
                        &setup.config,
                        dimension,
                        &control,
                        &budget,
                        &rx,
                        &worker_progress,
                        None,
                    );
                    Ok(())
                } else {
                    with_scoped_pool_using(
                        threads,
                        |worker| {
                            SESSION_WORKER.with(|id| id.set(session_id));
                            worker.run();
                            SESSION_WORKER.with(|id| id.set(0));
                        },
                        |pool| {
                            serve(
                                &wrapped,
                                &starts,
                                &setup.mass,
                                &setup.config,
                                dimension,
                                &control,
                                &budget,
                                &rx,
                                &worker_progress,
                                Some(pool),
                            )
                        },
                    )
                }
            }));
            let mut state = worker_progress.lock().unwrap_or_else(|p| p.into_inner());
            state.closed = true;
            state.target_calls = budget.started();
            match result {
                Err(_) => {
                    state.failed = true;
                    state.error = Some("session worker panicked".into());
                }
                Ok(Err(error)) => {
                    state.failed = true;
                    state.error = Some(error.to_string());
                }
                Ok(Ok(())) => {}
            }
            // target (including any external-code keepalive) drops only after runs,
            // wrappers and callback execution have left scope.
        })
        .map_err(|e| Error::resource(format!("could not spawn continuation worker: {e}")))?;
    let worker_id = worker.thread().id();
    Ok(SessionHandle {
        requests: tx,
        busy: Mutex::new(()),
        cancellation,
        worker: Mutex::new(Some(worker)),
        worker_id,
        progress,
    })
}

fn serve<T: Target>(
    target: &T,
    starts: &[Vec<f64>],
    mass: &DiagonalMass,
    config: &RunConfig,
    dimension: usize,
    control: &RunControl<'_>,
    budget: &TargetEvaluationBudget,
    requests: &mpsc::Receiver<Request>,
    progress: &Mutex<SessionProgress>,
    pool: Option<&rayon::ThreadPool>,
) {
    let first_reply = loop {
        match requests.recv() {
            Ok(Request::Adapt(reply)) => break reply,
            Ok(Request::Draw(_, reply)) => {
                let _ = reply.send(Err(Error::configuration(
                    "adapt must be called before draw",
                )));
            }
            Ok(Request::Close) | Err(_) => return,
        }
    };
    let controls: Vec<_> = (0..starts.len())
        .map(|chain| ExecutionControl {
            public: control,
            failed_chain: None,
            chain,
        })
        .collect();
    let initialization = catch_unwind(AssertUnwindSafe(|| -> Result<_, Error> {
        let shared = if let Some((warmup, search)) = config
            .warmup
            .as_ref()
            .and_then(|w| w.initial_step_search.as_ref().map(|s| (w, s)))
        {
            Some(
                search_initial_step(
                    target,
                    &starts[0],
                    mass,
                    &inverse_mass(mass)?,
                    config.tuning,
                    warmup.target_acceptance,
                    search,
                    chain_seed(config.seed, 0),
                    &controls[0],
                )
                .map_err(|e| e.at_chain(0))?,
            )
        } else {
            None
        };
        let mut runs = Vec::with_capacity(starts.len());
        for (chain, start) in starts.iter().enumerate() {
            runs.push(
                ChainRun::start(
                    target,
                    dimension,
                    start,
                    mass,
                    None,
                    false,
                    config,
                    chain_seed(config.seed, chain),
                    1,
                    &controls[chain],
                    shared.as_ref(),
                    None,
                )
                .map_err(|e| e.at_chain(chain))?,
            );
        }
        Ok(runs)
    }))
    .unwrap_or_else(|_| {
        Err(Error::new(
            ErrorKind::Panic,
            "session initialization panicked",
        ))
    });
    let mut runs = match initialization {
        Ok(runs) => runs,
        Err(error) => {
            fail(progress, budget, &[], &error);
            let _ = first_reply.send(Err(error));
            return;
        }
    };
    let initialization_calls = budget.started();
    let mut first = advance(
        &mut runs,
        config.discarded,
        budget,
        0,
        0,
        true,
        progress,
        pool,
    );
    if let Ok(chunk) = &mut first {
        chunk.initialization_target_calls = initialization_calls;
    }
    let failed = first.is_err();
    if !failed {
        progress.lock().unwrap_or_else(|p| p.into_inner()).adapted = true;
    }
    if first_reply.send(first).is_err() || failed {
        return;
    }
    let mut retained = 0usize;
    loop {
        match requests.recv() {
            Ok(Request::Adapt(reply)) => {
                let _ = reply.send(Err(Error::configuration("warmup already completed")));
            }
            Ok(Request::Draw(n, reply)) => {
                let Some(end) = retained
                    .checked_add(n)
                    .filter(|end| n > 0 && *end <= config.retained)
                else {
                    let _ = reply.send(Err(Error::configuration(
                        "draw count must be positive and within remaining session budget",
                    )));
                    continue;
                };
                let Some(transition_end) = config.discarded.checked_add(end) else {
                    let _ = reply.send(Err(Error::overflow()));
                    continue;
                };
                let result = advance(
                    &mut runs,
                    transition_end,
                    budget,
                    retained,
                    end,
                    false,
                    progress,
                    pool,
                );
                let failed = result.is_err();
                if reply.send(result).is_err() || failed {
                    return;
                }
                retained = end;
            }
            Ok(Request::Close) | Err(_) => return,
        }
    }
}

fn fail(
    progress: &Mutex<SessionProgress>,
    budget: &TargetEvaluationBudget,
    transitions: &[usize],
    error: &Error,
) {
    let mut state = progress.lock().unwrap_or_else(|p| p.into_inner());
    state.failed = true;
    state.error = Some(error.to_string());
    state.target_calls = budget.started();
    if !transitions.is_empty() {
        state.completed_transitions = transitions.to_vec();
    }
}

fn advance<T: Target>(
    runs: &mut [ChainRun<'_, T>],
    end: usize,
    budget: &TargetEvaluationBudget,
    retained_start: usize,
    retained_end: usize,
    is_warmup: bool,
    progress: &Mutex<SessionProgress>,
    pool: Option<&rayon::ThreadPool>,
) -> Result<SessionChunk, Error> {
    let calls_before = if is_warmup { 0 } else { budget.started() };
    let diagnostic_starts: Vec<_> = runs.iter().map(|r| r.diagnostics.len()).collect();
    let result = catch_unwind(AssertUnwindSafe(|| -> Result<(), Error> {
        if let Some(pool) = pool {
            // Indexed collection joins every task before publishing a chunk/error.
            // Per-chain RNG and state are never shared across tasks.
            let results: Vec<_> = pool.install(|| {
                runs.par_iter_mut()
                    .enumerate()
                    .map(|(chain, run)| {
                        catch_unwind(AssertUnwindSafe(|| run.advance(end)))
                            .unwrap_or_else(|_| {
                                Err(Error::new(ErrorKind::Panic, "session transition panicked"))
                            })
                            .map_err(|e| e.at_chain(chain))
                    })
                    .collect()
            });
            for result in results {
                result?;
            }
        } else {
            for (chain, run) in runs.iter_mut().enumerate() {
                run.advance(end).map_err(|e| e.at_chain(chain))?;
            }
        }
        Ok(())
    }))
    .unwrap_or_else(|_| Err(Error::new(ErrorKind::Panic, "session transition panicked")));
    let completed: Vec<_> = runs.iter().map(|r| r.next_transition).collect();
    if let Err(error) = result {
        fail(progress, budget, &completed, &error);
        return Err(error);
    }
    let dimension = runs[0].dimension;
    let chains = runs
        .iter()
        .zip(diagnostic_starts)
        .map(|(r, start)| SessionChainChunk {
            samples: r.samples[retained_start * dimension..retained_end * dimension].to_vec(),
            diagnostics: r.diagnostics[start..].to_vec(),
            telemetry: r.telemetry.clone(),
            mass_diagonal: r.active_mass.diagonal.clone(),
            tuning: r.active_tuning,
            effective_seed: r.seed,
        })
        .collect();
    let mut state = progress.lock().unwrap_or_else(|p| p.into_inner());
    state.completed_transitions = completed;
    state.target_calls = budget.started();
    Ok(SessionChunk {
        chains,
        dimension,
        retained_start,
        retained_end,
        is_warmup,
        target_calls: budget.started() - calls_before,
        cumulative_target_calls: budget.started(),
        initialization_target_calls: 0,
    })
}
