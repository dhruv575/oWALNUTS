//! Stan/ArviZ-style convergence diagnostics and run summaries.
//!
//! The per-parameter functions take one parameter's draws as a slice of
//! chains (`&[&[f64]]`, every chain the same length) and follow the
//! definitions of Vehtari, Gelman, Simpson, Carpenter and Bürkner (2021),
//! *Rank-normalization, folding, and localization: an improved R-hat for
//! assessing convergence of MCMC*, as implemented by ArviZ:
//!
//! - [`rhat`]: rank-normalised split R-hat, the maximum of the bulk (rank
//!   z-scored) and tail (folded, rank z-scored) split R-hat values;
//! - [`ess_bulk`]: split ESS of the rank z-scored draws;
//! - [`ess_tail`]: the minimum of the 5% and 95% quantile ESS values;
//! - [`ess_quantile`], [`ess_mean`], [`mcse_mean`]: the remaining estimators
//!   Stan's `stansummary` and `az.summary` report.
//!
//! Every estimator is validated against `az.rhat`, `az.ess` and `az.mcse` in
//! `tests/diagnostics_arviz.rs` from a committed fixture
//! (`tests/data/arviz_fixture.json`).
//!
//! [`Summary`] combines the parameter table with sampler-health counts read
//! from the run telemetry (divergences, invalid evaluations, depth-cap and
//! refinement-level exhaustions, mean tree depth, step size) per chain and
//! pooled, and prints as an aligned table.
//!
//! Invalid inputs — no chains, chains of unequal length, fewer than four
//! draws, non-finite values — make the estimators return `NaN` rather than
//! panic, mirroring ArviZ; R-hat also needs at least two chains.

use std::fmt;

use crate::walnutpie::{ChainOutput, MultiChainOutput};

/// Default quantile probabilities reported by [`ParameterSummary`].
pub const SUMMARY_QUANTILES: [f64; 3] = [0.05, 0.5, 0.95];

const MIN_DRAWS: usize = 4;

fn validate(chains: &[&[f64]], min_chains: usize) -> Option<(usize, usize)> {
    let n_chain = chains.len();
    if n_chain < min_chains {
        return None;
    }
    let n_draw = chains[0].len();
    if n_draw < MIN_DRAWS {
        return None;
    }
    for chain in chains {
        if chain.len() != n_draw || chain.iter().any(|value| !value.is_finite()) {
            return None;
        }
    }
    Some((n_chain, n_draw))
}

fn flatten(chains: &[&[f64]]) -> Vec<f64> {
    chains
        .iter()
        .flat_map(|chain| chain.iter().copied())
        .collect()
}

/// Mean over every draw of every chain (`NaN` when there are no draws).
pub fn mean(chains: &[&[f64]]) -> f64 {
    let flat = flatten(chains);
    if flat.is_empty() {
        return f64::NAN;
    }
    flat.iter().sum::<f64>() / flat.len() as f64
}

fn mean_slice(values: &[f64]) -> f64 {
    values.iter().sum::<f64>() / values.len() as f64
}

/// Sample variance with one degree of freedom removed.
fn variance_slice(values: &[f64]) -> f64 {
    let n = values.len();
    if n < 2 {
        return f64::NAN;
    }
    let mean = mean_slice(values);
    values
        .iter()
        .map(|value| (value - mean).powi(2))
        .sum::<f64>()
        / (n - 1) as f64
}

/// Sample standard deviation (`ddof = 1`) over every draw of every chain.
pub fn sd(chains: &[&[f64]]) -> f64 {
    variance_slice(&flatten(chains)).sqrt()
}

/// R type-7 (linear interpolation) quantile of the pooled draws.
///
/// This is the definition used by `numpy.quantile`, `stansummary` and ArviZ.
/// Returns `NaN` for empty input or `prob` outside `[0, 1]`.
pub fn quantile(chains: &[&[f64]], prob: f64) -> f64 {
    let mut flat = flatten(chains);
    quantile_sorted_in_place(&mut flat, prob)
}

fn quantile_sorted_in_place(values: &mut [f64], prob: f64) -> f64 {
    if values.is_empty() || !(0.0..=1.0).contains(&prob) || values.iter().any(|v| v.is_nan()) {
        return f64::NAN;
    }
    values.sort_by(|a, b| a.partial_cmp(b).expect("no NaN after check"));
    let position = (values.len() - 1) as f64 * prob;
    let lower = position.floor() as usize;
    let upper = (lower + 1).min(values.len() - 1);
    let weight = position - lower as f64;
    values[lower] + weight * (values[upper] - values[lower])
}

