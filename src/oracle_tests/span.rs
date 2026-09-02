use crate::kernel::{
    BuildSpanResult, Direction, FixedTuning, Rejection, ScriptedUniform01, Span, SpanStop,
    SpanTraceEvent, build_span_traced,
};
use crate::types::State;
use serde_json::Value;

const ORACLE: &str = include_str!("../../oracle/walnutpie/f5bba365/span_traces.json");
const ABS_TOL: f64 = 2e-14;
const REL_TOL: f64 = 2e-14;

fn number(value: &Value, field: &str) -> f64 {
    value[field]
        .as_f64()
        .unwrap_or_else(|| panic!("missing numeric field {field}"))
}

fn usize_field(value: &Value, field: &str) -> usize {
    value[field]
        .as_u64()
        .unwrap_or_else(|| panic!("missing integer field {field}")) as usize
}

fn numbers(value: &Value, field: &str) -> Vec<f64> {
    value[field]
        .as_array()
        .unwrap_or_else(|| panic!("missing array field {field}"))
        .iter()
        .map(|item| item.as_f64().expect("array value must be numeric"))
        .collect()
}

fn close(case: &str, field: &str, actual: f64, expected: f64) {
    let tolerance = ABS_TOL.max(REL_TOL * actual.abs().max(expected.abs()));
    assert!(
        (actual - expected).abs() <= tolerance,
        "{case} {field}: actual {actual:.17e}, expected {expected:.17e}, tolerance {tolerance:.3e}"
    );
}

fn close_vec(case: &str, field: &str, actual: &[f64], expected: &[f64]) {
    assert_eq!(actual.len(), expected.len(), "{case} {field} length");
    for (index, (&actual, &expected)) in actual.iter().zip(expected).enumerate() {
        close(case, &format!("{field}[{index}]"), actual, expected);
    }
}

fn direction(input: &Value) -> Direction {
    match input["direction"].as_str().expect("direction") {
        "forward" => Direction::Forward,
        "backward" => Direction::Backward,
        other => panic!("unknown direction {other}"),
    }
}

fn expected_events(case: &Value) -> &[Value] {
    case["trace"].as_array().expect("trace")
}

fn assert_event(case_name: &str, actual: &SpanTraceEvent, expected: &Value) {
    assert_eq!(
        actual.event,
        expected["event"].as_str().unwrap(),
        "{case_name}"
    );
    assert_eq!(
        actual.depth,
        expected["depth"].as_u64().map(|value| value as usize),
        "{case_name} {} depth",
        actual.event
    );
    assert_eq!(
        actual.flag,
        expected["flag"].as_bool().unwrap(),
        "{case_name} {} flag",
        actual.event
    );
    assert_eq!(
        actual.target_evaluations,
        usize_field(expected, "target_evaluations"),
        "{case_name} {} evaluations",
        actual.event
    );
    if let Some(value) = expected.get("uniform_draw") {
        close(
            case_name,
            "uniform_draw",
            actual.uniform_draw.expect("Rust combine draw"),
            value.as_f64().unwrap(),
        );
    } else {
        assert!(actual.uniform_draw.is_none());
    }
    if let Some(value) = expected.get("update_log_probability") {
        close(
            case_name,
            "update_log_probability",
            actual
                .update_log_probability
                .expect("Rust combine probability"),
            value.as_f64().unwrap(),
        );
    } else {
        assert!(actual.update_log_probability.is_none());
    }
    if let Some(value) = expected.get("forward_dot") {
        close(
            case_name,
            "forward_dot",
            actual.forward_dot.expect("Rust U-turn forward dot"),
            value.as_f64().unwrap(),
        );
        match expected.get("backward_dot").unwrap() {
            Value::Null => assert!(
                actual.backward_dot.is_none(),
                "{case_name} must preserve upstream U-turn short circuit"
            ),
            Value::Number(number) => close(
                case_name,
                "backward_dot",
                actual.backward_dot.expect("Rust U-turn backward dot"),
                number.as_f64().unwrap(),
            ),
            _ => panic!("invalid backward_dot"),
        }
    } else {
        assert!(actual.forward_dot.is_none());
        assert!(actual.backward_dot.is_none());
    }
}

