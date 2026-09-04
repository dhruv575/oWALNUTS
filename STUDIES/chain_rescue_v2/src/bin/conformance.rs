//! Deterministic, non-evidence observe-versus-disabled conformance fixture.
#![forbid(unsafe_code)]

#[path = "../arms.rs"]
mod arms;

use arms::Arm;
use owalnuts::sampler::{Limits, Metric, Sampler, Target, TargetError, Tuning};
use owalnuts::walnutpie::{ChainRescueOutcome, MultiChainOutput};
use serde_json::{Value, json};
use std::{env, error::Error, path::Path};

const FIXTURE_SEED: u64 = 92_001;
const WARMUP: usize = 150;
const RETAINED: usize = 64;
const CHAINS: usize = 4;

struct DisconnectedTrap;

impl Target for DisconnectedTrap {
    fn dimension(&self) -> usize {
        3
    }

    fn log_density_gradient(
        &self,
        position: &[f64],
        gradient: &mut [f64],
    ) -> Result<f64, TargetError> {
        let x = position[0];
        let mut logp = if x < -50.0 {
            let centered = x + 60.0;
            gradient[0] = -centered;
            -100.0 - 0.5 * centered * centered
        } else if x > 50.0 {
            let centered = x - 60.0;
            gradient[0] = -centered;
            -0.5 * centered * centered
        } else {
            return Err(TargetError::recoverable(
                "disconnected conformance trap gap",
            ));
        };
        for (index, scale) in [(1, 2.0_f64), (2, 0.5_f64)] {
            let value = position[index];
            gradient[index] = -value / (scale * scale);
            logp -= 0.5 * value * value / (scale * scale);
        }
        Ok(logp)
    }
}

fn fixture_starts() -> Vec<Vec<f64>> {
    vec![
        vec![-60.0, 0.0, 0.0],
        vec![60.0, -0.5, 0.75],
        vec![60.5, 0.25, -0.5],
        vec![59.5, 0.75, -0.25],
    ]
}

fn run_arm(arm: Arm) -> Result<MultiChainOutput, Box<dyn Error>> {
    let sampler = Sampler::new()
        .warmup(WARMUP)
        .draws(RETAINED)
        .chains(CHAINS)
        .threads(CHAINS)
        .seed(FIXTURE_SEED)
        .metric(Metric::diagonal())
        .adaptation(arms::adaptation(arm)?)
        .tuning(Tuning::default())
        .limits(Limits::new().admit_worst_case());
    Ok(sampler
        .run(&DisconnectedTrap, &fixture_starts())?
        .into_inner())
}

fn snapshot(output: &MultiChainOutput) -> Vec<Value> {
    output
        .chains()
        .iter()
        .map(|chain| {
            json!({
                "retained_unconstrained_sha256": arms::retained_unconstrained_sha256(chain),
                "retained_diagnostics_sha256": arms::retained_diagnostics_sha256(chain, WARMUP),
                "non_rescue_telemetry_sha256": arms::non_rescue_telemetry_sha256(chain.telemetry()),
                "final_metric_sha256": arms::final_metric_sha256(chain),
                "final_tuning_sha256": arms::final_tuning_sha256(chain),
                "work_discarded": arms::work_json(chain.telemetry().discarded()),
                "work_retained": arms::work_json(chain.telemetry().retained()),
                "work_total": arms::work_json(chain.telemetry().total()),
                "adaptation_target_calls": chain.telemetry().adaptation_target_calls(),
            })
        })
        .collect()
}

