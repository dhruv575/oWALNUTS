//! Numerical agreement with ArviZ from `tests/data/arviz_fixture.json`
//! (regenerate with `tests/data/generate_arviz_fixture.py`).

use owalnuts::diagnostics::{
    ess_bulk, ess_mean, ess_quantile, ess_tail, mcse_mean, mean, quantile, rhat, sd,
};
use serde_json::Value;

const RELATIVE_TOLERANCE: f64 = 1e-6;

fn close(actual: f64, expected: Option<f64>, what: &str, case: &str) {
    match expected {
        None => assert!(actual.is_nan(), "{case}: {what} expected NaN, got {actual}"),
        Some(expected) => {
            let scale = expected.abs().max(1e-12);
            assert!(
                (actual - expected).abs() <= RELATIVE_TOLERANCE * scale,
                "{case}: {what} expected {expected}, got {actual}"
            );
        }
    }
}

#[test]
fn estimators_match_arviz_fixture() {
    let fixture: Value =
        serde_json::from_str(include_str!("data/arviz_fixture.json")).expect("valid fixture");
    let cases = fixture["cases"].as_array().expect("cases");
    assert!(cases.len() >= 9);
    for case in cases {
        let name = case["name"].as_str().unwrap();
        let chains: Vec<Vec<f64>> = case["chains"]
            .as_array()
            .unwrap()
            .iter()
            .map(|chain| {
                chain
                    .as_array()
                    .unwrap()
                    .iter()
                    .map(|v| v.as_f64().unwrap())
                    .collect()
            })
            .collect();
        let views: Vec<&[f64]> = chains.iter().map(Vec::as_slice).collect();
        let expected = |key: &str| case[key].as_f64();
        close(rhat(&views), expected("rhat"), "rhat", name);
        close(ess_bulk(&views), expected("ess_bulk"), "ess_bulk", name);
        close(ess_tail(&views), expected("ess_tail"), "ess_tail", name);
        close(ess_mean(&views), expected("ess_mean"), "ess_mean", name);
        close(
            ess_quantile(&views, 0.05),
            expected("ess_q05"),
            "ess_q05",
            name,
        );
        close(mcse_mean(&views), expected("mcse_mean"), "mcse_mean", name);
        close(mean(&views), expected("mean"), "mean", name);
        close(sd(&views), expected("sd"), "sd", name);
        close(quantile(&views, 0.05), expected("q05"), "q05", name);
        close(quantile(&views, 0.5), expected("q50"), "q50", name);
        close(quantile(&views, 0.95), expected("q95"), "q95", name);
    }
}
