//! Per-transition warmup profile of the shipped defaults (plus research arms) on a BridgeStan model.
//! Usage: warmup-profile <model.so> <data.json> <seed> <out.json> [arm]
//! arms: default | beyond-warmup | adaptsel-warmup | stan-search | beyond-warmup+stan-search
#![forbid(unsafe_code)]
use owalnuts::sampler::{
    Adaptation, DEFAULT_METRIC_REGULARIZATION, DEFAULT_WARMUP_EXHAUSTION, Init, Limits, Metric,
    ReverseCoarserPolicy, Sampler, Tuning, WarmupConfig, uniform_starts,
};
use owalnuts::walnutpie::InitialStepSearchConfig;
use owalnuts_bridgestan::{ReplicatedStanTarget, default_preload};
use serde_json::json;
use std::{env, error::Error, fs, path::Path};

const CHAINS: usize = 4;
const WARMUP: usize = 1000;
const RETAINED: usize = 1000;

fn main() -> Result<(), Box<dyn Error>> {
    let args: Vec<String> = env::args().skip(1).collect();
    let (model, data, seed, out, arm) = match args.as_slice() {
        [m, d, s, o] => (m, d, s, o, "default".to_string()),
        [m, d, s, o, a] => (m, d, s, o, a.clone()),
        _ => return Err("usage: <model.so> <data.json> <seed> <out.json> [arm]".into()),
    };
    let seed: u64 = seed.parse()?;
    let data_json = fs::read_to_string(data)?;
    let target = ReplicatedStanTarget::load(
        Path::new(model),
        &default_preload(),
        Some(&data_json),
        1,
        CHAINS,
    )?;
    let mut warmup = WarmupConfig::new(0.8)?
        .with_mass_adaptation(true)
        .with_metric_regularization(DEFAULT_METRIC_REGULARIZATION)
        .with_warmup_exhaustion_rule(DEFAULT_WARMUP_EXHAUSTION)
        .with_telemetry_checkpoints((0..WARMUP).collect())?;
    for part in arm.split('+') {
        warmup = match part {
            "default" => warmup,
            "beyond-warmup" => {
                warmup.with_warmup_reverse_coarser_policy(ReverseCoarserPolicy::ZeroWeightBeyond)
            }
            "adaptsel-warmup" => warmup.with_warmup_reverse_coarser_policy(
                ReverseCoarserPolicy::ZeroWeightBeyondAdaptSelected,
            ),
            "stan-search" => warmup.with_initial_step_search(InitialStepSearchConfig::stan()),
            "skip" => warmup.with_skip_single_leaf_reverse_coarser_statistic(true),
            "initnuts" => warmup.with_initial_phase_max_error(1000.0)?,
            "descent2" => warmup.with_dual_averaging_max_descent(2.0)?,
            "descent1.5" => warmup.with_dual_averaging_max_descent(1.5)?,
            other => return Err(format!("unknown arm part {other}").into()),
        };
    }
    let sampler = Sampler::new()
        .warmup(WARMUP)
        .draws(RETAINED)
        .chains(CHAINS)
        .seed(seed)
        .threads(CHAINS)
        .metric(Metric::diagonal())
        .adaptation(Adaptation::Custom(warmup))
        .tuning(Tuning::default())
        .limits(Limits::new().admit_worst_case());
    let (radius, max_attempts) = match Init::uniform() {
        Init::Uniform {
            radius,
            max_attempts,
        } => (radius, max_attempts),
        _ => unreachable!(),
    };
    let starts = uniform_starts(&target, CHAINS, seed, radius, max_attempts)?;
    let posterior = sampler.run(&target, &starts)?;
    let chains: Vec<_> = posterior
        .chains()
        .iter()
        .map(|chain| {
            let t = chain.telemetry();
            let cps: Vec<_> = t
                .warmup_checkpoints()
                .iter()
                .map(|c| {
                    json!({
                        "t": c.transition(), "phase": format!("{:?}", c.phase()),
                        "window": c.window_index(), "calls": c.target_calls(),
                        "h_before": c.step_before(), "h_after": c.step_after(),
                        "divergent": c.divergent(), "refine": c.refinement_attempts(),
                        "rc_rej": c.reverse_coarser_rejections(),
                        "max_error_after": c.max_error_after(),
                        "cce": c.current_coarse_endpoint().mean(), "cce_n": c.current_coarse_endpoint().count(),
                    })
                })
                .collect();
            let diags: Vec<_> = chain
                .diagnostics()
                .iter()
                .map(|d| json!([d.depth(), d.orbit_states(), d.step_size(), d.maximum_absolute_energy_error()]))
                .collect();
            let draws: Vec<Vec<f64>> = (0..RETAINED)
                .map(|i| chain.sample(i).unwrap().to_vec())
                .collect();
            let r = t.retained();
            json!({
                "checkpoints": cps,
                "diagnostics": diags,
                "draws": draws,
                "warmup_calls": t.discarded().target_calls_total(),
                "retained_calls": r.target_calls_total(),
                "retained_divergences": r.divergences(),
                "retained_rc_stops": r.reverse_coarser_stops(),
                "retained_leaves": r.leaves_built(),
                "final_step": chain.metadata().tuning().step_size(),
                "mass_diagonal": chain.metadata().mass_diagonal().to_vec(),
            })
        })
        .collect();
    let payload = json!({"seed": seed, "model": model, "arm": arm, "total_calls": target.calls(), "chains": chains});
    fs::write(out, serde_json::to_vec(&payload)?)?;
    eprintln!("done {arm}: calls {}", target.calls());
    Ok(())
}