fn compare() -> Result<Value, Box<dyn Error>> {
    let disabled = run_arm(Arm::Disabled)?;
    let observe = run_arm(Arm::Observe)?;
    let disabled_snapshot = snapshot(&disabled);
    let observe_snapshot = snapshot(&observe);
    let retained_bytes_equal =
        disabled
            .chains()
            .iter()
            .zip(observe.chains())
            .all(|(left, right)| {
                left.samples().len() == right.samples().len()
                    && left
                        .samples()
                        .iter()
                        .zip(right.samples())
                        .all(|(a, b)| a.to_bits() == b.to_bits())
                    && arms::retained_unconstrained_sha256(left)
                        == arms::retained_unconstrained_sha256(right)
            });
    let work_equal = disabled_snapshot
        .iter()
        .zip(&observe_snapshot)
        .all(|(a, b)| {
            a["work_discarded"] == b["work_discarded"]
                && a["work_retained"] == b["work_retained"]
                && a["work_total"] == b["work_total"]
                && a["adaptation_target_calls"] == b["adaptation_target_calls"]
        });
    let final_adaptation_equal = disabled_snapshot
        .iter()
        .zip(&observe_snapshot)
        .all(|(a, b)| {
            a["final_metric_sha256"] == b["final_metric_sha256"]
                && a["final_tuning_sha256"] == b["final_tuning_sha256"]
        });
    let diagnostics_equal = disabled_snapshot
        .iter()
        .zip(&observe_snapshot)
        .all(|(a, b)| a["retained_diagnostics_sha256"] == b["retained_diagnostics_sha256"]);
    let non_rescue_telemetry_equal = disabled_snapshot
        .iter()
        .zip(&observe_snapshot)
        .all(|(a, b)| a["non_rescue_telemetry_sha256"] == b["non_rescue_telemetry_sha256"]);
    let observe_events = observe
        .chains()
        .iter()
        .flat_map(|chain| chain.telemetry().chain_rescues())
        .count();
    let observe_hits = observe
        .chains()
        .iter()
        .flat_map(|chain| chain.telemetry().chain_rescues())
        .filter(|update| matches!(update.outcome(), ChainRescueOutcome::ObservedHit { .. }))
        .count();
    let observe_forbidden_outcomes = observe
        .chains()
        .iter()
        .flat_map(|chain| chain.telemetry().chain_rescues())
        .filter(|update| {
            update.installed_unconstrained_position().is_some()
                || matches!(
                    update.outcome(),
                    ChainRescueOutcome::Restarted { .. }
                        | ChainRescueOutcome::PendingFirstHit { .. }
                        | ChainRescueOutcome::Pooled { .. }
                )
        })
        .count();
    let no_rescue_rng_mutation = retained_bytes_equal
        && work_equal
        && final_adaptation_equal
        && diagnostics_equal
        && non_rescue_telemetry_equal;
    let bit_identical = retained_bytes_equal
        && work_equal
        && final_adaptation_equal
        && diagnostics_equal
        && non_rescue_telemetry_equal
        && observe_hits > 0
        && observe_forbidden_outcomes == 0;
    Ok(json!({
        "schema": "chain-rescue-v2-conformance",
        "schema_version": 1,
        "status": if bit_identical { "pass" } else { "fail" },
        "evidence": false,
        "fixture": "deterministic-disconnected-log-density-trap-v2",
        "seed": FIXTURE_SEED,
        "warmup": WARMUP,
        "retained": RETAINED,
        "chains": CHAINS,
        "starts": fixture_starts(),
        "initial_position_sha256": fixture_starts().iter().map(|x| arms::initial_position_sha256(x)).collect::<Vec<_>>(),
        "comparison": {
            "retained_draw_bytes_equal": retained_bytes_equal,
            "work_counters_equal": work_equal,
            "final_adaptation_hashes_equal": final_adaptation_equal,
            "retained_diagnostics_equal": diagnostics_equal,
            "non_rescue_telemetry_equal": non_rescue_telemetry_equal,
            "no_rescue_rng_mutation": no_rescue_rng_mutation,
            "observed_hit_path_exercised": observe_hits > 0,
            "observe_forbidden_outcomes": observe_forbidden_outcomes,
            "bit_identical": bit_identical,
        },
        "observe_boundary_events": observe_events,
        "observe_hits": observe_hits,
        "disabled": disabled_snapshot,
        "observe": observe_snapshot,
    }))
}

fn main() {
    let args = env::args().skip(1).collect::<Vec<_>>();
    let [output] = args.as_slice() else {
        eprintln!("usage: conformance <out.json>");
        std::process::exit(2);
    };
    let result = compare().and_then(|payload| {
        arms::write_new_atomically(Path::new(output), &serde_json::to_vec_pretty(&payload)?)?;
        if payload["comparison"]["bit_identical"] == true {
            Ok(())
        } else {
            Err("observe and disabled fixture runs were not bit-identical".into())
        }
    });
    if let Err(error) = result {
        eprintln!("error: {error}");
        std::process::exit(1);
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn observe_is_bit_identical_to_disabled_on_non_evidence_fixture() {
        let result = compare().expect("conformance fixture runs");
        assert_eq!(result["comparison"]["bit_identical"], true);
        assert_eq!(result["comparison"]["observed_hit_path_exercised"], true);
        assert_eq!(result["comparison"]["no_rescue_rng_mutation"], true);
        assert!(result["observe_hits"].as_u64().unwrap() > 0);
        assert_eq!(result["comparison"]["observe_forbidden_outcomes"], 0);
        assert_ne!(result["seed"], 92_101);
    }

    #[test]
    fn exported_schedule_matches_every_observed_boundary() {
        let output = run_arm(Arm::Observe).unwrap();
        for chain in output.chains() {
            let schedule = arms::warmup_schedule_json(chain).unwrap();
            let windows = schedule["windows"].as_array().unwrap();
            let events = chain.telemetry().chain_rescues();
            assert_eq!(windows.len(), events.len());
            for (window, event) in windows.iter().zip(events) {
                assert_eq!(window["window_index"], event.window_index());
                assert_eq!(window["boundary_transition"], event.transition());
                assert_eq!(window["window_transitions"], event.window_transitions());
            }
        }
    }
}
