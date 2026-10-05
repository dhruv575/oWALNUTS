//! Exact transition identity, budgets and lifecycle of additive sessions.
use owalnuts::sampler::{Adaptation, Limits, Metric, Sampler, Target, TargetError, Tuning};
use owalnuts::walnutpie::{InitialStepSearchConfig, WarmupConfig};
use std::sync::{
    Arc, Mutex,
    atomic::{AtomicBool, AtomicUsize, Ordering},
};
use std::time::{Duration, Instant};

#[derive(Clone)]
struct Gaussian {
    calls: Arc<AtomicUsize>,
    fail: Arc<AtomicBool>,
}
impl Gaussian {
    fn new() -> Self {
        Self {
            calls: Arc::new(AtomicUsize::new(0)),
            fail: Arc::new(AtomicBool::new(false)),
        }
    }
}
impl Target for Gaussian {
    fn dimension(&self) -> usize {
        2
    }
    fn log_density_gradient(&self, q: &[f64], g: &mut [f64]) -> Result<f64, TargetError> {
        self.calls.fetch_add(1, Ordering::Relaxed);
        if self.fail.load(Ordering::Acquire) {
            return Err(TargetError::new("injected failure"));
        }
        g[0] = -q[0];
        g[1] = -q[1] / 3.;
        Ok(-0.5 * (q[0] * q[0] + q[1] * q[1] / 3.))
    }
}
fn sampler(cache: bool) -> Sampler {
    Sampler::new()
        .warmup(60)
        .draws(13)
        .threads(1)
        .seed(12345)
        .tuning(Tuning::default().max_depth(5))
        .cache_initial_evaluation(cache)
        .adaptation(Adaptation::Custom(
            WarmupConfig::new(0.8)
                .unwrap()
                .with_initial_step_search(InitialStepSearchConfig::stan()),
        ))
}
fn starts() -> Vec<Vec<f64>> {
    vec![vec![0.1, -0.3], vec![-0.2, 0.4]]
}

#[test]
fn uneven_chunks_match_uninterrupted_rng_adaptation_diagnostics_and_calls() {
    for cache in [false, true] {
        let target = Gaussian::new();
        let full = sampler(cache).run(&target, &starts()).unwrap();
        let expected_calls = target.calls.load(Ordering::Relaxed);
        let target = Gaussian::new();
        let calls = Arc::clone(&target.calls);
        let session = sampler(cache).start_session(target, &starts()).unwrap();
        assert_eq!(calls.load(Ordering::Relaxed), 0);
        assert!(session.draw(1).is_err());
        let warmup = session.adapt().unwrap();
        assert!(warmup.initialization_target_calls > 0);
        assert_eq!(
            warmup.initialization_target_calls,
            warmup.chains[0]
                .telemetry
                .initial_step_search()
                .unwrap()
                .target_calls()
        );
        assert!(warmup.target_calls >= warmup.initialization_target_calls);
        assert!(session.adapt().is_err());
        assert!(session.draw(0).is_err());
        assert!(session.draw(14).is_err());
        let a = session.draw(1).unwrap();
        let b = session.draw(5).unwrap();
        let c = session.draw(7).unwrap();
        assert_eq!(
            a.initialization_target_calls
                + b.initialization_target_calls
                + c.initialization_target_calls,
            0
        );
        assert_eq!((a.retained_start, a.retained_end), (0, 1));
        assert_eq!((b.retained_start, b.retained_end), (1, 6));
        assert_eq!((c.retained_start, c.retained_end), (6, 13));
        for i in 0..2 {
            let samples = [
                a.chains[i].samples.clone(),
                b.chains[i].samples.clone(),
                c.chains[i].samples.clone(),
            ]
            .concat();
            let diagnostics = [
                warmup.chains[i].diagnostics.clone(),
                a.chains[i].diagnostics.clone(),
                b.chains[i].diagnostics.clone(),
                c.chains[i].diagnostics.clone(),
            ]
            .concat();
            assert_eq!(samples, full.chains()[i].samples());
            assert_eq!(diagnostics, full.chains()[i].diagnostics());
            assert_eq!(&c.chains[i].telemetry, full.chains()[i].telemetry());
            assert_eq!(
                c.chains[i].mass_diagonal,
                full.chains()[i].metadata().mass_diagonal()
            );
            assert_eq!(&c.chains[i].tuning, full.chains()[i].metadata().tuning());
        }
        assert_eq!(calls.load(Ordering::Relaxed), expected_calls);
        assert_eq!(c.cumulative_target_calls, expected_calls);
        assert_eq!(
            warmup.target_calls + a.target_calls + b.target_calls + c.target_calls,
            expected_calls
        );
        assert!(session.draw(1).is_err());
        session.close().unwrap();
        session.close().unwrap();
    }
}

