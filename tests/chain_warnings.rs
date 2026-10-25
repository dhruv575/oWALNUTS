//! Observe-only chain checks (`STUDIES/chain_disagreement_warning_v1`, WP44):
//! end-of-warmup and retained-draw window telemetry, `ChainWarning`, and the
//! `Summary` warning lines. Nothing here may change a draw.

use std::num::NonZeroUsize;

use owalnuts::diagnostics::{ChainWarning, Summary};
use owalnuts::sampler::{Metric, Sampler};
use owalnuts::walnutpie::{
    ChainRescueConfig, ChainWindowSummary, DiagonalMass, KernelTuning, RunConfig, Target,
    TargetError, WarmupConfig, sample_chains,
};

struct Gaussian(usize);

impl Target for Gaussian {
    fn dimension(&self) -> usize {
        self.0
    }

    fn log_density_gradient(&self, q: &[f64], gradient: &mut [f64]) -> Result<f64, TargetError> {
        for (g, x) in gradient.iter_mut().zip(q) {
            *g = -x;
        }
        Ok(-0.5 * q.iter().map(|x| x * x).sum::<f64>())
    }
}

/// The `tests/chain_rescue.rs` trap: a standard Gaussian plus a narrow,
/// negligible spike far away that a chain started inside never leaves.
struct Trap;

const TRAP_CENTER: f64 = 15.0;
const TRAP_SD: f64 = 0.3;
const TRAP_LOG_WEIGHT: f64 = -14.0;

impl Target for Trap {
    fn dimension(&self) -> usize {
        2
    }

    fn log_density_gradient(&self, q: &[f64], gradient: &mut [f64]) -> Result<f64, TargetError> {
        let main = -0.5 * q.iter().map(|x| x * x).sum::<f64>();
        let spike = TRAP_LOG_WEIGHT
            - 2.0 * TRAP_SD.ln()
            - 0.5
                * q.iter()
                    .map(|x| ((x - TRAP_CENTER) / TRAP_SD).powi(2))
                    .sum::<f64>();
        let max = main.max(spike);
        let value = max + ((main - max).exp() + (spike - max).exp()).ln();
        let w_main = (main - value).exp();
        let w_spike = (spike - value).exp();
        for (g, x) in gradient.iter_mut().zip(q) {
            *g = w_main * (-x) + w_spike * (-(x - TRAP_CENTER) / (TRAP_SD * TRAP_SD));
        }
        Ok(value)
    }
}

fn config(discarded: usize, retained: usize, rescue: Option<ChainRescueConfig>) -> RunConfig {
    let warmup = WarmupConfig::new(0.8).unwrap();
    let warmup = match rescue {
        Some(rescue) => warmup.with_chain_rescue(rescue),
        None => warmup,
    };
    RunConfig::new(discarded, NonZeroUsize::new(retained).unwrap(), 0x5eed)
        .with_tuning(
            KernelTuning::new(
                0.5,
                NonZeroUsize::new(8).unwrap(),
                NonZeroUsize::new(1).unwrap(),
                NonZeroUsize::new(4).unwrap(),
                1.0,
            )
            .unwrap(),
        )
        .with_warmup(warmup)
}

fn starts(dimension: usize) -> Vec<Vec<f64>> {
    (0..4)
        .map(|chain| {
            (0..dimension)
                .map(|i| ((chain as f64 + 1.0) * 0.5 - 1.25) * if i % 2 == 0 { 1.0 } else { -1.0 })
                .collect()
        })
        .collect()
}

