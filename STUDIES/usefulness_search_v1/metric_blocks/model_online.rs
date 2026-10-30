use owalnuts::sampler::{Adaptation, Limits, Metric, Sampler, Target, TargetError, WarmupConfig, DEFAULT_WARMUP_EXHAUSTION, DEFAULT_METRIC_REGULARIZATION};
use serde_json::{json, Value};
use std::{env, fs, error::Error, time::Instant};
use owalnuts_bridgestan::{ReplicatedStanTarget, default_preload};
use owalnuts::walnutpie::DenseAutoSelectConfig;
fn main() -> Result<(), Box<dyn Error>> {
    let args: Vec<_> = env::args().collect();
    let input: Value = serde_json::from_slice(&fs::read(&args[1])?)?;
    let data = fs::read_to_string(input["data"].as_str().unwrap())?;
    let target = ReplicatedStanTarget::load(std::path::Path::new(input["model"].as_str().unwrap()), &default_preload(), Some(&data), 1, 4)?;
    let starts: Vec<Vec<f64>> = serde_json::from_value(input["starts"].clone())?;
    let mut sampler = Sampler::new().warmup(input["warmup"].as_u64().unwrap() as usize)
        .draws(input["draws"].as_u64().unwrap() as usize).seed(input["seed"].as_u64().unwrap())
        .threads(4).limits(Limits::new().admit_worst_case());
    match input["arm"].as_str().unwrap() {
        "dense" => sampler = sampler.metric(Metric::dense()),
        "fixed_dense" | "fixed_diag" => {
            let m: Vec<f64> = serde_json::from_value(input["mass"].clone())?;
            sampler = sampler.metric(if input["arm"] == "fixed_dense" { Metric::fixed_dense(m) }
                else { Metric::fixed_diagonal(m) })
                .adaptation(Adaptation::Custom(WarmupConfig::new(0.8)?.with_mass_adaptation(false)));
        },
        "diag" => {},
        "auto" => sampler = sampler.adaptation(Adaptation::Custom(WarmupConfig::new(0.8)?.with_warmup_exhaustion_rule(DEFAULT_WARMUP_EXHAUSTION).with_metric_regularization(DEFAULT_METRIC_REGULARIZATION).with_dense_auto_select(DenseAutoSelectConfig::hessian_fit(2, 5.0, 0.5)?))),
        _ => return Err("unknown arm".into()),
    }
    let start = Instant::now();
    let result = sampler.run(&target, &starts)?;
    let elapsed = start.elapsed().as_secs_f64();
    let draws: Vec<_> = result.chains().iter().map(|c|
        (0..c.retained()).map(|i| c.sample(i).unwrap().to_vec()).collect::<Vec<_>>()).collect();
    fs::write(&args[2], serde_json::to_vec(&json!({"draws": draws, "seconds": elapsed,
        "target_calls": target.calls(), "retained_divergences": result.chains().iter().map(|c| c.telemetry().retained().divergences()).sum::<usize>(), "revision": result.algorithm_revision()}))?)?;
    Ok(())
}
