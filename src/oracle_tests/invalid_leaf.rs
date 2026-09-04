//! Differential oracle for zero-density (failed-evaluation) semantics: every
//! macro leaf in `oracle/walnutpie/f5bba365_invalid_leaves/invalid_leaf_cases.json`
//! was produced by the unmodified upstream `walnutpie::detail::macro_step` on
//! Neal's 10-D funnel with a hard wall, where the upstream `NoExceptLogpGrad`
//! wrapper maps a throwing evaluation to `logp = -inf`, `grad = 0`. The Rust
//! kernel, fed `(-inf, 0)` inside the wall, must reproduce the acceptance
//! decision, endpoint state, adaptation statistic, total target-call count,
//! and the number of zero-density calls of every case.

use crate::kernel::{Direction, FixedTuning, TransitionWorkTelemetry, macro_leaf_observed};
use crate::types::State;
use serde_json::Value;

const FIXTURE: &str =
    include_str!("../../oracle/walnutpie/f5bba365_invalid_leaves/invalid_leaf_cases.json");
const ABS_TOLERANCE: f64 = 1e-11;
const REL_TOLERANCE: f64 = 1e-11;

#[derive(Clone, Copy)]
enum Wall {
    NeckOmega,
    BodyX1,
}

fn inside(wall: Wall, theta: &[f64]) -> bool {
    match wall {
        Wall::NeckOmega => theta[0] < -7.0,
        Wall::BodyX1 => theta[1] > 0.8,
    }
}

fn wall_funnel(wall: Wall, theta: &[f64]) -> (f64, Vec<f64>) {
    if inside(wall, theta) {
        return (f64::NEG_INFINITY, vec![0.0; theta.len()]);
    }
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
fn zero_density_macro_leaves_match_upstream_reference() {
    let fixture: Value =
        serde_json::from_str(FIXTURE).expect("invalid-leaf oracle must be valid JSON");
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
    let mut touched_wall = 0usize;
    let mut accepted_through_wall = 0usize;
    for case in cases {
        let index = case["index"].as_u64().expect("index");
        let wall = match case["wall"].as_str() {
            Some("neck_omega") => Wall::NeckOmega,
            Some("body_x1") => Wall::BodyX1,
            other => panic!("case {index}: unknown wall {other:?}"),
        };
        let input = &case["input"];
        let theta = vector(input, "theta");
        let rho = vector(input, "rho");
        let (log_prob, grad) = wall_funnel(wall, &theta);
        assert!(log_prob.is_finite(), "case {index}: start must be valid");
        let start = State {
            theta,
            rho,
            log_prob,
            grad,
        };
        let tuning = FixedTuning {
            options: crate::kernel::KernelOptions::default(),
            reverse_coarsening_order: crate::kernel::ReverseCoarseningOrder::FinestToCoarsest,
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
        let mut work = TransitionWorkTelemetry::default();
        let mut zero_density_calls = 0usize;
        let result = macro_leaf_observed(
            &start,
            &inverse_mass,
            tuning,
            direction,
            &mut |theta: &[f64]| {
                let value = wall_funnel(wall, theta);
                if value.0 == f64::NEG_INFINITY {
                    zero_density_calls += 1;
                }
                value
            },
            &mut work,
        )
        .unwrap_or_else(|error| panic!("case {index}: macro leaf failed: {error}"));
        let expected_accepted = case["accepted"].as_bool().expect("accepted");
        let expected_calls = case["target_evaluations"].as_u64().expect("calls") as usize;
        let expected_zero_density = case["zero_density_evaluations"]
            .as_u64()
            .expect("zero density") as usize;
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
        if zero_density_calls != expected_zero_density
            || work.zero_density_evaluations != expected_zero_density
        {
            reasons.push(format!(
                "zero-density calls {} (telemetry {}) vs upstream {}",
                zero_density_calls, work.zero_density_evaluations, expected_zero_density
            ));
        }
        if work.rejections.invalid_forward_evaluation != 0
            || work.rejections.invalid_reverse_evaluation != 0
        {
            reasons.push("zero-density point classified as an invalid evaluation".into());
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
        if expected_zero_density > 0 {
            touched_wall += 1;
            if expected_accepted {
                accepted_through_wall += 1;
            }
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
        touched_wall >= 200,
        "oracle must exercise the wall ({touched_wall} leaves touched it)"
    );
    assert!(
        accepted_through_wall > 0,
        "oracle must contain leaves accepted after refining away from the wall"
    );
    assert!(
        mismatches.is_empty(),
        "{} of {} zero-density leaves disagree with upstream walnutpie; first 12:\n{}",
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
