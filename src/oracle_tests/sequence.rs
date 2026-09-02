use crate::kernel::{
    Direction, FixedTuning, Rejection, ScriptedTransitionRng, SpanStop, TransitionDraw,
    TransitionInput, TransitionStop, TransitionTuning, transition_w_traced,
};
use serde_json::Value;

const ORACLE: &str =
    include_str!("../../oracle/walnutpie/f5bba365/transition_sequence_traces.json");
// The C++ and Rust implementations perform the same binary64 formulas but Eigen
// may reassociate elementary vector operations. This is about 90 ulps near one.
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

fn trace<'a>(transition: &'a Value, event: &str) -> impl Iterator<Item = &'a Value> {
    transition["trace"]
        .as_array()
        .expect("trace")
        .iter()
        .filter(move |entry| entry["event"].as_str() == Some(event))
}

fn expected_stop(transition: &Value) -> TransitionStop {
    if trace(transition, "recursive_stop").next().is_some() {
        TransitionStop::Recursive(SpanStop::Leaf(Rejection::RefinementExhausted))
    } else if trace(transition, "outer_uturn_predicate")
        .any(|event| event["flag"].as_bool() == Some(true))
    {
        TransitionStop::OuterUTurn
    } else {
        TransitionStop::MaxDepth
    }
}

fn scripted_draws(transition: &Value) -> Vec<TransitionDraw> {
    let script = &transition["script"];
    let direction_count = usize_field(
        &transition["rng_counts"]["raw_scripted_draws"],
        "directions",
    );
    let uniform_count = usize_field(&transition["rng_counts"]["raw_scripted_draws"], "uniforms");
    let directions: Vec<_> = script["directions"]
        .as_array()
        .expect("directions")
        .iter()
        .take(direction_count)
        .map(direction)
        .collect();
    let mut uniforms = numbers(script, "uniforms");
    uniforms.truncate(uniform_count);
    let mut draws = Vec::with_capacity(directions.len() + uniforms.len());
    let mut uniform_index = 0;
    for (depth_index, direction) in directions.into_iter().enumerate() {
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
        if !trace(transition, "recursive_stop").any(|event| usize_field(event, "depth") == depth) {
            draws.push(TransitionDraw::Uniform(uniforms[uniform_index]));
            uniform_index += 1;
        }
    }
    assert_eq!(
        uniform_index,
        uniforms.len(),
        "all upstream-consumed uniforms must be scripted"
    );
    draws
}

#[derive(Default)]
struct Aggregate {
    transitions: usize,
    evaluations: usize,
    directions: usize,
    uniforms: usize,
    barker: usize,
    metropolis: usize,
    normal_components: usize,
    leaves_attempted: usize,
    leaves_built: usize,
}