/// Inverse of the standard normal CDF (Wichura's algorithm AS 241, PPND16;
/// relative accuracy about 1e-16). The coefficients are the published ones,
/// hence the precision allowance.
#[allow(clippy::excessive_precision)]
fn normal_quantile(p: f64) -> f64 {
    if !(0.0..=1.0).contains(&p) || p.is_nan() {
        return f64::NAN;
    }
    if p == 0.0 {
        return f64::NEG_INFINITY;
    }
    if p == 1.0 {
        return f64::INFINITY;
    }
    let q = p - 0.5;
    if q.abs() <= 0.425 {
        const A: [f64; 8] = [
            3.387_132_872_796_366_608,
            1.331_416_678_917_843_77e2,
            1.971_590_950_306_551_323e3,
            1.373_169_376_550_946_139e4,
            4.592_195_393_154_987_2e4,
            6.726_577_092_700_870_7e4,
            3.343_057_558_358_812_9e4,
            2.509_080_928_730_122_7e3,
        ];
        const B: [f64; 8] = [
            1.0,
            4.231_333_070_160_091_1e1,
            6.871_870_074_920_579_1e2,
            5.394_196_021_424_751e3,
            2.121_379_430_415_775_7e4,
            3.930_789_580_009_271e4,
            2.872_908_573_572_194_3e4,
            5.226_495_278_852_854_4e3,
        ];
        let r = 0.180_625 - q * q;
        return q * poly(&A, r) / poly(&B, r);
    }
    let r = if q < 0.0 { p } else { 1.0 - p };
    let r = (-r.ln()).sqrt();
    let value = if r <= 5.0 {
        const C: [f64; 8] = [
            1.423_437_110_749_683_577_34,
            4.630_337_846_156_545_295_9,
            5.769_497_221_460_691_405_5,
            3.647_848_324_763_204_605_04,
            1.270_458_252_452_368_382_58,
            2.417_807_251_774_506_117_66e-1,
            2.272_384_498_926_918_945_96e-2,
            7.745_450_142_783_414_075_64e-4,
        ];
        const D: [f64; 8] = [
            1.0,
            2.053_191_626_637_758_821_87,
            1.676_384_830_183_803_849_4,
            6.897_673_349_851_000_044_84e-1,
            1.481_039_764_274_800_074_49e-1,
            1.519_866_656_361_645_713_66e-2,
            5.475_938_084_995_344_946_0e-4,
            1.050_750_071_644_416_838_57e-9,
        ];
        let r = r - 1.6;
        poly(&C, r) / poly(&D, r)
    } else {
        const E: [f64; 8] = [
            6.657_904_643_501_103_777_2,
            5.463_784_911_164_114_369_9,
            1.784_826_539_917_291_335_8,
            2.965_605_718_285_048_711_2e-1,
            2.653_218_952_657_612_303_3e-2,
            1.242_660_947_388_078_437_9e-3,
            2.711_555_568_743_487_578_5e-5,
            2.010_334_399_292_288_131_1e-7,
        ];
        const F: [f64; 8] = [
            1.0,
            5.998_322_069_733_540_366_7e-1,
            1.369_298_809_227_358_057_9e-1,
            1.487_536_129_085_061_485_5e-2,
            7.868_691_311_456_132_591_7e-4,
            1.846_318_317_510_054_680_7e-5,
            1.421_511_758_316_445_734_5e-7,
            2.044_263_103_389_939_785_3e-15,
        ];
        let r = r - 5.0;
        poly(&E, r) / poly(&F, r)
    };
    if q < 0.0 { -value } else { value }
}

fn poly(coefficients: &[f64; 8], x: f64) -> f64 {
    coefficients
        .iter()
        .rev()
        .fold(0.0, |acc, &coefficient| acc * x + coefficient)
}

/// Average ranks (1-based, ties averaged), as `scipy.stats.rankdata`.
fn average_ranks(values: &[f64]) -> Vec<f64> {
    let mut order: Vec<usize> = (0..values.len()).collect();
    order.sort_by(|&a, &b| values[a].partial_cmp(&values[b]).expect("finite values"));
    let mut ranks = vec![0.0; values.len()];
    let mut start = 0;
    while start < order.len() {
        let mut end = start + 1;
        while end < order.len() && values[order[end]] == values[order[start]] {
            end += 1;
        }
        // Ranks start..end are 1-based start+1 ..= end; their mean:
        let rank = (start + 1 + end) as f64 / 2.0;
        for &index in &order[start..end] {
            ranks[index] = rank;
        }
        start = end;
    }
    ranks
}

/// Rank-normalise (z-scale) values across every chain jointly.
fn z_scale(values: &[f64]) -> Vec<f64> {
    let size = values.len() as f64;
    const C: f64 = 3.0 / 8.0;
    average_ranks(values)
        .into_iter()
        .map(|rank| normal_quantile((rank - C) / (size - 2.0 * C + 1.0)))
        .collect()
}

