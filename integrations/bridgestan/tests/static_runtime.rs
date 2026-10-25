//! Opt-in Windows multi-replica dispatch for static-runtime DLLs
//! (`WindowsDispatch::ConcurrentIfStaticRuntime`).
//!
//! Needs real models, so it is skipped unless these are set:
//!
//! * `OWALNUTS_BRIDGESTAN_STATIC_MODEL`, `OWALNUTS_BRIDGESTAN_STATIC_TBB`,
//!   `OWALNUTS_BRIDGESTAN_STATIC_DATA`: a model DLL and private `tbb.dll`
//!   built by `tools/build_static_runtime.py`, plus its data;
//! * optionally `OWALNUTS_BRIDGESTAN_DYNAMIC_MODEL` and
//!   `OWALNUTS_BRIDGESTAN_DYNAMIC_TBB` (a stock build of the same model) to
//!   check the fallback to the owned worker.

use owalnuts::walnutpie::Target;
use owalnuts_bridgestan::{
    Execution, ReplicatedOptions, ReplicatedStanTarget, check_static_runtime,
};
use std::path::PathBuf;

fn env_path(name: &str) -> Option<PathBuf> {
    std::env::var_os(name).map(PathBuf::from)
}

fn static_assets() -> Option<(PathBuf, PathBuf, String)> {
    let (Some(model), Some(tbb), Some(data)) = (
        env_path("OWALNUTS_BRIDGESTAN_STATIC_MODEL"),
        env_path("OWALNUTS_BRIDGESTAN_STATIC_TBB"),
        env_path("OWALNUTS_BRIDGESTAN_STATIC_DATA"),
    ) else {
        eprintln!("skipping: OWALNUTS_BRIDGESTAN_STATIC_{{MODEL,TBB,DATA}} not set");
        return None;
    };
    Some((model, tbb, std::fs::read_to_string(data).expect("data")))
}

fn positions(dimension: usize) -> Vec<Vec<f64>> {
    (0..16)
        .map(|k| {
            (0..dimension)
                .map(|i| ((k * 7 + i * 3) % 11) as f64 / 11.0 - 0.5)
                .collect()
        })
        .collect()
}

#[test]
fn static_runtime_dlls_get_concurrent_replicas_with_identical_gradients() {
    let Some((model, tbb, data)) = static_assets() else {
        return;
    };
    let report = check_static_runtime(&model, std::slice::from_ref(&tbb)).expect("readable");
    assert!(report.passed(), "{:?}", report.problems);

    let owned = ReplicatedStanTarget::load(&model, std::slice::from_ref(&tbb), Some(&data), 1, 4)
        .expect("owned load");
    let concurrent = ReplicatedStanTarget::load_with_options(
        &model,
        std::slice::from_ref(&tbb),
        Some(&data),
        1,
        4,
        &ReplicatedOptions::concurrent_if_static_runtime(),
    )
    .expect("concurrent load");
    if cfg!(windows) {
        assert_eq!(owned.effective_replicas(), 1);
        assert_eq!(owned.execution(), Execution::OwnedSerialised);
        assert!(
            concurrent
                .static_runtime_report()
                .expect("checked")
                .passed()
        );
    }
    assert_eq!(concurrent.effective_replicas(), 4);
    assert_eq!(concurrent.execution(), Execution::ReplicatedConcurrent);

    let dimension = owned.dimension();
    let expected: Vec<(u64, Vec<u64>)> = positions(dimension)
        .iter()
        .map(|q| {
            let mut g = vec![0.0; dimension];
            let lp = owned.log_density_gradient(q, &mut g).expect("finite");
            (lp.to_bits(), g.iter().map(|x| x.to_bits()).collect())
        })
        .collect();
    std::thread::scope(|scope| {
        for _ in 0..4 {
            scope.spawn(|| {
                for _ in 0..50 {
                    for (q, want) in positions(dimension).iter().zip(&expected) {
                        let mut g = vec![0.0; dimension];
                        let lp = concurrent.log_density_gradient(q, &mut g).expect("finite");
                        assert_eq!(lp.to_bits(), want.0);
                        assert_eq!(g.iter().map(|x| x.to_bits()).collect::<Vec<_>>(), want.1);
                    }
                }
            });
        }
    });
    assert_eq!(concurrent.calls(), 4 * 50 * 16);
}

#[test]
fn dynamic_runtime_dlls_fall_back_to_the_owned_worker() {
    let (Some(model), Some(tbb), Some((_, _, data))) = (
        env_path("OWALNUTS_BRIDGESTAN_DYNAMIC_MODEL"),
        env_path("OWALNUTS_BRIDGESTAN_DYNAMIC_TBB"),
        static_assets(),
    ) else {
        eprintln!("skipping: dynamic model/tbb not set");
        return;
    };
    let target = ReplicatedStanTarget::load_with_options(
        &model,
        std::slice::from_ref(&tbb),
        Some(&data),
        1,
        4,
        &ReplicatedOptions::concurrent_if_static_runtime(),
    )
    .expect("load");
    if cfg!(windows) {
        let report = target.static_runtime_report().expect("checked");
        assert!(!report.passed());
        assert!(report.problems.iter().any(|p| p.contains("mingw runtime")));
        assert_eq!(target.effective_replicas(), 1);
        assert_eq!(target.execution(), Execution::OwnedSerialised);
    }
}