#[test]
fn failed_execution_is_terminal_but_invalid_request_is_not() {
    let target = Gaussian::new();
    let fail = Arc::clone(&target.fail);
    let session = sampler(true).start_session(target, &starts()).unwrap();
    session.adapt().unwrap();
    session.draw(2).unwrap();
    let before = session.progress().target_calls;
    assert!(session.draw(20).is_err());
    assert_eq!(session.progress().target_calls, before);
    fail.store(true, Ordering::Release);
    assert!(session.draw(1).is_err());
    assert!(session.progress().failed);
    assert!(session.progress().target_calls > before);
    assert!(session.draw(1).is_err());
    session.close().unwrap();
}

#[test]
fn unsupported_configuration_and_admission_make_zero_target_calls() {
    let target = Gaussian::new();
    let calls = Arc::clone(&target.calls);
    assert!(
        sampler(true)
            .threads(0)
            .start_session(target.clone(), &starts())
            .is_err()
    );
    assert!(
        sampler(true)
            .metric(Metric::dense())
            .start_session(target.clone(), &starts())
            .is_err()
    );
    assert!(
        sampler(true)
            .limits(Limits::new().max_target_evaluations(1))
            .start_session(target.clone(), &starts())
            .is_err()
    );
    assert!(
        sampler(true)
            .start_session(target.clone(), &[vec![f64::NAN, 0.]])
            .is_err()
    );
    assert_eq!(calls.load(Ordering::Relaxed), 0);
}

#[test]
fn cancellation_and_reentrancy_do_not_release_a_live_target() {
    struct Blocking {
        entered: Arc<AtomicBool>,
        release: Arc<AtomicBool>,
        dropped: Arc<AtomicBool>,
    }
    impl Target for Blocking {
        fn dimension(&self) -> usize {
            2
        }
        fn log_density_gradient(&self, q: &[f64], g: &mut [f64]) -> Result<f64, TargetError> {
            self.entered.store(true, Ordering::Release);
            let deadline = Instant::now() + Duration::from_secs(5);
            while !self.release.load(Ordering::Acquire) {
                if Instant::now() > deadline {
                    return Err(TargetError::new("test callback deadline"));
                }
                std::thread::yield_now();
            }
            g[0] = -q[0];
            g[1] = -q[1];
            Ok(-0.5 * (q[0] * q[0] + q[1] * q[1]))
        }
    }
    impl Drop for Blocking {
        fn drop(&mut self) {
            self.dropped.store(true, Ordering::Release);
        }
    }
    let entered = Arc::new(AtomicBool::new(false));
    let release = Arc::new(AtomicBool::new(false));
    let dropped = Arc::new(AtomicBool::new(false));
    let session = Arc::new(
        sampler(true)
            .start_session(
                Blocking {
                    entered: entered.clone(),
                    release: release.clone(),
                    dropped: dropped.clone(),
                },
                &starts(),
            )
            .unwrap(),
    );
    let request = Arc::clone(&session);
    let waiter = std::thread::spawn(move || request.adapt());
    let deadline = Instant::now() + Duration::from_secs(3);
    while !entered.load(Ordering::Acquire) {
        assert!(Instant::now() < deadline);
        std::thread::yield_now();
    }
    assert!(session.draw(1).is_err());
    session.cancel();
    assert!(!dropped.load(Ordering::Acquire));
    release.store(true, Ordering::Release);
    assert!(waiter.join().unwrap().is_err());
    session.close().unwrap();
    assert!(dropped.load(Ordering::Acquire));
    assert!(session.progress().closed);
}

