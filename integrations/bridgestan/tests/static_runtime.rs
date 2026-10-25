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
