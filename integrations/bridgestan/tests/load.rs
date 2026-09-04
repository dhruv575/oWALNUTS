//! Loads the compiled Eight Schools BridgeStan model if present and checks the
//! `Target` contract: dimension, finite evaluations, exception mapping, and
//! concurrent evaluation under `STAN_THREADS=true`.
//!
//! The model is built by `python -c "import bridgestan; ..."` (see README);
//! the test is skipped, not failed, when the `.so` is absent so that
//! `cargo test` works on a checkout without a C++ toolchain.

use owalnuts::walnutpie::{Target, TargetErrorKind};
use owalnuts_bridgestan::{Execution, StanTarget, Threading, default_preload};
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
    if cfg!(windows) {
        assert_eq!(m.threading(), Threading::Serialised);
    } else {
        assert_eq!(m.threading(), m.compiled_threading());
    }
    assert_eq!(
        m.execution(),
        if cfg!(windows) {
            Execution::OwnedSerialised
        } else if m.threading() == Threading::Concurrent {
            Execution::DirectConcurrent
        } else {
            Execution::DirectSerialised
        }
    );
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
    assert_eq!(pool.requested_replicas(), 4);
    assert_eq!(pool.replicas(), if cfg!(windows) { 1 } else { 4 });
    assert_eq!(pool.effective_replicas(), pool.replicas());
    assert_eq!(
        pool.threading(),
        if cfg!(windows) {
            Threading::Serialised
        } else {
            Threading::Concurrent
        }
    );
    assert_eq!(
        pool.execution(),
        if cfg!(windows) {
            Execution::OwnedSerialised
        } else {
            Execution::ReplicatedConcurrent
        }
    );
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

#[test]
fn repeated_model_and_replica_load_drop_remains_evaluable() {
    use owalnuts_bridgestan::ReplicatedStanTarget;

    let so = PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("models/eight_schools_model.so");
    if !so.exists() {
        eprintln!("skipping: {} not built", so.display());
        return;
    }
    for cycle in 0..16 {
        let target =
            StanTarget::load(&so, &default_preload(), Some(DATA), 100 + cycle).expect("load");
        let mut gradient = vec![0.0; 10];
        assert!(
            target
                .log_density_gradient(&[0.0; 10], &mut gradient)
                .unwrap()
                .is_finite()
        );
        drop(target);

        let replicas =
            ReplicatedStanTarget::load(&so, &default_preload(), Some(DATA), 200 + cycle, 4)
                .expect("replicated load");
        assert!(
            replicas
                .log_density_gradient(&[0.0; 10], &mut gradient)
                .unwrap()
                .is_finite()
        );
        drop(replicas);
    }
}

#[test]
fn external_real_model_owned_worker_has_exact_parallel_parity() {
    use owalnuts_bridgestan::ReplicatedStanTarget;

    let Some(model_path) = std::env::var_os("OWALNUTS_BRIDGESTAN_REAL_MODEL").map(PathBuf::from)
    else {
        eprintln!("skipping: OWALNUTS_BRIDGESTAN_REAL_MODEL is not set");
        return;
    };
    let Some(data_path) = std::env::var_os("OWALNUTS_BRIDGESTAN_REAL_DATA").map(PathBuf::from)
    else {
        eprintln!("skipping: OWALNUTS_BRIDGESTAN_REAL_DATA is not set");
        return;
    };
    let data = std::fs::read_to_string(data_path).expect("read external model data");
    let direct =
        StanTarget::load(&model_path, &default_preload(), Some(&data), 991).expect("direct load");
    let replicated =
        ReplicatedStanTarget::load(&model_path, &default_preload(), Some(&data), 991, 4)
            .expect("replicated load");
    assert_eq!(replicated.requested_replicas(), 4);
    assert_eq!(replicated.replicas(), if cfg!(windows) { 1 } else { 4 });
    assert_eq!(replicated.effective_replicas(), replicated.replicas());
    if cfg!(windows) {
        assert_eq!(direct.threading(), Threading::Serialised);
        assert_eq!(replicated.threading(), Threading::Serialised);
        assert_eq!(direct.compiled_threading(), replicated.compiled_threading());
        assert_eq!(direct.execution(), Execution::OwnedSerialised);
        assert_eq!(replicated.execution(), Execution::OwnedSerialised);
    }
    assert_eq!(direct.dimension(), replicated.dimension());
    assert_eq!(direct.info(), replicated.info());
    assert_eq!(direct.param_unc_names(), replicated.param_unc_names());

    let dimension = direct.dimension();
    let (position, expected_value, expected_gradient) = [0.0, 0.1, -0.1, 0.5, -0.5]
        .into_iter()
        .find_map(|coordinate| {
            let position = vec![coordinate; dimension];
            let mut gradient = vec![0.0; dimension];
            direct
                .log_density_gradient(&position, &mut gradient)
                .ok()
                .map(|value| (position, value, gradient))
        })
        .expect("one deterministic external-model probe is valid");

    let observed: Vec<_> = std::thread::scope(|scope| {
        let handles: Vec<_> = (0..16)
            .map(|_| {
                let position = &position;
                let replicated = &replicated;
                scope.spawn(move || {
                    let mut gradient = vec![0.0; dimension];
                    let value = replicated
                        .log_density_gradient(position, &mut gradient)
                        .unwrap();
                    (value, gradient)
                })
            })
            .collect();
        handles
            .into_iter()
            .map(|handle| handle.join().unwrap())
            .collect()
    });
    assert!(
        observed
            .iter()
            .all(|(value, gradient)| *value == expected_value && *gradient == expected_gradient)
    );
    assert_eq!(replicated.calls(), 16);
}