#[test]
fn conservative_admission_has_no_hidden_constructor_callbacks() {
    let target = Gaussian::new();
    let calls = Arc::clone(&target.calls);
    let session = Sampler::new()
        .warmup(0)
        .draws(2)
        .threads(1)
        .adaptation(Adaptation::None)
        .metric(Metric::Identity)
        .tuning(Tuning::default().max_depth(2).max_refinement_levels(1))
        .limits(Limits::new().admit_conservative())
        .start_session(target, &starts())
        .unwrap();
    assert_eq!(calls.load(Ordering::Relaxed), 0);
    let warmup = session.adapt().unwrap();
    let chunk = session.draw(2).unwrap();
    assert_eq!(
        warmup.target_calls + chunk.target_calls,
        calls.load(Ordering::Relaxed)
    );
    assert_eq!(chunk.cumulative_target_calls, calls.load(Ordering::Relaxed));
    session.close().unwrap();
}

#[test]
fn callback_panic_is_terminal_and_reports_started_work() {
    struct Panic;
    impl Target for Panic {
        fn dimension(&self) -> usize {
            2
        }
        fn log_density_gradient(&self, _: &[f64], _: &mut [f64]) -> Result<f64, TargetError> {
            panic!("injected callback panic")
        }
    }
    let session = sampler(true).start_session(Panic, &starts()).unwrap();
    assert!(session.adapt().is_err());
    session.close().unwrap();
    let state = session.progress();
    assert!(state.failed);
    assert!(state.closed);
    assert!(state.target_calls > 0);
}

#[test]
fn callback_close_cancels_without_joining_itself_and_external_close_reaps() {
    use owalnuts::sampler::SessionHandle;
    struct Reentrant {
        handle: Arc<Mutex<Option<Arc<SessionHandle>>>>,
        saw_error: Arc<AtomicBool>,
        dropped: Arc<AtomicBool>,
    }
    impl Target for Reentrant {
        fn dimension(&self) -> usize {
            2
        }
        fn log_density_gradient(&self, q: &[f64], g: &mut [f64]) -> Result<f64, TargetError> {
            let session = self
                .handle
                .lock()
                .unwrap()
                .take()
                .expect("test session assigned before adapt");
            session.cancel();
            let error = session
                .close()
                .expect_err("self-close must reject joining the current worker");
            self.saw_error
                .store(error.to_string().contains("own worker"), Ordering::Release);
            assert!(!self.dropped.load(Ordering::Acquire));
            g[0] = -q[0];
            g[1] = -q[1];
            Ok(-0.5 * (q[0] * q[0] + q[1] * q[1]))
        }
    }
    impl Drop for Reentrant {
        fn drop(&mut self) {
            self.dropped.store(true, Ordering::Release);
        }
    }
    let slot = Arc::new(Mutex::new(None));
    let saw_error = Arc::new(AtomicBool::new(false));
    let dropped = Arc::new(AtomicBool::new(false));
    let session = Arc::new(
        sampler(true)
            .start_session(
                Reentrant {
                    handle: slot.clone(),
                    saw_error: saw_error.clone(),
                    dropped: dropped.clone(),
                },
                &starts(),
            )
            .unwrap(),
    );
    *slot.lock().unwrap() = Some(session.clone());
    assert!(session.adapt().is_err());
    session.close().unwrap();
    assert!(saw_error.load(Ordering::Acquire));
    assert!(dropped.load(Ordering::Acquire));
    assert!(session.progress().closed);
}

