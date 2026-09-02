//! CmdStan CSV export round-trip, the `Summary` table on a real run, and an
//! optional cross-check against `arviz.from_cmdstan` / `az.summary`.
//!
//! Set `OWALNUTS_ARVIZ_PYTHON` to a Python interpreter with `arviz` installed
//! to run `integrations/python/tests/check_cmdstan_export.py` on the files
//! this test writes; without it the Python step is skipped.

use std::{env, fs, num::NonZeroUsize, path::PathBuf, process::Command};

use owalnuts::{
    diagnostics::{SamplerHealth, Summary},
    export::{CmdStanCsv, ExportError, SAMPLER_STAT_COLUMNS},
    walnutpie::{
        DiagonalMass, KernelTuning, MultiChainOutput, RunConfig, Target, TargetError, WarmupConfig,
        sample_chains,
    },
};
use serde_json::json;

struct Gaussian {
    scales: Vec<f64>,
}

impl Target for Gaussian {
    fn dimension(&self) -> usize {
        self.scales.len()
    }
    fn log_density_gradient(
        &self,
        position: &[f64],
        gradient: &mut [f64],
    ) -> Result<f64, TargetError> {
        let mut lp = 0.0;
        for ((g, x), s) in gradient.iter_mut().zip(position).zip(&self.scales) {
            *g = -x / (s * s);
            lp -= 0.5 * (x / s).powi(2);
        }
        Ok(lp)
    }
}

fn nz(n: usize) -> NonZeroUsize {
    NonZeroUsize::new(n).unwrap()
}

fn run() -> (Gaussian, MultiChainOutput) {
    let target = Gaussian {
        scales: vec![1.0, 3.0, 0.5],
    };
    let tuning = KernelTuning::new(0.4, nz(8), nz(1), nz(4), 1.0).unwrap();
    let config = RunConfig::new(200, nz(400), 0x5eed_d1a6)
        .with_tuning(tuning)
        .with_warmup(WarmupConfig::new(0.8).unwrap());
    let starts: Vec<Vec<f64>> = (0..4).map(|k| vec![0.1 * k as f64, -0.2, 0.3]).collect();
    let output = sample_chains(
        &target,
        &starts,
        &DiagonalMass::identity(nz(3)),
        &config,
        nz(4),
    )
    .unwrap();
    (target, output)
}

fn names() -> Vec<String> {
    ["mu", "tau", "eta"].map(str::to_string).to_vec()
}

fn scratch_dir(name: &str) -> PathBuf {
    let dir = env::temp_dir().join(format!("owalnuts-{name}-{}", std::process::id()));
    let _ = fs::remove_dir_all(&dir);
    fs::create_dir_all(&dir).unwrap();
    dir
}

#[test]
fn csv_round_trips_draws_and_sampler_stats() {
    let (target, output) = run();
    let names = names();
    let writer = CmdStanCsv::new()
        .with_parameter_names(&names)
        .with_log_density(&target);
    let mut buffer = Vec::new();
    writer.write(&output.chains()[0], 1, &mut buffer).unwrap();
    let text = String::from_utf8(buffer).unwrap();
    let mut lines = text.lines().filter(|line| !line.starts_with('#'));
    let header: Vec<&str> = lines.next().unwrap().split(',').collect();
    let mut expected = vec!["lp__"];
    expected.extend(SAMPLER_STAT_COLUMNS);
    expected.extend(["mu", "tau", "eta"]);
    assert_eq!(header, expected);
    assert!(text.contains("# Step size = "));
    assert!(text.contains("# Diagonal elements of inverse mass matrix:"));

    let chain = &output.chains()[0];
    let discarded = chain.metadata().discarded();
    let rows: Vec<Vec<f64>> = lines
        .map(|line| line.split(',').map(|c| c.parse().unwrap()).collect())
        .collect();
    assert_eq!(rows.len(), chain.retained());
    let mut gradient = vec![0.0; 3];
    for (draw, row) in rows.iter().enumerate() {
        let sample = chain.sample(draw).unwrap();
        let diagnostic = &chain.diagnostics()[discarded + draw];
        assert_eq!(
            row[0],
            target.log_density_gradient(sample, &mut gradient).unwrap()
        );
        assert_eq!(row[1], chain.metadata().tuning().step_size());
        assert_eq!(row[2], diagnostic.depth() as f64);
        assert_eq!(row[3], diagnostic.target_evaluations() as f64);
        assert_eq!(row[4], f64::from(u8::from(diagnostic.divergent())));
        assert_eq!(row[5], diagnostic.initial_hamiltonian());
        assert_eq!(&row[6..], sample);
    }

    let wrong = ["a".to_string()];
    assert!(matches!(
        CmdStanCsv::new()
            .with_parameter_names(&wrong)
            .write(chain, 1, Vec::new()),
        Err(ExportError::NameCountMismatch { .. })
    ));
    let other = Gaussian { scales: vec![1.0] };
    assert!(matches!(
        CmdStanCsv::new()
            .with_log_density(&other)
            .write(chain, 1, Vec::new()),
        Err(ExportError::DimensionMismatch { .. })
    ));
}