/// Split every chain into its first and last halves, giving `2 * chains`
/// chains of `draws / 2` draws (the middle draw of an odd-length chain is
/// dropped, as in ArviZ).
fn split_chains(chains: &[&[f64]]) -> Vec<Vec<f64>> {
    let n_draw = chains[0].len();
    let half = n_draw / 2;
    let mut split = Vec::with_capacity(2 * chains.len());
    for chain in chains {
        split.push(chain[..half].to_vec());
    }
    for chain in chains {
        split.push(chain[n_draw - half..].to_vec());
    }
    split
}

/// Apply `f` to the flattened draws of `chains` and reshape back.
fn map_flat(chains: &[Vec<f64>], f: impl Fn(&[f64]) -> Vec<f64>) -> Vec<Vec<f64>> {
    let n_draw = chains[0].len();
    let flat: Vec<f64> = chains.iter().flatten().copied().collect();
    f(&flat).chunks_exact(n_draw).map(<[f64]>::to_vec).collect()
}

fn as_views(chains: &[Vec<f64>]) -> Vec<&[f64]> {
    chains.iter().map(Vec::as_slice).collect()
}

/// Classic (non-split, non-normalised) potential scale reduction factor.
fn rhat_raw(chains: &[&[f64]]) -> f64 {
    let n_draw = chains[0].len() as f64;
    let chain_means: Vec<f64> = chains.iter().map(|chain| mean_slice(chain)).collect();
    let within: f64 = mean_slice(
        &chains
            .iter()
            .map(|chain| variance_slice(chain))
            .collect::<Vec<_>>(),
    );
    let between = n_draw * variance_slice(&chain_means);
    ((between / within + n_draw - 1.0) / n_draw).sqrt()
}

/// Rank-normalised, folded split R-hat (Vehtari et al. 2021), equal to
/// `az.rhat(method="rank")`.
///
/// Returns `NaN` for fewer than two chains, fewer than four draws, chains of
/// unequal length, non-finite draws, or draws without any variation.
pub fn rhat(chains: &[&[f64]]) -> f64 {
    if validate(chains, 2).is_none() {
        return f64::NAN;
    }
    let split = split_chains(chains);
    let bulk = rhat_raw(&as_views(&map_flat(&split, z_scale)));
    let folded = map_flat(&split, |flat| {
        let mut sorted = flat.to_vec();
        let median = quantile_sorted_in_place(&mut sorted, 0.5);
        z_scale(
            &flat
                .iter()
                .map(|value| (value - median).abs())
                .collect::<Vec<_>>(),
        )
    });
    let tail = rhat_raw(&as_views(&folded));
    bulk.max(tail)
}

/// Iterative radix-2 complex FFT in place (`inverse` omits the `1/n` scale).
fn fft(re: &mut [f64], im: &mut [f64], inverse: bool) {
    let n = re.len();
    debug_assert!(n.is_power_of_two());
    let mut j = 0;
    for i in 1..n {
        let mut bit = n >> 1;
        while j & bit != 0 {
            j ^= bit;
            bit >>= 1;
        }
        j |= bit;
        if i < j {
            re.swap(i, j);
            im.swap(i, j);
        }
    }
    let mut length = 2;
    while length <= n {
        let angle = 2.0 * std::f64::consts::PI / length as f64 * if inverse { 1.0 } else { -1.0 };
        let (w_re, w_im) = (angle.cos(), angle.sin());
        for start in (0..n).step_by(length) {
            let (mut cur_re, mut cur_im) = (1.0, 0.0);
            for k in 0..length / 2 {
                let (a, b) = (start + k, start + k + length / 2);
                let t_re = re[b] * cur_re - im[b] * cur_im;
                let t_im = re[b] * cur_im + im[b] * cur_re;
                re[b] = re[a] - t_re;
                im[b] = im[a] - t_im;
                re[a] += t_re;
                im[a] += t_im;
                let next_re = cur_re * w_re - cur_im * w_im;
                cur_im = cur_re * w_im + cur_im * w_re;
                cur_re = next_re;
            }
        }
        length <<= 1;
    }
}

/// Biased (`1/n`) autocovariance at every lag of one chain, via FFT.
fn autocovariance(chain: &[f64]) -> Vec<f64> {
    let n = chain.len();
    let m = (2 * n).next_power_of_two();
    let mean = mean_slice(chain);
    let mut re = vec![0.0; m];
    let mut im = vec![0.0; m];
    for (slot, value) in re.iter_mut().zip(chain) {
        *slot = value - mean;
    }
    fft(&mut re, &mut im, false);
    for (r, i) in re.iter_mut().zip(im.iter_mut()) {
        *r = *r * *r + *i * *i;
        *i = 0.0;
    }
    fft(&mut re, &mut im, true);
    re.truncate(n);
    let scale = 1.0 / (m as f64 * n as f64);
    for value in &mut re {
        *value *= scale;
    }
    re
}