#[test]
fn parallel_four_chains_match_sequential_chunks_and_ordinary_run() {
    let starts = vec![
        vec![0.1, -0.3],
        vec![-0.2, 0.4],
        vec![0.7, 0.8],
        vec![-0.8, -0.6],
    ];
    for cache in [false, true] {
        let full = sampler(cache)
            .threads(4)
            .run(&Gaussian::new(), &starts)
            .unwrap();
        let seq = sampler(cache)
            .start_session(Gaussian::new(), &starts)
            .unwrap();
        let par = sampler(cache)
            .threads(4)
            .start_session(Gaussian::new(), &starts)
            .unwrap();
        let sw = seq.adapt().unwrap();
        let pw = par.adapt().unwrap();
        assert_eq!(sw.target_calls, pw.target_calls);
        for i in 0..4 {
            assert_eq!(sw.chains[i].diagnostics, pw.chains[i].diagnostics);
        }
        let mut samples = vec![Vec::new(); 4];
        for n in [1, 5, 7] {
            let a = seq.draw(n).unwrap();
            let b = par.draw(n).unwrap();
            assert_eq!(a.target_calls, b.target_calls);
            assert_eq!(a.cumulative_target_calls, b.cumulative_target_calls);
            for i in 0..4 {
                assert_eq!(a.chains[i].samples, b.chains[i].samples);
                assert_eq!(a.chains[i].diagnostics, b.chains[i].diagnostics);
                assert_eq!(a.chains[i].telemetry, b.chains[i].telemetry);
                assert_eq!(a.chains[i].mass_diagonal, b.chains[i].mass_diagonal);
                assert_eq!(a.chains[i].tuning, b.chains[i].tuning);
                samples[i].extend_from_slice(&b.chains[i].samples);
            }
        }
        for i in 0..4 {
            assert_eq!(samples[i], full.chains()[i].samples());
        }
        seq.close().unwrap();
        par.close().unwrap();
    }
}