#[test]
fn matches_both_validated_upstream_transition_sequences() {
    let document: Value = serde_json::from_str(ORACLE).expect("valid sequence oracle JSON");
    assert_eq!(
        document["upstream_commit"].as_str(),
        Some("f5bba36529697c34567a2944be36b68e305c546d")
    );
    assert_eq!(
        document["schema"].as_str(),
        Some("walnutpie-transition-sequence-trace-oracle-v1")
    );
    let tapes = document["tapes"].as_array().expect("tapes");
    assert_eq!(tapes.len(), 2);
    let mut aggregate = Aggregate::default();

    for tape in tapes {
        let tape_name = tape["name"].as_str().expect("tape name");
        let precision = numbers(&tape["model"], "precision");
        let inverse_mass = numbers(&tape["model"], "inverse_mass");
        let mut propagated = numbers(tape, "initial_theta");
        let transitions = tape["transitions"].as_array().expect("transitions");
        assert_eq!(transitions.len(), 12, "{tape_name} transition count");

        for transition in transitions {
            let index = usize_field(transition, "index");
            let case = format!("{tape_name}/{index}");
            let input = numbers(transition, "input_theta");
            close_vec(&case, "propagated input", &input, &propagated);

            let z = numbers(&transition["script"], "standard_normal");
            let momentum: Vec<_> = z
                .iter()
                .zip(&inverse_mass)
                .map(|(z, inverse_mass)| z / inverse_mass.sqrt())
                .collect();
            close_vec(
                &case,
                "transformed momentum",
                &momentum,
                &numbers(transition, "resulting_momentum"),
            );
            let raw = &transition["rng_counts"]["raw_scripted_draws"];
            let logical = &transition["rng_counts"]["logical_calls"];
            assert_eq!(usize_field(logical, "standard_normal"), 1, "{case}");
            assert_eq!(
                usize_field(raw, "normal_components"),
                z.len(),
                "{case} normal components"
            );

            let mut rng = ScriptedTransitionRng::new(scripted_draws(transition));
            let kernel = &transition["kernel"];
            let mut evaluations = 0;
            let traced = transition_w_traced(
                &mut rng,
                TransitionInput {
                    theta: input.clone(),
                    rho: momentum,
                },
                &inverse_mass,
                TransitionTuning {
                    leaf: FixedTuning {
                        options: crate::kernel::KernelOptions::default(),
                        step_size: number(kernel, "step"),
                        max_refinement_levels: usize_field(kernel, "max_step_halvings"),
                        min_micro_steps: usize_field(kernel, "min_micro_steps"),
                        max_error: number(kernel, "max_error"),
                        divergence_threshold: 1000.0,
                    },
                    max_depth: usize_field(kernel, "max_depth"),
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
            .unwrap_or_else(|error| panic!("{case}: {error}"));
            let diagnostics = &traced.result.diagnostics;
            let expected_output = &transition["output"];
            close_vec(
                &case,
                "selected theta",
                &traced.result.selected.theta,
                &numbers(expected_output, "theta"),
            );
            close_vec(
                &case,
                "selected gradient",
                &traced.result.selected.grad,
                &numbers(expected_output, "gradient"),
            );
            close(
                &case,
                "selected log_prob",
                traced.result.selected.log_prob,
                number(expected_output, "logp_position"),
            );
            assert_eq!(
                diagnostics.stop,
                expected_stop(transition),
                "{case} stop cause"
            );
            assert_eq!(
                diagnostics.depth,
                usize_field(logical, "uniform_binary"),
                "{case} logical depth"
            );
            let upstream_depth = usize_field(&transition["diagnostics"], "depth");
            let expected_upstream_depth = if diagnostics.stop == TransitionStop::MaxDepth {
                diagnostics.depth + 1
            } else {
                diagnostics.depth
            };
            assert_eq!(
                upstream_depth, expected_upstream_depth,
                "{case} pinned depth-output convention"
            );
            assert_eq!(
                evaluations,
                usize_field(transition, "target_evaluations"),
                "{case} evaluations"
            );
            assert_eq!(diagnostics.target_evaluations, evaluations, "{case}");
            assert_eq!(
                diagnostics.direction_draws,
                usize_field(logical, "uniform_binary"),
                "{case} direction draws"
            );
            assert_eq!(
                diagnostics.uniform_draws,
                usize_field(logical, "uniform_01"),
                "{case} uniform draws"
            );
            assert_eq!(
                diagnostics.recursive_barker_draws,
                trace(transition, "combine")
                    .filter(|event| event["update"] == "barker")
                    .count(),
                "{case} Barker draws"
            );
            assert_eq!(
                diagnostics.outer_metropolis_draws,
                trace(transition, "combine")
                    .filter(|event| event["update"] == "metropolis")
                    .count(),
                "{case} Metropolis draws"
            );
            assert_eq!(
                rng.consumed(),
                diagnostics.direction_draws + diagnostics.uniform_draws,
                "{case} total logical draws"
            );
            assert_eq!(rng.remaining(), 0, "{case} unconsumed draws");

            let leaf_events: Vec<_> = traced
                .events
                .iter()
                .filter(|event| event.event == "leaf")
                .collect();
            assert_eq!(
                diagnostics.leaves_attempted,
                leaf_events.len(),
                "{case} attempted leaves"
            );
            assert_eq!(
                diagnostics.leaves_built,
                leaf_events
                    .iter()
                    .filter(|event| event.flag == Some(true))
                    .count(),
                "{case} built leaves"
            );
            let exposed_upstream: Vec<_> = transition["trace"]
                .as_array()
                .expect("trace")
                .iter()
                .filter(|event| {
                    !matches!(
                        event["event"].as_str(),
                        Some("momentum" | "outer_combine_complete" | "doubling_exit")
                    )
                })
                .collect();
            let upstream_has_stop = exposed_upstream
                .iter()
                .any(|event| event["event"] == "transition_stop");
            let exposed_rust: Vec<_> = traced
                .events
                .iter()
                .filter(|event| {
                    if event.event == "transition_stop" && !upstream_has_stop {
                        return false;
                    }
                    matches!(
                        event.event,
                        "direction"
                            | "combine"
                            | "outer_uturn_predicate"
                            | "outer_combine_metropolis"
                            | "recursive_stop"
                            | "transition_stop"
                    )
                })
                .collect();
            assert_eq!(
                exposed_rust.len(),
                exposed_upstream.len(),
                "{case} exposed event count"
            );
            for (upstream, actual) in exposed_upstream.into_iter().zip(exposed_rust) {
                let upstream_name = upstream["event"].as_str().unwrap();
                let expected_name = if upstream_name == "combine" {
                    match upstream["update"].as_str().unwrap() {
                        "barker" => "combine",
                        "metropolis" => "outer_combine_metropolis",
                        other => panic!("unknown update {other}"),
                    }
                } else {
                    upstream_name
                };
                assert_eq!(actual.event, expected_name, "{case} event kind");
                if upstream_name != "combine" {
                    assert_eq!(
                        actual.depth,
                        upstream["depth"].as_u64().map(|value| value as usize),
                        "{case} {upstream_name} depth"
                    );
                }
                if actual.direction.is_some() {
                    assert_eq!(
                        actual.direction,
                        upstream
                            .get("direction")
                            .and_then(Value::as_str)
                            .map(|_| direction(&upstream["direction"])),
                        "{case} {upstream_name} direction"
                    );
                }
                if actual.flag.is_some() {
                    assert_eq!(
                        actual.flag,
                        upstream.get("flag").and_then(Value::as_bool),
                        "{case} {} flag",
                        upstream["event"]
                    );
                }
                if upstream_name == "combine" {
                    close(
                        &case,
                        "event uniform",
                        actual.uniform_draw.expect("combine uniform"),
                        number(upstream, "uniform_draw"),
                    );
                    close(
                        &case,
                        "event log probability",
                        actual
                            .update_log_probability
                            .expect("combine log probability"),
                        number(upstream, "update_log_probability"),
                    );
                }
            }

            propagated = traced.result.selected.theta.clone();
            aggregate.transitions += 1;
            aggregate.evaluations += diagnostics.target_evaluations;
            aggregate.directions += diagnostics.direction_draws;
            aggregate.uniforms += diagnostics.uniform_draws;
            aggregate.barker += diagnostics.recursive_barker_draws;
            aggregate.metropolis += diagnostics.outer_metropolis_draws;
            aggregate.normal_components += z.len();
            aggregate.leaves_attempted += diagnostics.leaves_attempted;
            aggregate.leaves_built += diagnostics.leaves_built;
        }
        close_vec(
            tape_name,
            "final sequence",
            &propagated,
            &numbers(tape, "final_theta"),
        );
    }

    let fixture_transitions = tapes
        .iter()
        .flat_map(|tape| tape["transitions"].as_array().unwrap())
        .collect::<Vec<_>>();
    assert_eq!(aggregate.transitions, 24);
    assert_eq!(
        aggregate.evaluations,
        fixture_transitions
            .iter()
            .map(|transition| usize_field(transition, "target_evaluations"))
            .sum::<usize>()
    );
    assert_eq!(
        aggregate.directions,
        fixture_transitions
            .iter()
            .map(|transition| {
                usize_field(
                    &transition["rng_counts"]["raw_scripted_draws"],
                    "directions",
                )
            })
            .sum::<usize>()
    );
    assert_eq!(
        aggregate.uniforms,
        fixture_transitions
            .iter()
            .map(|transition| {
                usize_field(&transition["rng_counts"]["raw_scripted_draws"], "uniforms")
            })
            .sum::<usize>()
    );
    assert_eq!(
        aggregate.normal_components,
        fixture_transitions
            .iter()
            .map(|transition| {
                usize_field(
                    &transition["rng_counts"]["raw_scripted_draws"],
                    "normal_components",
                )
            })
            .sum::<usize>()
    );
    assert_eq!(aggregate.barker + aggregate.metropolis, aggregate.uniforms);
    assert!(aggregate.leaves_attempted >= aggregate.leaves_built);
}