/// Geyer initial-monotone-sequence ESS of already-split chains (ArviZ `_ess`).
fn ess_raw(chains: &[&[f64]]) -> f64 {
    let n_chain = chains.len();
    let n_draw = chains[0].len();
    let (mut lo, mut hi) = (f64::INFINITY, f64::NEG_INFINITY);
    for value in chains.iter().flat_map(|chain| chain.iter()) {
        lo = lo.min(*value);
        hi = hi.max(*value);
    }
    let size = (n_chain * n_draw) as f64;
    if hi - lo < 1e-15 {
        return size;
    }
    let acov: Vec<Vec<f64>> = chains.iter().map(|chain| autocovariance(chain)).collect();
    let chain_means: Vec<f64> = chains.iter().map(|chain| mean_slice(chain)).collect();
    let acov_mean = |lag: usize| mean_slice(&acov.iter().map(|row| row[lag]).collect::<Vec<_>>());
    let n = n_draw as f64;
    let mean_var = acov_mean(0) * n / (n - 1.0);
    let mut var_plus = mean_var * (n - 1.0) / n;
    if n_chain > 1 {
        var_plus += variance_slice(&chain_means);
    }

    let mut rho = vec![0.0; n_draw];
    let mut rho_even = 1.0;
    rho[0] = rho_even;
    let mut rho_odd = 1.0 - (mean_var - acov_mean(1)) / var_plus;
    rho[1] = rho_odd;

    // Geyer's initial positive sequence.
    let mut t: usize = 1;
    while t + 3 < n_draw && rho_even + rho_odd > 0.0 {
        rho_even = 1.0 - (mean_var - acov_mean(t + 1)) / var_plus;
        rho_odd = 1.0 - (mean_var - acov_mean(t + 2)) / var_plus;
        if rho_even + rho_odd >= 0.0 {
            rho[t + 1] = rho_even;
            rho[t + 2] = rho_odd;
        }
        t += 2;
    }
    let max_t = t as isize - 2;
    if rho_even > 0.0 {
        rho[(max_t + 1) as usize] = rho_even;
    }
    // Geyer's initial monotone sequence.
    let mut t: isize = 1;
    while t <= max_t - 2 {
        let i = t as usize;
        if rho[i + 1] + rho[i + 2] > rho[i - 1] + rho[i] {
            rho[i + 1] = (rho[i - 1] + rho[i]) / 2.0;
            rho[i + 2] = rho[i + 1];
        }
        t += 2;
    }

    let head: f64 = rho[..(max_t + 1).max(0) as usize].iter().sum();
    let tau_hat = -1.0 + 2.0 * head + rho[(max_t + 1) as usize];
    let tau_hat = tau_hat.max(1.0 / size.log10());
    if rho.iter().any(|value| value.is_nan()) {
        return f64::NAN;
    }
    size / tau_hat
}

/// Split ESS of the pooled mean (`az.ess(method="mean")`).
pub fn ess_mean(chains: &[&[f64]]) -> f64 {
    if validate(chains, 1).is_none() {
        return f64::NAN;
    }
    ess_raw(&as_views(&split_chains(chains)))
}

/// Bulk ESS: split ESS of the rank-normalised draws (`az.ess(method="bulk")`).
pub fn ess_bulk(chains: &[&[f64]]) -> f64 {
    if validate(chains, 1).is_none() {
        return f64::NAN;
    }
    let split = split_chains(chains);
    ess_raw(&as_views(&map_flat(&split, z_scale)))
}

/// ESS of the indicator `draw <= quantile(prob)`
/// (`az.ess(method="quantile", prob=prob)`).
pub fn ess_quantile(chains: &[&[f64]], prob: f64) -> f64 {
    if validate(chains, 1).is_none() || !(0.0..=1.0).contains(&prob) {
        return f64::NAN;
    }
    let threshold = quantile(chains, prob);
    let indicator: Vec<Vec<f64>> = chains
        .iter()
        .map(|chain| {
            chain
                .iter()
                .map(|value| if *value <= threshold { 1.0 } else { 0.0 })
                .collect()
        })
        .collect();
    ess_raw(&as_views(&split_chains(&as_views(&indicator))))
}

/// Tail ESS: the smaller of the 5% and 95% quantile ESS values
/// (`az.ess(method="tail")`).
pub fn ess_tail(chains: &[&[f64]]) -> f64 {
    ess_quantile(chains, 0.05).min(ess_quantile(chains, 0.95))
}

