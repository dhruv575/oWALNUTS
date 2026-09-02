//! Loads the compiled Eight Schools BridgeStan model if present and checks the
//! `Target` contract: dimension, finite evaluations, exception mapping, and
//! concurrent evaluation under `STAN_THREADS=true`.
//!
//! The model is built by `python -c "import bridgestan; ..."` (see README);
//! the test is skipped, not failed, when the `.so` is absent so that
//! `cargo test` works on a checkout without a C++ toolchain.

use owalnuts::walnutpie::{Target, TargetErrorKind};
use owalnuts_bridgestan::{StanTarget, Threading, default_preload};
use std::path::PathBuf;

const DATA: &str = r#"{"J":8,"y":[28,8,-3,7,-1,1,18,12],"sigma":[15,10,16,11,9,11,10,18]}"#;

fn model() -> Option<StanTarget> {
    let so = PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("models/eight_schools_model.so");
    if !so.exists() {
        eprintln!("skipping: {} not built", so.display());
        return None;
    }
    Some(StanTarget::load(&so, &default_preload(), Some(DATA), 7).expect("load"))
}

#[test]
fn dimension_and_finite_evaluation() {
    let Some(m) = model() else { return };
    assert_eq!(m.dimension(), 10);
    let q = vec![0.0; 10];
    let mut g = vec![0.0; 10];
    let lp = m.log_density_gradient(&q, &mut g).expect("finite");
    assert!(lp.is_finite());
    assert!(g.iter().all(|x| x.is_finite()));
    assert_eq!(m.calls(), 1);
}

#[test]
fn dimension_mismatch_is_fatal() {
    let Some(m) = model() else { return };
    let mut g = vec![0.0; 10];
    let err = m.log_density_gradient(&[0.0; 9], &mut g).unwrap_err();
    assert_eq!(err.kind(), TargetErrorKind::Fatal);
}

#[test]
fn stan_domain_exception_is_recoverable() {
    let Some(m) = model() else { return };
    // Unconstrained log tau = +1e6 overflows exp -> Stan throws a domain error
    // ("Scale parameter is inf") which must map to a zero-density proposal.
    let mut q = vec![0.0; 10];
    q[1] = 1.0e6;
    let mut g = vec![0.0; 10];
    match m.log_density_gradient(&q, &mut g) {
        Err(e) => assert_eq!(e.kind(), TargetErrorKind::Recoverable, "{}", e.message()),
        Ok(lp) => panic!("expected a recoverable failure, got {lp}"),
    }
    assert_eq!(m.recoverable_failures(), 1);
}

#[test]
fn concurrent_evaluations_agree_with_serial() {
    let Some(m) = model() else { return };
    let points: Vec<Vec<f64>> = (0..64)
        .map(|i| {
            (0..10)
                .map(|j| ((i * 7 + j * 3) % 11) as f64 * 0.1 - 0.5)
                .collect()
        })
        .collect();
    let serial: Vec<(f64, Vec<f64>)> = points
        .iter()
        .map(|p| {
            let mut g = vec![0.0; 10];
            (m.log_density_gradient(p, &mut g).unwrap(), g)
        })
        .collect();
    let parallel: Vec<(f64, Vec<f64>)> = std::thread::scope(|s| {
        let handles: Vec<_> = points
            .chunks(8)
            .map(|chunk| {
                let m = &m;
                s.spawn(move || {
                    chunk
                        .iter()
                        .map(|p| {
                            let mut g = vec![0.0; 10];
                            (m.log_density_gradient(p, &mut g).unwrap(), g)
                        })
                        .collect::<Vec<_>>()
                })
            })
            .collect();
        handles
            .into_iter()
            .flat_map(|h| h.join().unwrap())
            .collect()
    });
    assert_eq!(serial, parallel);
    if m.threading() == Threading::Serialised {
        eprintln!("note: model built without STAN_THREADS; evaluations were serialised");
    }
}

#[test]
fn replicated_target_agrees_with_serial_and_counts_calls() {
    use owalnuts_bridgestan::ReplicatedStanTarget;
    let Some(m) = model() else { return };
    let so = PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("models/eight_schools_model.so");
    let pool = ReplicatedStanTarget::load(&so, &default_preload(), Some(DATA), 7, 4).expect("pool");
    assert_eq!(pool.replicas(), 4);
    assert_eq!(pool.dimension(), m.dimension());
    let points: Vec<Vec<f64>> = (0..64)
        .map(|i| {
            (0..10)
                .map(|j| ((i * 5 + j * 3) % 11) as f64 * 0.1 - 0.5)
                .collect()
        })
        .collect();
    let serial: Vec<(f64, Vec<f64>)> = points
        .iter()
        .map(|p| {
            let mut g = vec![0.0; 10];
            (m.log_density_gradient(p, &mut g).unwrap(), g)
        })
        .collect();
    let parallel: Vec<(f64, Vec<f64>)> = std::thread::scope(|s| {
        let handles: Vec<_> = points
            .chunks(16)
            .map(|chunk| {
                let pool = &pool;
                s.spawn(move || {
                    chunk
                        .iter()
                        .map(|p| {
                            let mut g = vec![0.0; 10];
                            (pool.log_density_gradient(p, &mut g).unwrap(), g)
                        })
                        .collect::<Vec<_>>()
                })
            })
            .collect();
        handles
            .into_iter()
            .flat_map(|h| h.join().unwrap())
            .collect()
    });
    assert_eq!(serial, parallel);
    assert_eq!(pool.calls(), 64);
    let mut g = vec![0.0; 10];
    assert!(matches!(
        pool.log_density_gradient(&[0.0; 9], &mut g)
            .unwrap_err()
            .kind(),
        TargetErrorKind::Fatal
    ));
}