#[test]
fn window_telemetry_matches_the_observe_only_last_boundary_and_the_draws() {
    let target = Gaussian(3);
    let mass = DiagonalMass::identity(NonZeroUsize::new(3).unwrap());
    let threads = NonZeroUsize::new(2).unwrap();
    let plain = sample_chains(
        &target,
        &starts(3),
        &mass,
        &config(1000, 400, None),
        threads,
    )
    .unwrap();
    let observed = sample_chains(
        &target,
        &starts(3),
        &mass,
        &config(1000, 400, Some(ChainRescueConfig::observe_only())),
        threads,
    )
    .unwrap();
    for (p, o) in plain.chains().iter().zip(observed.chains()) {
        // Observe-only rescue scoring and the chain checks are both
        // draw-neutral, so the two runs are the same run.
        assert_eq!(p.samples(), o.samples());
        assert_eq!(p.telemetry().warmup_end(), o.telemetry().warmup_end());
        assert_eq!(p.telemetry().sampling_end(), o.telemetry().sampling_end());

        let warmup = p.telemetry().warmup_end().expect("warmup window");
        // Default schedule at 1,000 warmup transitions: last slow window 450..950.
        assert_eq!((warmup.start(), warmup.end()), (450, 950));
        assert_eq!(warmup.transitions(), 500);
        assert_eq!(
            warmup.step_size().to_bits(),
            p.metadata().tuning().step_size().to_bits()
        );
        let last = o
            .telemetry()
            .chain_rescues()
            .iter()
            .rev()
            .find(|u| u.window_index() == 4)
            .expect("observe-only scores the last slow window");
        assert_eq!(last.transition() + 1, warmup.end());
        assert_eq!(last.window_transitions(), warmup.transitions());
        assert_eq!(last.median_log_density(), Some(warmup.median_log_density()));
        assert_eq!(last.log_density_iqr(), Some(warmup.log_density_iqr()));

        let sampled = p.telemetry().sampling_end().expect("retained window");
        assert_eq!((sampled.start(), sampled.end()), (1000, 1400));
        assert_eq!(
            sampled.step_size().to_bits(),
            p.metadata().tuning().step_size().to_bits()
        );
        assert!(sampled.median_log_density().is_finite());
        assert!(sampled.log_density_iqr() > 0.0);
    }
    assert!(ChainWarning::from_chains(plain.chains()).is_empty());
    let summary = Summary::from_output(&plain, None).unwrap();
    assert!(summary.chain_warnings.is_empty());
    assert!(!summary.to_string().contains("warning: chain"));
}

#[test]
fn a_trapped_chain_is_named_at_warmup_end_and_on_the_draws() {
    let target = Trap;
    let mass = DiagonalMass::identity(NonZeroUsize::new(2).unwrap());
    let mut starts = starts(2);
    starts[3] = vec![TRAP_CENTER, TRAP_CENTER];
    let output = sample_chains(
        &target,
        &starts,
        &mass,
        // 600 retained draws keep the three healthy chains' R-hat well below
        // 1.01 on every platform (the check is a strict threshold, and libm
        // rounding differs between Windows and Linux at 300 draws).
        &config(500, 600, None),
        NonZeroUsize::new(4).unwrap(),
    )
    .unwrap();
    let warnings = ChainWarning::from_chains(output.chains());
    assert!(!warnings.is_empty());
    assert!(warnings.iter().all(|w| w.chain() == 3), "{warnings:?}");
    assert!(
        warnings
            .iter()
            .any(|w| matches!(w, ChainWarning::WarmupLogDensity { .. }))
    );
    assert!(
        warnings
            .iter()
            .any(|w| matches!(w, ChainWarning::SampledLogDensity { .. }))
    );
    assert!(
        warnings
            .iter()
            .any(|w| matches!(w, ChainWarning::RHat { .. }))
    );
    let summary = Summary::from_output(&output, None).unwrap();
    assert_eq!(summary.chain_warnings, warnings);
    let text = summary.to_string();
    let lines: Vec<&str> = text
        .lines()
        .filter(|line| line.starts_with("warning: chain"))
        .collect();
    assert_eq!(lines.len(), 1, "one line per flagged chain:\n{text}");
    assert!(lines[0].starts_with("warning: chain 3 disagrees with the other chains: "));
    assert!(lines[0].contains("last-warmup-window median log density"));
    assert!(lines[0].contains("retained-draw median log density"));
    assert!(lines[0].contains("without this chain"));
}