/// Monte Carlo standard error of the mean, `sd / sqrt(ess_mean)`
/// (`az.mcse(method="mean")`).
pub fn mcse_mean(chains: &[&[f64]]) -> f64 {
    if validate(chains, 1).is_none() {
        return f64::NAN;
    }
    sd(chains) / ess_mean(chains).sqrt()
}

/// One row of a [`Summary`] table.
#[derive(Clone, Debug, PartialEq)]
#[non_exhaustive]
pub struct ParameterSummary {
    pub name: String,
    pub mean: f64,
    pub sd: f64,
    pub mcse_mean: f64,
    /// Quantiles at [`SUMMARY_QUANTILES`] (5%, 50%, 95%).
    pub quantiles: [f64; 3],
    pub ess_bulk: f64,
    pub ess_tail: f64,
    pub rhat: f64,
}

impl ParameterSummary {
    /// Summarise one parameter from its chains.
    pub fn compute(name: impl Into<String>, chains: &[&[f64]]) -> Self {
        Self {
            name: name.into(),
            mean: mean(chains),
            sd: sd(chains),
            mcse_mean: mcse_mean(chains),
            quantiles: SUMMARY_QUANTILES.map(|prob| quantile(chains, prob)),
            ess_bulk: ess_bulk(chains),
            ess_tail: ess_tail(chains),
            rhat: rhat(chains),
        }
    }
}

/// Sampler-health counts over the retained transitions of one chain (or, for
/// [`SamplerHealth::pooled`], every chain).
#[derive(Clone, Debug, PartialEq)]
#[non_exhaustive]
pub struct ChainHealth {
    /// Retained transitions counted.
    pub transitions: usize,
    /// Transitions flagged divergent (energy error above the threshold).
    pub divergences: usize,
    /// Transitions stopped by an invalid (non-finite) target evaluation.
    pub invalid_evaluation_stops: usize,
    /// Transitions stopped because every refinement level was exhausted.
    pub refinement_exhaustion_stops: usize,
    /// Transitions stopped by the tree-depth cap.
    pub maximum_depth_stops: usize,
    /// Fused log-density/gradient calls made by the retained transitions.
    pub target_calls: usize,
    /// Mean tree depth of the retained transitions.
    pub mean_tree_depth: f64,
    /// Macro step size used for the retained transitions (pooled: the mean
    /// over chains).
    pub step_size: f64,
}

impl ChainHealth {
    /// Read the retained-phase counts of one chain.
    pub fn from_chain(chain: &ChainOutput) -> Self {
        let work = chain.telemetry().retained();
        let discarded = chain.metadata().discarded();
        let retained = &chain.diagnostics()[discarded.min(chain.diagnostics().len())..];
        let mean_tree_depth = if retained.is_empty() {
            f64::NAN
        } else {
            retained.iter().map(|d| d.depth() as f64).sum::<f64>() / retained.len() as f64
        };
        Self {
            transitions: work.transitions(),
            divergences: work.divergences(),
            invalid_evaluation_stops: work.invalid_evaluation_stops(),
            refinement_exhaustion_stops: work.refinement_exhaustion_stops(),
            maximum_depth_stops: work.maximum_depth_stops(),
            target_calls: work.target_calls_total(),
            mean_tree_depth,
            step_size: chain.metadata().tuning().step_size(),
        }
    }

    fn pooled(chains: &[ChainHealth]) -> Self {
        let total_transitions: usize = chains.iter().map(|c| c.transitions).sum();
        let mean_tree_depth = if total_transitions == 0 {
            f64::NAN
        } else {
            chains
                .iter()
                .map(|c| c.mean_tree_depth * c.transitions as f64)
                .sum::<f64>()
                / total_transitions as f64
        };
        let step_size = if chains.is_empty() {
            f64::NAN
        } else {
            chains.iter().map(|c| c.step_size).sum::<f64>() / chains.len() as f64
        };
        Self {
            transitions: total_transitions,
            divergences: chains.iter().map(|c| c.divergences).sum(),
            invalid_evaluation_stops: chains.iter().map(|c| c.invalid_evaluation_stops).sum(),
            refinement_exhaustion_stops: chains.iter().map(|c| c.refinement_exhaustion_stops).sum(),
            maximum_depth_stops: chains.iter().map(|c| c.maximum_depth_stops).sum(),
            target_calls: chains.iter().map(|c| c.target_calls).sum(),
            mean_tree_depth,
            step_size,
        }
    }
}

/// Per-chain and pooled [`ChainHealth`].
#[derive(Clone, Debug, PartialEq)]
#[non_exhaustive]
pub struct SamplerHealth {
    pub per_chain: Vec<ChainHealth>,
    pub pooled: ChainHealth,
}

impl SamplerHealth {
    pub fn from_chains(chains: &[ChainOutput]) -> Self {
        let per_chain: Vec<ChainHealth> = chains.iter().map(ChainHealth::from_chain).collect();
        let pooled = ChainHealth::pooled(&per_chain);
        Self { per_chain, pooled }
    }
}