/// One evaluation as bits: `Ok(logp)` or the error kind and message, plus the
/// gradient buffer the caller sees afterwards.
type Observed = (Result<u64, (String, String)>, Vec<u64>);

fn observe(target: &ReplicatedStanTarget, q: &[f64], prefill: f64) -> Observed {
    let mut g = vec![prefill; q.len()];
    let outcome = target
        .log_density_gradient(q, &mut g)
        .map(f64::to_bits)
        .map_err(|e| (format!("{:?}", e.kind()), e.message().to_owned()));
    (outcome, g.iter().map(|x| x.to_bits()).collect())
}

/// Positions that fail recoverably, mixed with ordinary ones. `sigma` is the
/// last unconstrained coordinate of sblrc/arK: -1000 gives `sigma = 0` and a
/// NaN coordinate fails the argument checks (both Stan exceptions, which
/// leave the gradient unwritten); +1000 gives `sigma = inf` and a `-inf` log
/// density with a written gradient.
fn throwing_positions(dimension: usize) -> Vec<Vec<f64>> {
    let mut out = Vec::new();
    for base in positions(dimension).into_iter().take(4) {
        out.push(base.clone());
        for bad in [1000.0, -1000.0] {
            let mut q = base.clone();
            q[dimension - 1] = bad;
            out.push(q);
        }
        let mut q = base;
        q[0] = f64::NAN;
        out.push(q);
    }
    out
}

/// WP50E parity: on a recoverable Stan exception the owned worker returns a
/// zeroed gradient buffer; the direct static-runtime dispatch must return the
/// same bytes, whatever the caller prefilled (the kernel prefills NaN).
#[test]
fn recoverable_stan_exceptions_have_identical_outputs_under_both_dispatches() {
    let Some((model, tbb, data)) = static_assets() else {
        return;
    };
    let owned = ReplicatedStanTarget::load(&model, std::slice::from_ref(&tbb), Some(&data), 1, 4)
        .expect("owned load");
    let concurrent = ReplicatedStanTarget::load_with_options(
        &model,
        std::slice::from_ref(&tbb),
        Some(&data),
        1,
        4,
        &ReplicatedOptions::concurrent_if_static_runtime(),
    )
    .expect("concurrent load");
    assert_eq!(concurrent.execution(), Execution::ReplicatedConcurrent);
    if cfg!(windows) {
        assert_eq!(owned.execution(), Execution::OwnedSerialised);
    }

    let qs = throwing_positions(owned.dimension());
    let prefills = [f64::NAN, -7.25, f64::INFINITY];
    let expected: Vec<Vec<Observed>> = prefills
        .iter()
        .map(|&p| qs.iter().map(|q| observe(&owned, q, p)).collect())
        .collect();
    let stan_exceptions = expected[0]
        .iter()
        .filter(|(outcome, _)| {
            outcome.as_ref().is_err_and(|(kind, message)| {
                kind == "Recoverable" && message.starts_with("stan exception")
            })
        })
        .count();
    let recoverable = expected[0].iter().filter(|(o, _)| o.is_err()).count();
    assert_eq!((stan_exceptions, recoverable), (8, 12), "{:?}", expected[0]);
    if cfg!(windows) {
        // The owned worker's documented contract: the buffer does not depend
        // on the caller's prefill, and is zero after a Stan exception.
        for observed in &expected[1..] {
            assert_eq!(observed, &expected[0]);
        }
        for (outcome, g) in &expected[0] {
            if outcome
                .as_ref()
                .is_err_and(|(_, message)| message.starts_with("stan exception"))
            {
                assert!(g.iter().all(|&bits| bits == 0), "{g:?}");
            }
        }
    }

    // Single thread, then four threads so every replica is exercised.
    for (p, want) in prefills.iter().zip(&expected) {
        let got: Vec<Observed> = qs.iter().map(|q| observe(&concurrent, q, *p)).collect();
        assert_eq!(&got, want, "prefill {p}");
    }
    std::thread::scope(|scope| {
        for _ in 0..4 {
            scope.spawn(|| {
                for _ in 0..25 {
                    for (p, want) in prefills.iter().zip(&expected) {
                        for (q, w) in qs.iter().zip(want) {
                            assert_eq!(&observe(&concurrent, q, *p), w, "prefill {p}");
                        }
                    }
                }
            });
        }
    });
    if cfg!(windows) {
        assert_eq!(
            concurrent.recoverable_failures(),
            owned.recoverable_failures() * 101
        );
    }
}
