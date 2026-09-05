use crate::kernel::{
    Direction, FixedTuning, Rejection, ScriptedTransitionRng, SpanStop, TransitionDraw,
    TransitionInput, TransitionStop, TransitionTraceEvent, TransitionTuning, transition_w_traced,
};
use serde_json::Value;

const ORACLE: &str = include_str!("../../oracle/walnutpie/f5bba365/transition_traces.json");
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
        "{case} {field}: actual {actual:.17e}, expected {expected:.17e}, \
         tolerance {tolerance:.3e}"
    );
}

fn close_vec(case: &str, field: &str, actual: &[f64], expected: &[f64]) {
    assert_eq!(actual.len(), expected.len(), "{case} {field} length");
    for (index, (&actual, &expected)) in actual.iter().zip(expected).enumerate() {
        close(case, &format!("{field}[{index}]"), actual, expected);
    }
}

fn direction(value: &Value) -> Direction {
    match value.as_str().expect("direction string") {
        "forward" => Direction::Forward,
        "backward" => Direction::Backward,
        other => panic!("unknown direction {other}"),
    }
}

fn trace<'a>(case: &'a Value, event: &str) -> impl Iterator<Item = &'a Value> {
    case["trace"]
        .as_array()
        .expect("trace")
        .iter()
        .filter(move |entry| entry["event"].as_str() == Some(event))
}

fn rust_event<'a>(
    events: &'a [TransitionTraceEvent],
    event: &str,
    depth: usize,
) -> &'a TransitionTraceEvent {
    let matches: Vec<_> = events
        .iter()
        .filter(|entry| entry.event == event && entry.depth == Some(depth))
        .collect();
    assert_eq!(
        matches.len(),
        1,
        "expected one Rust {event} event at depth {depth}"
    );
    matches[0]
}