/// Why a [`Summary`] could not be built.
#[derive(Clone, Debug, PartialEq, Eq)]
#[non_exhaustive]
pub enum SummaryError {
    /// No chains were supplied.
    NoChains,
    /// Chains disagree on dimension or retained draw count.
    ShapeMismatch,
    /// The supplied parameter-name list does not have one entry per dimension.
    NameCountMismatch { expected: usize, got: usize },
}

impl fmt::Display for SummaryError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::NoChains => f.write_str("no chains to summarise"),
            Self::ShapeMismatch => {
                f.write_str("chains disagree on dimension or retained draw count")
            }
            Self::NameCountMismatch { expected, got } => write!(
                f,
                "parameter names must have exactly {expected} entries (got {got})"
            ),
        }
    }
}

impl std::error::Error for SummaryError {}

/// Default CmdStan-style parameter names `theta.1 ..= theta.d`.
pub fn default_parameter_names(dimension: usize) -> Vec<String> {
    (1..=dimension).map(|i| format!("theta.{i}")).collect()
}

/// R-hat threshold above which [`ChainDisagreement`] names chains.
pub const RHAT_DISAGREEMENT_THRESHOLD: f64 = 1.01;

/// Which chain(s) a failed R-hat points at: the leave-one-chain-out
/// diagnostic of a [`Summary`].
///
/// For every chain the maximum rank R-hat over all parameters is recomputed
/// with that chain left out. A chain whose removal alone brings the maximum
/// below [`RHAT_DISAGREEMENT_THRESHOLD`] is a *disagreeing* chain: the other
/// chains agree with each other and this one does not (a chain stuck in a
/// second mode, a chain that never left its start). Empty when no single
/// chain explains the failure (two chains in a second mode, or every chain
/// mixing poorly) — the field says which case a failed run is in.
#[derive(Clone, Debug, PartialEq)]
#[non_exhaustive]
pub struct ChainDisagreement {
    /// Maximum rank R-hat over parameters with every chain.
    pub max_rhat: f64,
    /// Maximum rank R-hat over parameters without chain `i`, per chain.
    pub max_rhat_without: Vec<f64>,
    /// Chains whose removal alone brings the maximum R-hat below the
    /// threshold, in chain order.
    pub chains: Vec<usize>,
}

impl ChainDisagreement {
    /// Compute the diagnostic from per-parameter chain columns
    /// (`parameters[p][chain]`). `None` with fewer than three chains, with no
    /// parameter, or when the maximum R-hat is already below the threshold or
    /// undefined.
    pub fn compute(parameters: &[Vec<&[f64]>]) -> Option<Self> {
        let chains = parameters.first()?.len();
        if chains < 3 || parameters.iter().any(|columns| columns.len() != chains) {
            return None;
        }
        let max_rhat = parameters
            .iter()
            .map(|columns| rhat(columns))
            .fold(f64::NAN, f64::max);
        if !(max_rhat > RHAT_DISAGREEMENT_THRESHOLD) {
            return None;
        }
        let max_rhat_without: Vec<f64> = (0..chains)
            .map(|left_out| {
                parameters
                    .iter()
                    .map(|columns| {
                        let subset: Vec<&[f64]> = columns
                            .iter()
                            .enumerate()
                            .filter(|(index, _)| *index != left_out)
                            .map(|(_, column)| *column)
                            .collect();
                        rhat(&subset)
                    })
                    .fold(f64::NAN, f64::max)
            })
            .collect();
        let disagreeing = max_rhat_without
            .iter()
            .enumerate()
            .filter(|(_, value)| **value <= RHAT_DISAGREEMENT_THRESHOLD)
            .map(|(index, _)| index)
            .collect();
        Some(Self {
            max_rhat,
            max_rhat_without,
            chains: disagreeing,
        })
    }
}

/// A Stan/ArviZ-style run summary: one [`ParameterSummary`] row per
/// parameter plus [`SamplerHealth`].
#[derive(Clone, Debug, PartialEq)]
#[non_exhaustive]
pub struct Summary {
    pub chains: usize,
    pub draws_per_chain: usize,
    pub parameters: Vec<ParameterSummary>,
    pub health: SamplerHealth,
    /// Present when the maximum R-hat exceeds
    /// [`RHAT_DISAGREEMENT_THRESHOLD`] and there are at least three chains;
    /// see [`ChainDisagreement`].
    pub chain_disagreement: Option<ChainDisagreement>,
}

impl Summary {
    /// Summarise a multi-chain run. `names` defaults to
    /// [`default_parameter_names`].
    pub fn from_output(
        output: &MultiChainOutput,
        names: Option<&[String]>,
    ) -> Result<Self, SummaryError> {
        Self::from_chains(output.chains(), names)
    }

