use crate::kernel::{Direction, FixedTuning, Rejection, macro_leaf};
use crate::types::State;
use serde_json::Value;

const FIXTURE: &str = include_str!("../../oracle/walnutpie/f5bba365/gaussian_cases.json");
const ABS_TOLERANCE: f64 = 1e-12;
const REL_TOLERANCE: f64 = 1e-12;

fn number(value: &Value, field: &str) -> f64 {
    value[field]
        .as_f64()
        .unwrap_or_else(|| panic!("missing numeric field {field}"))
}

fn count(value: &Value, field: &str) -> usize {
    value[field]
        .as_u64()
        .unwrap_or_else(|| panic!("missing integer field {field}")) as usize
}

fn vector(value: &Value, field: &str) -> Vec<f64> {
    value[field]
        .as_array()
        .unwrap_or_else(|| panic!("missing array field {field}"))
        .iter()
        .map(|entry| entry.as_f64().expect("array entry must be numeric"))
        .collect()
}

fn assert_close(case: &str, field: &str, actual: f64, expected: f64) {
    let tolerance = ABS_TOLERANCE.max(REL_TOLERANCE * expected.abs());
    assert!(
        (actual - expected).abs() <= tolerance,
        "{case}.{field}: expected {expected:.17e}, got {actual:.17e} \
         (absolute difference {:.3e}, tolerance {tolerance:.3e})",
        (actual - expected).abs()
    );
}

fn assert_vector_close(case: &str, field: &str, actual: &[f64], expected: &[f64]) {
    assert_eq!(
        actual.len(),
        expected.len(),
        "{case}.{field}: dimension mismatch"
    );
    for (index, (&actual, &expected)) in actual.iter().zip(expected).enumerate() {
        assert_close(case, &format!("{field}[{index}]"), actual, expected);
    }
}

fn check_case(requested_name: &str) {
    let fixture: Value = serde_json::from_str(FIXTURE).expect("oracle fixture must be valid JSON");
    assert_eq!(
        fixture["upstream_commit"].as_str(),
        Some("f5bba36529697c34567a2944be36b68e305c546d")
    );
    let cases = fixture["cases"]
        .as_array()
        .expect("oracle fixture must contain cases");
    let matches: Vec<_> = cases
        .iter()
        .filter(|case| case["name"].as_str() == Some(requested_name))
        .collect();
    assert_eq!(
        matches.len(),
        1,
        "fixture case {requested_name} must be unique"
    );

    for case in matches {
        let name = case["name"].as_str().expect("case must have a name");
        let input = &case["input"];
        let theta = vector(input, "theta");
        let rho = vector(input, "rho");
        let precision = vector(input, "precision");
        let inverse_mass = vector(input, "inverse_mass");
        let log_prob = -0.5
            * theta
                .iter()
                .zip(&precision)
                .map(|(theta, precision)| precision * theta * theta)
                .sum::<f64>();
        let grad = theta
            .iter()
            .zip(&precision)
            .map(|(theta, precision)| -precision * theta)
            .collect();
        let start = State {
            theta,
            rho,
            log_prob,
            grad,
        };
        let tuning = FixedTuning {
            step_size: number(input, "macro_step"),
            max_refinement_levels: count(input, "max_step_halvings"),
            min_micro_steps: count(input, "min_micro_steps"),
            max_error: number(input, "max_error"),
            divergence_threshold: 1000.0,
        };
        let direction = match case["direction"].as_str() {
            Some("forward") => Direction::Forward,
            Some("backward") => Direction::Backward,
            other => panic!("{name}: unknown direction {other:?}"),
        };
        let mut gaussian = |theta: &[f64]| {
            let log_prob = -0.5
                * theta
                    .iter()
                    .zip(&precision)
                    .map(|(theta, precision)| precision * theta * theta)
                    .sum::<f64>();
            let gradient = theta
                .iter()
                .zip(&precision)
                .map(|(theta, precision)| -precision * theta)
                .collect();
            (log_prob, gradient)
        };

        let result = macro_leaf(&start, &inverse_mass, tuning, direction, &mut gaussian)
            .unwrap_or_else(|error| panic!("{name}: Rust macro leaf failed: {error}"));
        let expected_category = match case["observed_category"].as_str() {
            Some("refinement_exhausted") => Some(Rejection::RefinementExhausted),
            Some("reverse_coarser_accepted") => Some(Rejection::ReverseCoarserAccepted),
            Some("accepted") => None,
            other => panic!("{name}: unknown observed category {other:?}"),
        };
        assert_eq!(result.rejection, expected_category, "{name}: category");
        assert_eq!(
            result.accepted(),
            case["accepted"]
                .as_bool()
                .expect("accepted must be boolean"),
            "{name}: acceptance"
        );
        assert_eq!(
            result.micro_steps,
            count(case, "selected_micro_steps"),
            "{name}: selected micro steps"
        );
        assert_eq!(
            result.forward_evaluations,
            count(case, "forward_evaluations"),
            "{name}: forward evaluations"
        );
        assert_eq!(
            result.reverse_evaluations,
            count(case, "reverse_evaluations"),
            "{name}: reverse evaluations"
        );
        assert_eq!(
            result.evaluations,
            count(case, "target_evaluations"),
            "{name}: total evaluations"
        );

        if let Some(end) = result.end_state {
            assert_vector_close(name, "theta", &end.theta, &vector(case, "theta"));
            assert_vector_close(name, "rho", &end.rho, &vector(case, "rho"));
            assert_vector_close(name, "gradient", &end.grad, &vector(case, "gradient"));
            assert_close(
                name,
                "logp_position",
                end.log_prob,
                number(case, "logp_position"),
            );
            let joint = end.log_prob
                - 0.5
                    * end
                        .rho
                        .iter()
                        .zip(&inverse_mass)
                        .map(|(rho, inverse_mass)| rho * rho * inverse_mass)
                        .sum::<f64>();
            assert_close(name, "logp_joint", joint, number(case, "logp_joint"));
        } else {
            assert!(
                case["theta"].is_null(),
                "{name}: unexpected rejected endpoint"
            );
        }
    }
}

macro_rules! oracle_case {
    ($test:ident, $case:literal) => {
        #[test]
        fn $test() {
            check_case($case);
        }
    };
}

oracle_case!(forward_minimum_acceptance, "forward_minimum_acceptance");
oracle_case!(backward_minimum_acceptance, "backward_minimum_acceptance");
oracle_case!(forward_refinement, "forward_refinement");
oracle_case!(backward_refinement, "backward_refinement");
oracle_case!(exhaustion, "exhaustion");
oracle_case!(
    forward_reverse_coarser_rejection,
    "forward_reverse_coarser_rejection"
);
oracle_case!(
    backward_reverse_coarser_rejection,
    "backward_reverse_coarser_rejection"
);
oracle_case!(
    multi_level_reverse_coarsening,
    "multi_level_reverse_coarsening"
);
oracle_case!(inclusive_boundary, "inclusive_boundary");
oracle_case!(non_power_of_two_minimum, "non_power_of_two_minimum");
oracle_case!(nonidentity_diagonal_mass, "nonidentity_diagonal_mass");