#[test]
fn matches_every_validated_upstream_transition_trace() {
    let document: Value = serde_json::from_str(ORACLE).expect("valid transition oracle JSON");
    assert_eq!(
        document["upstream_commit"].as_str(),
        Some("f5bba36529697c34567a2944be36b68e305c546d")
    );
    assert_eq!(
        document["schema"].as_str(),
        Some("walnutpie-transition-trace-oracle-v1")
    );

    for case in document["cases"].as_array().expect("cases") {
        let name = case["name"].as_str().expect("case name");
        let input = &case["input"];
        let expected = &case["result"];
        let precision = numbers(input, "precision");
        let inverse_mass = numbers(input, "inverse_mass");
        let theta = numbers(input, "theta");
        let standard_normal = numbers(input, "momentum_standard_normal");
        let rho: Vec<_> = standard_normal
            .iter()
            .zip(&inverse_mass)
            .map(|(z, inverse_mass)| z / inverse_mass.sqrt())
            .collect();

        let directions: Vec<_> = input["directions"]
            .as_array()
            .expect("directions")
            .iter()
            .map(direction)
            .collect();
        let uniforms = numbers(input, "uniforms");
        let mut draws = Vec::with_capacity(directions.len() + uniforms.len());
        let mut uniform_index = 0;
        for (depth_index, &direction) in directions.iter().enumerate() {
            draws.push(TransitionDraw::Direction(direction));
            let depth = depth_index + 1;
            let recursive_barker = if depth == 1 {
                0
            } else {
                (1usize << (depth - 1)) - 1
            };
            for _ in 0..recursive_barker {
                draws.push(TransitionDraw::Uniform(uniforms[uniform_index]));
                uniform_index += 1;
            }
            if !trace(case, "recursive_stop").any(|event| usize_field(event, "depth") == depth) {
                draws.push(TransitionDraw::Uniform(uniforms[uniform_index]));
                uniform_index += 1;
            }
        }
        assert_eq!(uniform_index, uniforms.len(), "{name} scripted uniforms");

        let mut rng = ScriptedTransitionRng::new(draws);
        let mut evaluations = 0;
        let traced = transition_w_traced(
            &mut rng,
            TransitionInput {
                theta: theta.clone(),
                rho,
            },
            &inverse_mass,
            TransitionTuning {
                leaf: FixedTuning {
                    options: crate::kernel::KernelOptions::default(),
                    reverse_coarsening_order:
                        crate::kernel::ReverseCoarseningOrder::FinestToCoarsest,
                    reverse_coarser_policy: crate::kernel::ReverseCoarserPolicy::StopOrbit,
                    step_size: number(input, "step"),
                    max_refinement_levels: usize_field(input, "max_step_halvings"),
                    min_micro_steps: usize_field(input, "min_micro_steps"),
                    max_error: number(input, "max_error"),
                    divergence_threshold: 1000.0,
                },
                max_depth: usize_field(input, "max_depth"),
            },
            &mut |position| {
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
            },
        )
        .unwrap_or_else(|error| panic!("{name}: {error}"));

        close_vec(
            name,
            "theta",
            &traced.result.selected.theta,
            &numbers(expected, "theta"),
        );
        close_vec(
            name,
            "gradient",
            &traced.result.selected.grad,
            &numbers(expected, "gradient"),
        );
        close(
            name,
            "logp_position",
            traced.result.selected.log_prob,
            number(expected, "logp_position"),
        );
        assert_eq!(
            evaluations,
            usize_field(expected, "target_evaluations"),
            "{name} target evaluations"
        );
        assert_eq!(
            traced.result.diagnostics.target_evaluations, evaluations,
            "{name} diagnostic evaluations"
        );

        let expected_stop = if trace(case, "recursive_stop").next().is_some() {
            TransitionStop::Recursive(SpanStop::Leaf(Rejection::RefinementExhausted))
        } else if trace(case, "outer_uturn_predicate")
            .any(|event| event["flag"].as_bool() == Some(true))
        {
            TransitionStop::OuterUTurn
        } else {
            TransitionStop::MaxDepth
        };
        assert_eq!(traced.result.diagnostics.stop, expected_stop, "{name} stop");
        assert_eq!(
            traced.result.diagnostics.depth,
            directions.len(),
            "{name} logical depth"
        );
        let upstream_depth = usize_field(expected, "depth");
        let expected_upstream_depth = if expected_stop == TransitionStop::MaxDepth {
            directions.len() + 1
        } else {
            directions.len()
        };
        assert_eq!(
            upstream_depth, expected_upstream_depth,
            "{name} pinned transition_w depth output convention"
        );

        let raw = &case["rng_consumption"];
        assert_eq!(
            usize_field(raw, "standard_normal_components"),
            theta.len(),
            "{name} momentum component consumption"
        );
        assert_eq!(
            traced.result.diagnostics.direction_draws,
            usize_field(raw, "uniform_binary"),
            "{name} direction draws"
        );
        assert_eq!(
            traced.result.diagnostics.uniform_draws,
            usize_field(raw, "uniform_01"),
            "{name} uniform draws"
        );
        assert_eq!(
            rng.consumed(),
            usize_field(raw, "uniform_binary") + usize_field(raw, "uniform_01"),
            "{name} comparable logical RNG consumption"
        );
        assert_eq!(rng.remaining(), 0, "{name} unconsumed scripted draws");

        for expected_direction in trace(case, "direction") {
            let depth = usize_field(expected_direction, "depth");
            let actual = rust_event(&traced.events, "direction", depth);
            assert_eq!(
                actual.direction,
                Some(direction(&expected_direction["direction"])),
                "{name} direction at depth {depth}"
            );
            assert_eq!(
                actual.flag,
                expected_direction["flag"].as_bool(),
                "{name} direction decision at depth {depth}"
            );
        }

        let expected_combines: Vec<_> = trace(case, "combine").collect();
        let actual_combines: Vec<_> = traced
            .events
            .iter()
            .filter(|event| event.event == "combine" || event.event == "outer_combine_metropolis")
            .collect();
        assert_eq!(
            actual_combines.len(),
            expected_combines.len(),
            "{name} combine event count"
        );
        for (expected_combine, actual) in expected_combines.iter().zip(actual_combines) {
            let update = expected_combine["update"].as_str().unwrap();
            let draw = number(expected_combine, "uniform_draw");
            assert_eq!(
                actual.direction,
                Some(direction(&expected_combine["direction"])),
                "{name} {update} combine direction"
            );
            assert_eq!(
                actual.event,
                match update {
                    "barker" => "combine",
                    "metropolis" => "outer_combine_metropolis",
                    other => panic!("unknown update {other}"),
                },
                "{name} combine kind"
            );
            assert_eq!(
                actual.flag,
                expected_combine["flag"].as_bool(),
                "{name} {update} combine decision"
            );
            close(name, "uniform_draw", actual.uniform_draw.unwrap(), draw);
            close(
                name,
                "update_log_probability",
                actual.update_log_probability.unwrap(),
                number(expected_combine, "update_log_probability"),
            );
        }

        if expected_stop == TransitionStop::OuterUTurn {
            let predicate = traced
                .events
                .iter()
                .position(|event| event.event == "outer_uturn_predicate")
                .unwrap();
            let combine = traced
                .events
                .iter()
                .position(|event| event.event == "outer_combine_metropolis")
                .unwrap();
            let stop = traced
                .events
                .iter()
                .position(|event| event.event == "transition_stop")
                .unwrap();
            assert!(predicate < combine && combine < stop, "{name} event order");
        }
        if expected_stop
            == TransitionStop::Recursive(SpanStop::Leaf(Rejection::RefinementExhausted))
        {
            let recursive = traced
                .events
                .iter()
                .position(|event| event.event == "recursive_stop")
                .unwrap();
            let stop = traced
                .events
                .iter()
                .position(|event| event.event == "transition_stop")
                .unwrap();
            assert!(recursive < stop, "{name} recursive-stop order");
            assert!(
                traced.events.iter().all(|event| {
                    event.event != "outer_uturn_predicate"
                        && event.event != "outer_combine_metropolis"
                }),
                "{name} recursive stop must precede outer operations"
            );
        }
    }
}