    /// Summarise chains produced by separate runs of the same target.
    pub fn from_chains(
        chains: &[ChainOutput],
        names: Option<&[String]>,
    ) -> Result<Self, SummaryError> {
        let first = chains.first().ok_or(SummaryError::NoChains)?;
        let dimension = first.dimension();
        let draws = first.retained();
        if chains
            .iter()
            .any(|chain| chain.dimension() != dimension || chain.retained() != draws)
        {
            return Err(SummaryError::ShapeMismatch);
        }
        let names = match names {
            Some(names) if names.len() != dimension => {
                return Err(SummaryError::NameCountMismatch {
                    expected: dimension,
                    got: names.len(),
                });
            }
            Some(names) => names.to_vec(),
            None => default_parameter_names(dimension),
        };
        let columns_by_parameter: Vec<Vec<Vec<f64>>> = (0..dimension)
            .map(|index| {
                chains
                    .iter()
                    .map(|chain| {
                        chain
                            .samples()
                            .iter()
                            .skip(index)
                            .step_by(dimension)
                            .copied()
                            .collect()
                    })
                    .collect()
            })
            .collect();
        let views: Vec<Vec<&[f64]>> = columns_by_parameter
            .iter()
            .map(|columns| as_views(columns))
            .collect();
        let parameters = names
            .into_iter()
            .zip(&views)
            .map(|(name, columns)| ParameterSummary::compute(name, columns))
            .collect();
        Ok(Self {
            chains: chains.len(),
            draws_per_chain: draws,
            parameters,
            health: SamplerHealth::from_chains(chains),
            chain_disagreement: ChainDisagreement::compute(&views),
        })
    }
}

fn fmt_num(value: f64) -> String {
    if value.is_nan() {
        "nan".to_string()
    } else if value == 0.0 {
        "0".to_string()
    } else if value.abs() >= 1e5 || value.abs() < 1e-3 {
        format!("{value:.3e}")
    } else {
        format!("{value:.3}")
    }
}

impl fmt::Display for Summary {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        let header = [
            "",
            "mean",
            "sd",
            "mcse_mean",
            "5%",
            "50%",
            "95%",
            "ess_bulk",
            "ess_tail",
            "rhat",
        ];
        let rows: Vec<Vec<String>> = self
            .parameters
            .iter()
            .map(|p| {
                vec![
                    p.name.clone(),
                    fmt_num(p.mean),
                    fmt_num(p.sd),
                    fmt_num(p.mcse_mean),
                    fmt_num(p.quantiles[0]),
                    fmt_num(p.quantiles[1]),
                    fmt_num(p.quantiles[2]),
                    fmt_num(p.ess_bulk),
                    fmt_num(p.ess_tail),
                    fmt_num(p.rhat),
                ]
            })
            .collect();
        let widths: Vec<usize> = (0..header.len())
            .map(|col| {
                rows.iter()
                    .map(|row| row[col].len())
                    .chain(std::iter::once(header[col].len()))
                    .max()
                    .unwrap_or(0)
            })
            .collect();
        writeln!(
            f,
            "Inference for {} chains x {} draws ({} retained draws):",
            self.chains,
            self.draws_per_chain,
            self.chains * self.draws_per_chain
        )?;
        writeln!(f)?;
        write_row(f, &header.map(str::to_string), &widths)?;
        for row in &rows {
            write_row(f, row, &widths)?;
        }
        writeln!(f)?;
        let h = &self.health.pooled;
        writeln!(
            f,
            "Sampler health (pooled over {} retained transitions):",
            h.transitions
        )?;
        writeln!(
            f,
            "  divergences={} invalid_evaluations={} depth_cap_stops={} \
             refinement_exhaustions={} mean_tree_depth={} target_calls={} step_size={}",
            h.divergences,
            h.invalid_evaluation_stops,
            h.maximum_depth_stops,
            h.refinement_exhaustion_stops,
            fmt_num(h.mean_tree_depth),
            h.target_calls,
            fmt_num(h.step_size),
        )?;
        for (index, c) in self.health.per_chain.iter().enumerate() {
            writeln!(
                f,
                "  chain {index}: divergences={} invalid_evaluations={} depth_cap_stops={} \
                 refinement_exhaustions={} mean_tree_depth={} target_calls={} step_size={}",
                c.divergences,
                c.invalid_evaluation_stops,
                c.maximum_depth_stops,
                c.refinement_exhaustion_stops,
                fmt_num(c.mean_tree_depth),
                c.target_calls,
                fmt_num(c.step_size),
            )?;
        }
        if let Some(d) = &self.chain_disagreement {
            let without: Vec<String> = d.max_rhat_without.iter().map(|v| fmt_num(*v)).collect();
            if d.chains.is_empty() {
                writeln!(
                    f,
                    "R-hat {} > {}: no single chain explains it (max R-hat without each chain: {})",
                    fmt_num(d.max_rhat),
                    RHAT_DISAGREEMENT_THRESHOLD,
                    without.join(", ")
                )?;
            } else {
                let names: Vec<String> = d.chains.iter().map(|c| c.to_string()).collect();
                writeln!(
                    f,
                    "R-hat {} > {}: chain(s) {} disagree with the rest (max R-hat without each chain: {})",
                    fmt_num(d.max_rhat),
                    RHAT_DISAGREEMENT_THRESHOLD,
                    names.join(", "),
                    without.join(", ")
                )?;
            }
        }
        Ok(())
    }
}