#[test]
fn matches_every_validated_upstream_span_trace() {
    let document: Value = serde_json::from_str(ORACLE).expect("valid span oracle JSON");
    assert_eq!(
        document["upstream_commit"].as_str().unwrap(),
        "f5bba36529697c34567a2944be36b68e305c546d"
    );
    assert_eq!(
        document["schema"].as_str().unwrap(),
        "walnutpie-span-trace-oracle-v1"
    );

    for case in document["cases"].as_array().expect("cases") {
        let name = case["name"].as_str().expect("case name");
        let input = &case["input"];
        let expected_result = &case["result"];
        let theta = numbers(input, "theta");
        let rho = numbers(input, "rho");
        let precision = numbers(input, "precision");
        let inverse_mass = numbers(input, "inverse_mass");
        let log_prob = -0.5
            * theta
                .iter()
                .zip(&precision)
                .map(|(theta, precision)| precision * theta * theta)
                .sum::<f64>();
        let initial = State {
            theta: theta.clone(),
            rho,
            log_prob,
            grad: theta
                .iter()
                .zip(&precision)
                .map(|(theta, precision)| -precision * theta)
                .collect(),
        };
        let initial_span = Span::from_state(initial, &inverse_mass).unwrap();
        let tuning = FixedTuning {
            options: crate::kernel::KernelOptions::default(),
            step_size: number(input, "step"),
            max_refinement_levels: usize_field(input, "max_step_halvings"),
            min_micro_steps: usize_field(input, "min_micro_steps"),
            max_error: number(input, "max_error"),
            divergence_threshold: 1000.0,
        };
        let scripted_draws: Vec<f64> = expected_events(case)
            .iter()
            .filter_map(|event| event.get("uniform_draw").and_then(Value::as_f64))
            .collect();
        let mut rng = ScriptedUniform01::new(scripted_draws);
        let mut evaluations = 0;
        let mut eval = |position: &[f64]| {
            evaluations += 1;
            (
                -0.5 * position
                    .iter()
                    .zip(&precision)
                    .map(|(theta, precision)| precision * theta * theta)
                    .sum::<f64>(),
                position
                    .iter()
                    .zip(&precision)
                    .map(|(theta, precision)| -precision * theta)
                    .collect(),
            )
        };
        let traced = build_span_traced(
            &mut rng,
            &initial_span,
            &inverse_mass,
            tuning,
            direction(input),
            usize_field(input, "depth"),
            &mut eval,
        )
        .unwrap_or_else(|error| panic!("{name}: {error}"));

        assert_eq!(
            evaluations,
            usize_field(expected_result, "target_evaluations"),
            "{name} target evaluations"
        );
        assert_eq!(
            rng.consumed(),
            usize_field(expected_result, "rng_engine_calls"),
            "{name} scripted uniform consumption"
        );
        assert_eq!(
            traced.events.len(),
            expected_events(case).len(),
            "{name} trace length"
        );
        for (actual, expected) in traced.events.iter().zip(expected_events(case)) {
            assert_event(name, actual, expected);
        }
        assert_eq!(
            traced
                .events
                .iter()
                .filter(|event| event.event == "leaf")
                .count(),
            expected_events(case)
                .iter()
                .filter(|event| event["event"] == "leaf")
                .count(),
            "{name} leaf count"
        );

        match traced.result {
            BuildSpanResult::Built {
                span,
                leaves,
                evaluations: result_evaluations,
            } => {
                assert!(expected_result["success"].as_bool().unwrap(), "{name}");
                assert_eq!(leaves, 1usize << usize_field(input, "depth"), "{name}");
                assert_eq!(result_evaluations, evaluations, "{name}");
                close_vec(
                    name,
                    "theta_backward",
                    &span.backward.state.theta,
                    &numbers(expected_result, "theta_backward"),
                );
                close_vec(
                    name,
                    "rho_backward",
                    &span.backward.state.rho,
                    &numbers(expected_result, "rho_backward"),
                );
                close_vec(
                    name,
                    "theta_forward",
                    &span.forward.state.theta,
                    &numbers(expected_result, "theta_forward"),
                );
                close_vec(
                    name,
                    "rho_forward",
                    &span.forward.state.rho,
                    &numbers(expected_result, "rho_forward"),
                );
                close_vec(
                    name,
                    "selected_theta",
                    &span.selected.theta,
                    &numbers(expected_result, "selected_theta"),
                );
                close_vec(
                    name,
                    "selected_gradient",
                    &span.selected.grad,
                    &numbers(expected_result, "selected_gradient"),
                );
                close(
                    name,
                    "selected_logp_position",
                    span.selected.log_prob,
                    number(expected_result, "selected_logp_position"),
                );
                close(
                    name,
                    "log_weight_sum",
                    span.log_weight,
                    number(expected_result, "log_weight_sum"),
                );
                close(
                    name,
                    "backward_log_weight",
                    span.backward.log_joint,
                    number(expected_result, "backward_log_weight"),
                );
                close(
                    name,
                    "forward_log_weight",
                    span.forward.log_joint,
                    number(expected_result, "forward_log_weight"),
                );
            }
            BuildSpanResult::Stopped {
                cause,
                evaluations: result_evaluations,
            } => {
                assert!(!expected_result["success"].as_bool().unwrap(), "{name}");
                assert_eq!(result_evaluations, evaluations, "{name}");
                let expected_cause = if expected_events(case)
                    .iter()
                    .any(|event| event["event"] == "uturn" && event["flag"] == true)
                {
                    SpanStop::UTurn
                } else {
                    SpanStop::Leaf(Rejection::RefinementExhausted)
                };
                assert_eq!(cause, expected_cause, "{name} stop cause");
            }
        }
    }
}
