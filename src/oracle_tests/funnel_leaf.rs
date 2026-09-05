//! Differential oracle: every macro leaf in
//! `oracle/walnutpie/f5bba365_funnel_leaves/funnel_leaf_cases.json` was
//! produced by the unmodified upstream `walnutpie::detail::macro_step` on
//! Neal's 10-D funnel. The Rust kernel must reproduce the acceptance
//! decision, endpoint state, adaptation statistic, and total target-call
//! count of every case.

use crate::kernel::{Direction, FixedTuning, macro_leaf};
use crate::types::State;
use serde_json::Value;

const FIXTURE: &str =
    include_str!("../../oracle/walnutpie/f5bba365_funnel_leaves/funnel_leaf_cases.json");
const ABS_TOLERANCE: f64 = 1e-11;
const REL_TOLERANCE: f64 = 1e-11;

fn funnel(theta: &[f64]) -> (f64, Vec<f64>) {
    let dim = theta.len();
    let omega = theta[0];
    let inv_var = (-omega).exp();
    let sum_sq: f64 = theta[1..].iter().map(|x| x * x).sum();
    let log_prob = -omega * omega / 18.0 - 0.5 * (dim - 1) as f64 * omega - 0.5 * sum_sq * inv_var;
    let mut grad = vec![0.0; dim];
    grad[0] = -omega / 9.0 - 0.5 * (dim - 1) as f64 + 0.5 * sum_sq * inv_var;
    for i in 1..dim {
        grad[i] = -theta[i] * inv_var;
    }
    (log_prob, grad)
}

fn vector(value: &Value, field: &str) -> Vec<f64> {
    value[field]
        .as_array()
        .unwrap_or_else(|| panic!("missing array field {field}"))
        .iter()
        .map(|entry| entry.as_f64().expect("array entry must be numeric"))
        .collect()
}

fn close(actual: f64, expected: f64) -> bool {
    let tolerance = ABS_TOLERANCE.max(REL_TOLERANCE * expected.abs());
    (actual - expected).abs() <= tolerance
}

fn vector_close(actual: &[f64], expected: &[f64]) -> bool {
    actual.len() == expected.len()
        && actual
            .iter()
            .zip(expected)
            .all(|(actual, expected)| close(*actual, *expected))
}

#[test]
fn funnel_macro_leaves_match_upstream_reference() {
    let fixture: Value = serde_json::from_str(FIXTURE).expect("funnel oracle must be valid JSON");
    assert_eq!(
        fixture["upstream_commit"].as_str(),
        Some("f5bba36529697c34567a2944be36b68e305c546d")
    );
    let cases = fixture["cases"].as_array().expect("cases");
    assert!(
        cases.len() >= 4000,
        "oracle must contain at least 4000 leaves"
    );
    let mut mismatches = Vec::new();
    let mut accepted = 0usize;
    for case in cases {
        let index = case["index"].as_u64().expect("index");
        let input = &case["input"];
        let theta = vector(input, "theta");
        let rho = vector(input, "rho");
        let (log_prob, grad) = funnel(&theta);
        let start = State {
            theta,
            rho,
            log_prob,
            grad,
        };
        let tuning = FixedTuning {
            options: crate::kernel::KernelOptions::default(),
            reverse_coarsening_order: crate::kernel::ReverseCoarseningOrder::FinestToCoarsest,
            reverse_coarser_policy: crate::kernel::ReverseCoarserPolicy::StopOrbit,
            step_size: input["macro_step"].as_f64().expect("macro_step"),
            max_refinement_levels: input["max_step_halvings"].as_u64().expect("halvings") as usize,
            min_micro_steps: input["min_micro_steps"].as_u64().expect("min_micro_steps") as usize,
            max_error: input["max_error"].as_f64().expect("max_error"),
            divergence_threshold: 1000.0,
        };
        let direction = match case["direction"].as_str() {
            Some("forward") => Direction::Forward,
            Some("backward") => Direction::Backward,
            other => panic!("case {index}: unknown direction {other:?}"),
        };
        let inverse_mass = vec![1.0; start.theta.len()];
        let result = macro_leaf(&start, &inverse_mass, tuning, direction, &mut funnel)
            .unwrap_or_else(|error| panic!("case {index}: macro leaf failed: {error}"));
        let expected_accepted = case["accepted"].as_bool().expect("accepted");
        let expected_calls = case["target_evaluations"].as_u64().expect("calls") as usize;
        let mut reasons = Vec::new();
        if result.accepted() != expected_accepted {
            reasons.push(format!(
                "accepted {} (rust {:?}) vs upstream {}",
                result.accepted(),
                result.rejection,
                expected_accepted
            ));
        }
        if result.evaluations != expected_calls {
            reasons.push(format!(
                "target calls {} vs upstream {}",
                result.evaluations, expected_calls
            ));
        }
        if let Some(expected) = case["minimum_acceptance"].as_f64()
            && !close(result.adaptation_value, expected)
        {
            reasons.push(format!(
                "adaptation value {:.17e} vs upstream {:.17e}",
                result.adaptation_value, expected
            ));
        }
        if expected_accepted && let Some(end) = &result.end_state {
            if !vector_close(&end.theta, &vector(case, "theta")) {
                reasons.push("endpoint theta".into());
            }
            if !vector_close(&end.rho, &vector(case, "rho")) {
                reasons.push("endpoint rho".into());
            }
            if !vector_close(&end.grad, &vector(case, "gradient")) {
                reasons.push("endpoint gradient".into());
            }
            if !close(end.log_prob, case["logp_position"].as_f64().expect("logp")) {
                reasons.push("endpoint log density".into());
            }
        }
        if expected_accepted {
            accepted += 1;
        }
        if !reasons.is_empty() {
            mismatches.push(format!(
                "case {index} ({:?}, min {} levels {} error {}): {}",
                direction,
                tuning.min_micro_steps,
                tuning.max_refinement_levels,
                tuning.max_error,
                reasons.join("; ")
            ));
        }
    }
    assert!(accepted > 0);
    assert!(
        mismatches.is_empty(),
        "{} of {} funnel leaves disagree with upstream walnutpie; first 12:\n{}",
        mismatches.len(),
        cases.len(),
        mismatches
            .iter()
            .take(12)
            .cloned()
            .collect::<Vec<_>>()
            .join("\n")
    );
}