fn write_row(f: &mut fmt::Formatter<'_>, row: &[String], widths: &[usize]) -> fmt::Result {
    for (col, (cell, width)) in row.iter().zip(widths).enumerate() {
        if col == 0 {
            write!(f, "{cell:<width$}")?;
        } else {
            write!(f, "  {cell:>width$}")?;
        }
    }
    writeln!(f)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn normal_quantile_matches_known_values() {
        assert!((normal_quantile(0.5)).abs() < 1e-15);
        assert!((normal_quantile(0.975) - 1.959_963_984_540_054).abs() < 1e-12);
        assert!((normal_quantile(0.001) + 3.090_232_306_167_813).abs() < 1e-12);
        assert!((normal_quantile(1e-10) + 6.361_340_902_404_056).abs() < 1e-9);
    }

    #[test]
    fn average_ranks_handle_ties() {
        assert_eq!(
            average_ranks(&[3.0, 1.0, 2.0, 1.0]),
            vec![4.0, 1.5, 3.0, 1.5]
        );
    }

    #[test]
    fn autocovariance_matches_direct_sum() {
        let chain = [1.0, 3.0, 2.0, 5.0, 4.0, 4.5, 0.5];
        let mean = mean_slice(&chain);
        let acov = autocovariance(&chain);
        for (lag, value) in acov.iter().enumerate() {
            let direct: f64 = (0..chain.len() - lag)
                .map(|i| (chain[i] - mean) * (chain[i + lag] - mean))
                .sum::<f64>()
                / chain.len() as f64;
            assert!((value - direct).abs() < 1e-12, "lag {lag}");
        }
    }

    #[test]
    fn quantile_is_type_seven() {
        let chains: [&[f64]; 1] = [&[1.0, 2.0, 3.0, 4.0]];
        assert_eq!(quantile(&chains, 0.5), 2.5);
        assert_eq!(quantile(&chains, 0.25), 1.75);
        assert!(quantile(&chains, 1.5).is_nan());
    }

    #[test]
    fn chain_disagreement_names_the_odd_chain_out() {
        // Three chains around zero, one chain shifted: only its removal
        // brings R-hat down.
        let n = 200;
        let wave = |phase: f64, offset: f64| -> Vec<f64> {
            (0..n)
                .map(|i| {
                    offset + ((i as f64) * 0.7 + phase).sin() + ((i as f64) * 1.3).cos() * 0.5
                })
                .collect()
        };
        let chains = [wave(0.0, 0.0), wave(1.0, 0.0), wave(2.0, 0.0), wave(3.0, 5.0)];
        let views = [vec![
            chains[0].as_slice(),
            chains[1].as_slice(),
            chains[2].as_slice(),
            chains[3].as_slice(),
        ]];
        let d = ChainDisagreement::compute(&views).expect("R-hat fails");
        assert!(d.max_rhat > RHAT_DISAGREEMENT_THRESHOLD);
        assert_eq!(d.chains, vec![3]);
        assert!(d.max_rhat_without[3] <= RHAT_DISAGREEMENT_THRESHOLD);
        // Agreeing chains: no diagnostic.
        let agree = [vec![
            chains[0].as_slice(),
            chains[1].as_slice(),
            chains[2].as_slice(),
        ]];
        assert!(ChainDisagreement::compute(&agree).is_none());
        // Fewer than three chains: no diagnostic.
        let two = [vec![chains[0].as_slice(), chains[3].as_slice()]];
        assert!(ChainDisagreement::compute(&two).is_none());
    }

    #[test]
    fn invalid_shapes_yield_nan() {
        let a = [1.0, 2.0, 3.0, 4.0];
        let b = [1.0, 2.0, 3.0];
        assert!(rhat(&[&a, &b]).is_nan());
        assert!(rhat(&[&a]).is_nan());
        assert!(ess_bulk(&[&b]).is_nan());
        assert!(ess_bulk(&[]).is_nan());
        assert!(mean(&[]).is_nan());
    }
}