#[test]
fn parallel_callback_close_does_not_join_coordinator() {
    use owalnuts::sampler::SessionHandle;
    struct Reentrant {
        slot: Arc<Mutex<Option<Arc<SessionHandle>>>>,
        saw: Arc<AtomicBool>,
    }
    impl Target for Reentrant {
        fn dimension(&self) -> usize {
            2
        }
        fn log_density_gradient(&self, q: &[f64], g: &mut [f64]) -> Result<f64, TargetError> {
            if let Some(handle) = self.slot.lock().unwrap().take() {
                assert!(handle.close().is_err());
                self.saw.store(true, Ordering::Release);
            }
            g[0] = -q[0];
            g[1] = -q[1];
            Ok(-0.5 * (q[0] * q[0] + q[1] * q[1]))
        }
    }
    let slot = Arc::new(Mutex::new(None));
    let saw = Arc::new(AtomicBool::new(false));
    let handle = Arc::new(
        sampler(true)
            .threads(4)
            .start_session(
                Reentrant {
                    slot: slot.clone(),
                    saw: saw.clone(),
                },
                &starts(),
            )
            .unwrap(),
    );
    handle.adapt().unwrap();
    *slot.lock().unwrap() = Some(handle.clone());
    assert!(handle.draw(1).is_err());
    handle.close().unwrap();
    assert!(saw.load(Ordering::Acquire));
    assert!(handle.progress().closed);
}
#[test]
fn parallel_callbacks_overlap_cancel_joins_and_global_budget_is_bounded() {
    use std::sync::Barrier;
    struct Concurrent {
        armed: Arc<AtomicBool>,
        entered: Arc<AtomicUsize>,
        active: Arc<AtomicUsize>,
        calls: Arc<AtomicUsize>,
        release: Arc<AtomicBool>,
        dropped: Arc<AtomicBool>,
        barrier: Arc<Barrier>,
    }
    impl Target for Concurrent {
        fn dimension(&self) -> usize {
            2
        }
        fn log_density_gradient(&self, q: &[f64], g: &mut [f64]) -> Result<f64, TargetError> {
            self.calls.fetch_add(1, Ordering::AcqRel);
            if self.armed.load(Ordering::Acquire) {
                self.active.fetch_add(1, Ordering::AcqRel);
                self.entered.fetch_add(1, Ordering::AcqRel);
                self.barrier.wait();
                let deadline = Instant::now() + Duration::from_secs(5);
                while !self.release.load(Ordering::Acquire) {
                    assert!(Instant::now() < deadline, "callback test deadline");
                    std::thread::yield_now();
                }
                self.active.fetch_sub(1, Ordering::AcqRel);
            }
            g[0] = -q[0];
            g[1] = -q[1];
            Ok(-0.5 * (q[0] * q[0] + q[1] * q[1]))
        }
    }
    impl Drop for Concurrent {
        fn drop(&mut self) {
            assert_eq!(self.active.load(Ordering::Acquire), 0);
            self.dropped.store(true, Ordering::Release);
        }
    }
    let armed = Arc::new(AtomicBool::new(false));
    let entered = Arc::new(AtomicUsize::new(0));
    let active = Arc::new(AtomicUsize::new(0));
    let calls = Arc::new(AtomicUsize::new(0));
    let release = Arc::new(AtomicBool::new(false));
    let dropped = Arc::new(AtomicBool::new(false));
    let builder = sampler(true).threads(4);
    let budget = builder.worst_case_target_evaluations(4).unwrap();
    let starts = vec![vec![0.1, 0.2]; 4];
    let handle = Arc::new(
        sampler(true)
            .threads(4)
            .limits(Limits::new().max_target_evaluations(budget))
            .start_session(
                Concurrent {
                    armed: armed.clone(),
                    entered: entered.clone(),
                    active: active.clone(),
                    calls: calls.clone(),
                    release: release.clone(),
                    dropped: dropped.clone(),
                    barrier: Arc::new(Barrier::new(4)),
                },
                &starts,
            )
            .unwrap(),
    );
    handle.adapt().unwrap();
    armed.store(true, Ordering::Release);
    let worker = handle.clone();
    let request = std::thread::spawn(move || worker.draw(1));
    let deadline = Instant::now() + Duration::from_secs(5);
    while entered.load(Ordering::Acquire) < 4 {
        assert!(Instant::now() < deadline);
        std::thread::yield_now();
    }
    assert_eq!(active.load(Ordering::Acquire), 4);
    handle.cancel();
    assert!(!dropped.load(Ordering::Acquire));
    release.store(true, Ordering::Release);
    assert!(request.join().unwrap().is_err());
    assert_eq!(active.load(Ordering::Acquire), 0);
    handle.close().unwrap();
    assert!(dropped.load(Ordering::Acquire));
    assert!(calls.load(Ordering::Acquire) <= budget);
    assert_eq!(
        handle.progress().target_calls,
        calls.load(Ordering::Acquire)
    );
}
#[test]
fn parallel_callback_error_is_terminal_and_target_drops_after_join() {
    struct Failing {
        inner: Gaussian,
        panic_mode: bool,
        dropped: Arc<AtomicBool>,
    }
    impl Target for Failing {
        fn dimension(&self) -> usize {
            2
        }
        fn log_density_gradient(&self, q: &[f64], g: &mut [f64]) -> Result<f64, TargetError> {
            if self.panic_mode && self.inner.fail.load(Ordering::Acquire) {
                self.inner.calls.fetch_add(1, Ordering::Relaxed);
                panic!("parallel injected panic");
            }
            self.inner.log_density_gradient(q, g)
        }
    }
    impl Drop for Failing {
        fn drop(&mut self) {
            self.dropped.store(true, Ordering::Release);
        }
    }
    for panic_mode in [false, true] {
        let inner = Gaussian::new();
        let fail = inner.fail.clone();
        let calls = inner.calls.clone();
        let dropped = Arc::new(AtomicBool::new(false));
        let session = sampler(true)
            .threads(4)
            .start_session(
                Failing {
                    inner,
                    panic_mode,
                    dropped: dropped.clone(),
                },
                &vec![vec![0.1, 0.2]; 4],
            )
            .unwrap();
        session.adapt().unwrap();
        fail.store(true, Ordering::Release);
        assert!(session.draw(1).is_err());
        assert!(session.progress().failed);
        assert!(session.draw(1).is_err());
        session.close().unwrap();
        assert!(dropped.load(Ordering::Acquire));
        assert!(session.progress().closed);
        assert_eq!(
            calls.load(Ordering::Acquire),
            session.progress().target_calls
        );
    }
}