#[test]
fn detect_applies_the_step_and_density_rules_and_their_guards() {
    let window = |step: f64, median: f64, iqr: f64| {
        ChainWindowSummary::new(450, 950, step, median, iqr).unwrap()
    };
    let w = [
        window(0.5, -10.0, 1.0),
        window(0.6, -10.5, 1.2),
        window(0.04, -10.2, 0.9),
        window(0.55, -20.0, 1.1),
    ];
    let warmup: Vec<Option<&ChainWindowSummary>> = w.iter().map(Some).collect();
    let warnings = ChainWarning::detect(&warmup, &[], None);
    // Step: median of (0.04, 0.5, 0.55, 0.6) = 0.525, threshold 0.0525.
    // Density: reference median(-20, -10.5, -10.2, -10) = -10.35, limit
    // 3 x median IQR (1.05) = 3.15; chain 3 is 9.65 below.
    assert_eq!(
        warnings,
        vec![
            ChainWarning::WarmupStep {
                chain: 2,
                step: 0.04,
                median_step: 0.525
            },
            ChainWarning::WarmupLogDensity {
                chain: 3,
                median_log_density: -20.0,
                reference: -10.35,
                threshold: 3.0 * 1.05
            },
        ]
    );
    // Fewer than three chains, a missing window, a short window or a
    // non-finite score skip the check.
    assert!(ChainWarning::detect(&warmup[..2], &[], None).is_empty());
    let missing = [warmup[0], warmup[1], None, warmup[3]];
    assert!(ChainWarning::detect(&missing, &[], None).is_empty());
    let short = ChainWindowSummary::new(940, 949, 0.01, -50.0, 1.0).unwrap();
    let with_short = [warmup[0], warmup[1], Some(&short), warmup[3]];
    assert!(ChainWarning::detect(&with_short, &[], None).is_empty());
    let nan = window(0.5, f64::NAN, 1.0);
    let with_nan = [warmup[0], Some(&nan), warmup[2], warmup[3]];
    let only_step = ChainWarning::detect(&with_nan, &[], None);
    assert!(
        only_step
            .iter()
            .all(|w| matches!(w, ChainWarning::WarmupStep { .. }))
    );
    assert!(ChainWindowSummary::new(10, 9, 0.1, 0.0, 1.0).is_err());
}

#[test]
fn posterior_exposes_the_checks_and_the_default_draws_are_unchanged() {
    let target = Gaussian(4);
    // 600 warmup / 600 draws on a 4-D Gaussian put every chain-agreement
    // statistic far from its threshold on every platform; at 300 / 200 the
    // R-hat check sat close enough to 1.01 to flip with libm rounding.
    let sampler = Sampler::new()
        .warmup(600)
        .draws(600)
        .chains(4)
        .seed(44)
        .metric(Metric::diagonal());
    let posterior = sampler.run_from_random_starts(&target).unwrap();
    assert!(
        posterior.chain_warnings().is_empty(),
        "{:?}",
        posterior.chain_warnings()
    );
    for telemetry in posterior.telemetry() {
        let warmup = telemetry.warmup_end().expect("warmup window");
        assert!(warmup.end() <= 600);
        let sampled = telemetry.sampling_end().expect("retained window");
        assert_eq!((sampled.start(), sampled.end()), (600, 1200));
    }
    // A run without warmup has no warmup window.
    let no_warmup = Sampler::new()
        .warmup(0)
        .draws(50)
        .chains(3)
        .seed(44)
        .metric(Metric::Identity)
        .adaptation(owalnuts::sampler::Adaptation::None)
        .run_from_random_starts(&target)
        .unwrap();
    assert!(no_warmup.telemetry().all(|t| t.warmup_end().is_none()));
    assert!(no_warmup.telemetry().all(|t| t.sampling_end().is_some()));
}