#[test]
fn summary_reports_gaussian_moments_and_health() {
    let (_, output) = run();
    let summary = Summary::from_output(&output, Some(&names())).unwrap();
    assert_eq!(summary.chains, 4);
    assert_eq!(summary.draws_per_chain, 400);
    for (row, scale) in summary.parameters.iter().zip([1.0, 3.0, 0.5]) {
        assert!(row.mean.abs() < 0.25 * scale, "{row:?}");
        assert!((row.sd / scale - 1.0).abs() < 0.2, "{row:?}");
        assert!(row.rhat < 1.05, "{row:?}");
        assert!(row.ess_bulk > 200.0 && row.ess_tail > 200.0, "{row:?}");
        assert!(row.mcse_mean > 0.0 && row.mcse_mean < 0.2 * scale);
        assert!(row.quantiles[0] < row.quantiles[1] && row.quantiles[1] < row.quantiles[2]);
    }
    let health = &summary.health;
    assert_eq!(health.per_chain.len(), 4);
    assert_eq!(health.pooled.transitions, 1600);
    assert_eq!(health.pooled.divergences, 0);
    assert!(health.pooled.mean_tree_depth > 0.0);
    assert!(health.pooled.step_size > 0.0);
    assert_eq!(
        health.pooled.target_calls,
        health
            .per_chain
            .iter()
            .map(|c| c.target_calls)
            .sum::<usize>()
    );
    assert_eq!(*health, SamplerHealth::from_chains(output.chains()));

    let table = summary.to_string();
    println!("{table}");
    assert!(table.contains("ess_bulk"));
    assert!(table.lines().any(|line| line.starts_with("mu ")));
    assert!(table.contains("Sampler health"));
    assert!(Summary::from_chains(&[], None).is_err());
}

#[test]
fn arviz_from_cmdstan_agrees_with_rust_summary() {
    let Some(python) = env::var_os("OWALNUTS_ARVIZ_PYTHON") else {
        eprintln!("OWALNUTS_ARVIZ_PYTHON not set; skipping ArviZ cross-check");
        return;
    };
    let (target, output) = run();
    let names = names();
    let dir = scratch_dir("cmdstan");
    let paths = CmdStanCsv::new()
        .with_parameter_names(&names)
        .with_log_density(&target)
        .write_dir(&output, &dir, "chain")
        .unwrap();
    assert_eq!(paths.len(), 4);
    let summary = Summary::from_output(&output, Some(&names)).unwrap();
    let rust = json!({
        "parameters": summary.parameters.iter().map(|p| json!({
            "name": p.name, "mean": p.mean, "sd": p.sd, "mcse_mean": p.mcse_mean,
            "ess_bulk": p.ess_bulk, "ess_tail": p.ess_tail, "rhat": p.rhat,
        })).collect::<Vec<_>>(),
        "health": {
            "divergences": summary.health.pooled.divergences,
            "target_calls": summary.health.pooled.target_calls,
            "mean_tree_depth": summary.health.pooled.mean_tree_depth,
            "step_size": summary.health.pooled.step_size,
            "transitions": summary.health.pooled.transitions,
        },
        "scales": target.scales,
    });
    fs::write(dir.join("summary.json"), rust.to_string()).unwrap();
    let script = PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .join("integrations/python/tests/check_cmdstan_export.py");
    let status = Command::new(python)
        .arg(&script)
        .arg(&dir)
        .status()
        .expect("run python");
    assert!(status.success(), "ArviZ cross-check failed (see output)");
    let _ = fs::remove_dir_all(&dir);
}