/// The `tests/nonfinite_position_policy.rs` cliff: `log p(x) = -G |x|` with
/// `G = 1e308`; the first half-kick at step 4 overflows and the default
/// `RejectLeaf` policy rescues the leaf without recording a divergence.
struct Cliff;

impl Target for Cliff {
    fn dimension(&self) -> usize {
        1
    }

    fn log_density_gradient(&self, q: &[f64], gradient: &mut [f64]) -> Result<f64, TargetError> {
        const G: f64 = 1e308;
        let x = q[0];
        if x.abs() >= 1.0 {
            return Err(TargetError::recoverable("cliff: |x| >= 1"));
        }
        gradient[0] = -G * x.signum();
        Ok(-G * x.abs())
    }
}

#[test]
fn nonfinite_rejections_are_reported_per_chain_and_by_phase() {
    use owalnuts::sampler::{Adaptation, Tuning};
    let posterior = Sampler::new()
        .warmup(3)
        .draws(5)
        .chains(2)
        .seed(11)
        .metric(Metric::fixed_diagonal(vec![1.0]))
        .adaptation(Adaptation::None)
        .tuning(
            Tuning::new()
                .step_size(4.0)
                .max_depth(3)
                .max_refinement_levels(2),
        )
        .run(&Cliff, &[vec![0.1], vec![-0.1]])
        .expect("the default policy rescues the overflowed leaves");
    let counts: Vec<(usize, usize)> = posterior
        .telemetry()
        .map(|t| {
            (
                t.discarded().nonfinite_position_rejections(),
                t.retained().nonfinite_position_rejections(),
            )
        })
        .collect();
    assert!(counts.iter().all(|&(w, s)| w >= 3 && s >= 5), "{counts:?}");
    // The rescue records no divergence, which is why the warning exists.
    assert!(posterior.telemetry().all(|t| t.total().divergences() == 0));

    let expected: Vec<ChainWarning> = counts
        .iter()
        .enumerate()
        .map(
            |(chain, &(warmup, sampling))| ChainWarning::NonfinitePositions {
                chain,
                warmup,
                sampling,
            },
        )
        .collect();
    let warnings = posterior.chain_warnings();
    assert_eq!(warnings, expected);
    assert!(warnings.iter().all(|w| !w.is_disagreement()));

    let summary = Summary::from_output(posterior.inner(), None).unwrap();
    assert_eq!(summary.chain_warnings, expected);
    let text = summary.to_string();
    let lines: Vec<&str> = text
        .lines()
        .filter(|line| line.starts_with("warning: chain"))
        .collect();
    let wanted: Vec<String> = counts
        .iter()
        .enumerate()
        .map(|(chain, (w, s))| {
            format!(
                "warning: chain {chain} rejected {w} nonfinite positions during warmup and {s} during sampling"
            )
        })
        .collect();
    assert_eq!(lines, wanted, "{text}");

    // Phase-only and singular wording; chains without rejections are silent.
    let only = ChainWarning::nonfinite_positions(&[(0, 0), (1, 0), (0, 7)]);
    assert_eq!(
        ChainWarning::lines(&only),
        vec![
            "warning: chain 1 rejected 1 nonfinite position during warmup".to_string(),
            "warning: chain 2 rejected 7 nonfinite positions during sampling".to_string(),
        ]
    );
    // A disagreement finding and a rejection on the same chain print as
    // two lines.
    let mut mixed = vec![ChainWarning::RHat {
        chain: 2,
        max_rhat: 1.2,
        max_rhat_without: 1.001,
    }];
    mixed.extend(only);
    let mixed_lines = ChainWarning::lines(&mixed);
    assert_eq!(mixed_lines.len(), 3);
    assert!(mixed_lines[1].starts_with("warning: chain 2 disagrees with the other chains: "));
    assert_eq!(
        mixed_lines[2],
        "warning: chain 2 rejected 7 nonfinite positions during sampling"
    );
}
