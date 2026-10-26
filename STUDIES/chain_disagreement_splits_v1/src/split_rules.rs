//! WP74 candidate split-aware chain-disagreement checks
//! (`STUDIES/chain_disagreement_splits_v1`), shared by every harness binary
//! through `#[path = "../split_rules.rs"] mod split_rules;`.
//!
//! Observe-only: everything here reads a finished run's retained draws and
//! its `RunTelemetry::warmup_end()` / `sampling_end()` window summaries, so
//! the draws are those of the plain default run. Frozen in
//! `PREREGISTRATION.md` before the first evidence cell.
//!
//! * `current`: the shipped `ChainWarning::from_chains` (WP44 D1-D4 plus
//!   `NonfinitePositions`), recorded verbatim.
//! * Candidate **K** (`pair_clusters`), primary (added after the smoke, before
//!   freezing): with at least 3 chains and the all-chain maximum rank R-hat
//!   above 1.01, two chains *agree* when the maximum rank R-hat over
//!   parameters of that pair alone is at most 1.01. The agreement graph's
//!   connected components are the clusters; the reference cluster is the
//!   largest (size tie: the higher mean retained-draw median log density;
//!   tie or undefined: the cluster holding the lowest chain index). K fires
//!   iff there are at least two clusters and the reference cluster has at
//!   least two chains; it names every chain outside the reference cluster.
//! * Candidate **S** (`split_rhat`), secondary: with at least 4 chains and the
//!   all-chain maximum rank R-hat above 1.01 (the `ChainDisagreement`
//!   threshold), every partition of the chains into two groups of at least
//!   two chains each is scored. A partition *agrees* when the maximum rank
//!   R-hat over parameters is at most 1.01 within each group. S fires iff
//!   some partition agrees; it reports the agreeing partition with the
//!   smallest larger-group-maximum (first in enumeration order on a tie) and
//!   names its smaller group, or, for equal groups, the group with the lower
//!   mean retained-draw median log density (the group without chain 0 if
//!   that is undefined or tied). This is D4's leave-one-out test extended to
//!   every complementary pair, with D4's columns, R-hat and threshold.
//! * Candidate **G** (`density_clusters`), third: on each of the two
//!   windows D2/D3 score (last slow warmup window, retained draws), with
//!   D2/D3's preconditions (>= 3 chains, every window >= 10 transitions,
//!   finite medians and IQRs), sort the chains' median log densities and cut
//!   between neighbours wherever the gap exceeds 3 x the median over chains
//!   of the within-chain IQR (D2/D3's scale). With two or more clusters, the
//!   reference cluster is the largest (on a tie, the one with the highest
//!   medians) and every chain outside it is named. Two-sided, unlike D2/D3.
//!
//! A candidate warning is the shipped warning plus the candidate's check
//! (additive: no shipped finding is removed).
use owalnuts::diagnostics::{ChainWarning, rhat};
use owalnuts::walnutpie::{ChainOutput, ChainWindowSummary};
use serde_json::{Value, json};

/// The `ChainDisagreement` threshold (`diagnostics::RHAT_DISAGREEMENT_THRESHOLD`).
pub const RHAT_THRESHOLD: f64 = 1.01;
/// D2/D3's scale: this many median within-chain IQRs.
pub const LOG_DENSITY_IQRS: f64 = 3.0;
/// D2/D3's minimum window.
pub const MIN_WINDOW: usize = 10;
/// S needs two groups of at least two chains.
pub const SPLIT_MIN_CHAINS: usize = 4;
/// G needs D2/D3's minimum.
pub const CLUSTER_MIN_CHAINS: usize = 3;

fn columns(chains: &[ChainOutput]) -> Vec<Vec<Vec<f64>>> {
    let dimension = chains.first().map_or(0, ChainOutput::dimension);
    (0..dimension)
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
        .collect()
}

/// Maximum rank R-hat over parameters on the chains in `subset` (NaN-ignoring
/// fold, as `ChainDisagreement::compute`).
fn max_rhat(columns: &[Vec<Vec<f64>>], subset: &[usize]) -> f64 {
    columns
        .iter()
        .map(|per_chain| {
            let views: Vec<&[f64]> = subset.iter().map(|&c| per_chain[c].as_slice()).collect();
            rhat(&views)
        })
        .fold(f64::NAN, f64::max)
}

/// Type-7 median (the `diagnostics` convention).
fn median_of(values: &[f64]) -> f64 {
    let mut sorted = values.to_vec();
    sorted.sort_by(|a, b| a.total_cmp(b));
    let n = sorted.len();
    if n == 0 {
        return f64::NAN;
    }
    let rank = 0.5 * (n - 1) as f64;
    let (low, high) = (rank.floor() as usize, rank.ceil() as usize);
    sorted[low] + (rank - low as f64) * (sorted[high] - sorted[low])
}

fn check_name(w: &ChainWarning) -> &'static str {
    match w {
        ChainWarning::WarmupStep { .. } => "warmup_step",
        ChainWarning::WarmupLogDensity { .. } => "warmup_log_density",
        ChainWarning::SampledLogDensity { .. } => "sampled_log_density",
        ChainWarning::RHat { .. } => "rhat",
        ChainWarning::NonfinitePositions { .. } => "nonfinite_positions",
        #[allow(unreachable_patterns)]
        _ => "other",
    }
}

fn sorted_unique(mut v: Vec<usize>) -> Vec<usize> {
    v.sort_unstable();
    v.dedup();
    v
}

/// Candidate K.
pub fn pair_clusters(chains: &[ChainOutput]) -> Value {
    let m = chains.len();
    if m < CLUSTER_MIN_CHAINS {
        return json!({"evaluated": false, "reason": "fewer than 3 chains", "fired": false, "named": []});
    }
    let first = &chains[0];
    if chains
        .iter()
        .any(|c| c.dimension() != first.dimension() || c.retained() != first.retained())
    {
        return json!({"evaluated": false, "reason": "shape mismatch", "fired": false, "named": []});
    }
    let cols = columns(chains);
    let all: Vec<usize> = (0..m).collect();
    let full = max_rhat(&cols, &all);
    if full.is_nan() || full <= RHAT_THRESHOLD {
        return json!({"evaluated": true, "max_rhat": full, "fired": false, "named": [], "pairs": []});
    }
    let mut parent: Vec<usize> = (0..m).collect();
    fn find(parent: &mut [usize], x: usize) -> usize {
        let mut r = x;
        while parent[r] != r {
            r = parent[r];
        }
        parent[x] = r;
        r
    }
    let mut pairs = Vec::new();
    for a in 0..m {
        for b in a + 1..m {
            let r = max_rhat(&cols, &[a, b]);
            let agree = r <= RHAT_THRESHOLD;
            pairs.push(json!({"pair": [a, b], "max_rhat": r, "agree": agree}));
            if agree {
                let (ra, rb) = (find(&mut parent, a), find(&mut parent, b));
                if ra != rb {
                    parent[ra.max(rb)] = ra.min(rb);
                }
            }
        }
    }
    let mut clusters: Vec<Vec<usize>> = Vec::new();
    let mut root_of: Vec<usize> = Vec::new();
    for c in 0..m {
        let r = find(&mut parent, c);
        match root_of.iter().position(|&x| x == r) {
            Some(i) => clusters[i].push(c),
            None => {
                root_of.push(r);
                clusters.push(vec![c]);
            }
        }
    }
    let sampled_median: Vec<Option<f64>> = chains
        .iter()
        .map(|c| c.telemetry().sampling_end().map(ChainWindowSummary::median_log_density))
        .collect();
    let mean_density = |g: &[usize]| -> Option<f64> {
        let v: Option<Vec<f64>> = g.iter().map(|&c| sampled_median[c]).collect();
        v.filter(|v| v.iter().all(|x| x.is_finite()))
            .map(|v| v.iter().sum::<f64>() / v.len() as f64)
    };
    // Clusters are in order of their lowest chain index; pick the largest,
    // then the higher mean density, then the earliest.
    let mut reference = 0usize;
    let mut how = "largest cluster";
    for i in 1..clusters.len() {
        let (ci, cr) = (clusters[i].len(), clusters[reference].len());
        if ci > cr {
            reference = i;
            how = "largest cluster";
        } else if ci == cr {
            match (mean_density(&clusters[i]), mean_density(&clusters[reference])) {
                (Some(a), Some(b)) if a > b => {
                    reference = i;
                    how = "size tie: higher retained log density";
                }
                (Some(a), Some(b)) if a < b => how = "size tie: higher retained log density",
                _ => how = "size tie: lowest chain index (density tie or undefined)",
            }
        }
    }
    let fired = clusters.len() >= 2 && clusters[reference].len() >= 2;
    let named: Vec<usize> = if fired {
        sorted_unique(
            clusters
                .iter()
                .enumerate()
                .filter(|(i, _)| *i != reference)
                .flat_map(|(_, c)| c.iter().copied())
                .collect(),
        )
    } else {
        Vec::new()
    };
    let text = if fired {
        format!(
            "chains {named:?} disagree with chains {:?}, which agree with each other: max R-hat {full:.3}",
            clusters[reference]
        )
    } else {
        String::new()
    };
    json!({"evaluated": true, "max_rhat": full, "fired": fired, "named": named, "clusters": clusters,
           "reference_cluster": clusters[reference], "reference_rule": how, "pairs": pairs, "text": text})
}

/// Candidate S.
pub fn split_rhat(chains: &[ChainOutput]) -> Value {
    let m = chains.len();
    if m < SPLIT_MIN_CHAINS {
        return json!({"evaluated": false, "reason": "fewer than 4 chains", "fired": false, "named": []});
    }
    let first = &chains[0];
    if chains
        .iter()
        .any(|c| c.dimension() != first.dimension() || c.retained() != first.retained())
    {
        return json!({"evaluated": false, "reason": "shape mismatch", "fired": false, "named": []});
    }
    let cols = columns(chains);
    let all: Vec<usize> = (0..m).collect();
    let full = max_rhat(&cols, &all);
    if full.is_nan() || full <= RHAT_THRESHOLD {
        return json!({"evaluated": true, "max_rhat": full, "fired": false, "named": [], "partitions": []});
    }
    let sampled_median: Vec<Option<f64>> = chains
        .iter()
        .map(|c| c.telemetry().sampling_end().map(ChainWindowSummary::median_log_density))
        .collect();
    let mut partitions = Vec::new();
    let mut best: Option<(f64, Vec<usize>, Vec<usize>, f64, f64)> = None;
    // Each unordered partition once: the group never contains chain 0.
    for mask in 1u64..(1u64 << m) {
        if mask & 1 == 1 {
            continue;
        }
        let group: Vec<usize> = (0..m).filter(|c| mask >> c & 1 == 1).collect();
        let rest: Vec<usize> = (0..m).filter(|c| mask >> c & 1 == 0).collect();
        if group.len() < 2 || rest.len() < 2 {
            continue;
        }
        let r_group = max_rhat(&cols, &group);
        let r_rest = max_rhat(&cols, &rest);
        let agree = r_group <= RHAT_THRESHOLD && r_rest <= RHAT_THRESHOLD;
        partitions.push(json!({"group": group, "rest": rest, "max_rhat_group": r_group,
                               "max_rhat_rest": r_rest, "agree": agree}));
        if agree {
            let worst = r_group.max(r_rest);
            if best.as_ref().is_none_or(|b| worst < b.0) {
                best = Some((worst, group, rest, r_group, r_rest));
            }
        }
    }
    let Some((_, group, rest, r_group, r_rest)) = best else {
        return json!({"evaluated": true, "max_rhat": full, "fired": false, "named": [],
                      "partitions": partitions});
    };
    let mean_density = |g: &[usize]| -> Option<f64> {
        let v: Option<Vec<f64>> = g.iter().map(|&c| sampled_median[c]).collect();
        v.filter(|v| v.iter().all(|x| x.is_finite()))
            .map(|v| v.iter().sum::<f64>() / v.len() as f64)
    };
    let (named, other, how) = if group.len() < rest.len() {
        (group.clone(), rest.clone(), "smaller group")
    } else if rest.len() < group.len() {
        (rest.clone(), group.clone(), "smaller group")
    } else {
        match (mean_density(&group), mean_density(&rest)) {
            (Some(a), Some(b)) if b < a => (rest.clone(), group.clone(), "lower retained log density"),
            (Some(a), Some(b)) if a < b => (group.clone(), rest.clone(), "lower retained log density"),
            _ => (group.clone(), rest.clone(), "group without chain 0 (density tie or undefined)"),
        }
    };
    let text = format!(
        "chains {named:?} agree with each other and disagree with chains {other:?}: max R-hat {full:.3} \
         falls to {r_group:.3} within {group:?} and {r_rest:.3} within {rest:?}"
    );
    json!({"evaluated": true, "max_rhat": full, "fired": true, "named": named, "other": other,
           "naming": how, "text": text, "partitions": partitions,
           "best": {"group": group, "rest": rest, "max_rhat_group": r_group, "max_rhat_rest": r_rest}})
}

fn cluster_window(windows: &[Option<&ChainWindowSummary>]) -> Value {
    if windows.len() < CLUSTER_MIN_CHAINS {
        return json!({"scored": false, "reason": "fewer than 3 chains", "named": []});
    }
    let Some(ws) = windows.iter().copied().collect::<Option<Vec<&ChainWindowSummary>>>() else {
        return json!({"scored": false, "reason": "a chain has no window", "named": []});
    };
    if ws.iter().any(|w| w.transitions() < MIN_WINDOW) {
        return json!({"scored": false, "reason": "window shorter than 10", "named": []});
    }
    let medians: Vec<f64> = ws.iter().map(|w| w.median_log_density()).collect();
    let iqrs: Vec<f64> = ws.iter().map(|w| w.log_density_iqr()).collect();
    if !medians.iter().chain(&iqrs).all(|x| x.is_finite()) {
        return json!({"scored": false, "reason": "nonfinite median or IQR", "named": []});
    }
    let threshold = LOG_DENSITY_IQRS * median_of(&iqrs);
    if !threshold.is_finite() {
        return json!({"scored": false, "reason": "nonfinite threshold", "named": []});
    }
    let mut order: Vec<usize> = (0..medians.len()).collect();
    order.sort_by(|&a, &b| medians[a].total_cmp(&medians[b]).then(a.cmp(&b)));
    let mut clusters: Vec<Vec<usize>> = vec![vec![order[0]]];
    let mut gaps = Vec::new();
    for pair in order.windows(2) {
        let gap = medians[pair[1]] - medians[pair[0]];
        gaps.push(gap);
        if gap > threshold {
            clusters.push(Vec::new());
        }
        clusters.last_mut().unwrap().push(pair[1]);
    }
    let fired = clusters.len() > 1;
    // Largest cluster; on a size tie the later one (higher medians).
    let reference = (0..clusters.len())
        .rev()
        .max_by_key(|&i| (clusters[i].len(), i))
        .unwrap();
    let named = if fired {
        sorted_unique(
            clusters
                .iter()
                .enumerate()
                .filter(|(i, _)| *i != reference)
                .flat_map(|(_, c)| c.iter().copied())
                .collect(),
        )
    } else {
        Vec::new()
    };
    json!({"scored": true, "medians": medians, "iqrs": iqrs, "threshold": threshold,
           "sorted_chains": order, "sorted_gaps": gaps, "clusters": clusters,
           "reference_cluster": clusters[reference], "fired": fired, "named": named,
           "max_gap_over_threshold": gaps.iter().copied().fold(0.0_f64, f64::max) / threshold})
}

/// Candidate G on both windows.
pub fn density_clusters(chains: &[ChainOutput]) -> Value {
    let warm: Vec<Option<&ChainWindowSummary>> =
        chains.iter().map(|c| c.telemetry().warmup_end()).collect();
    let samp: Vec<Option<&ChainWindowSummary>> =
        chains.iter().map(|c| c.telemetry().sampling_end()).collect();
    let w = cluster_window(&warm);
    let s = cluster_window(&samp);
    let mut named: Vec<usize> = Vec::new();
    for v in [&w, &s] {
        if let Some(a) = v["named"].as_array() {
            named.extend(a.iter().filter_map(|x| x.as_u64()).map(|x| x as usize));
        }
    }
    let named = sorted_unique(named);
    json!({"warmup_end": w, "sampling_end": s, "fired": !named.is_empty(), "named": named})
}

/// Everything the study records per run: the shipped warning, both
/// candidates, and the candidate warnings (shipped plus candidate).
pub fn evaluate(chains: &[ChainOutput]) -> Value {
    let current = ChainWarning::from_chains(chains);
    let current_chains = sorted_unique(
        current
            .iter()
            .filter(|w| w.is_disagreement())
            .map(ChainWarning::chain)
            .collect(),
    );
    let k = pair_clusters(chains);
    let s = split_rhat(chains);
    let g = density_clusters(chains);
    let named = |v: &Value| -> Vec<usize> {
        v["named"]
            .as_array()
            .map(|a| a.iter().filter_map(|x| x.as_u64()).map(|x| x as usize).collect())
            .unwrap_or_default()
    };
    let with = |extra: Vec<usize>| sorted_unique(current_chains.iter().copied().chain(extra).collect());
    let candidate_k = with(named(&k));
    let candidate_s = with(named(&s));
    let candidate_g = with(named(&g));
    json!({
        "schema": "chain-disagreement-splits-v1-rules",
        "current": {
            "warnings": current.iter().map(|w| json!({"check": check_name(w), "chain": w.chain(),
                                                      "disagreement": w.is_disagreement(),
                                                      "text": w.to_string()})).collect::<Vec<_>>(),
            "lines": ChainWarning::lines(&current),
            "disagreement_chains": current_chains,
            "fired": !current_chains.is_empty(),
        },
        "pair_clusters": k,
        "split_rhat": s,
        "density_clusters": g,
        "candidate_k": {"chains": candidate_k, "fired": !candidate_k.is_empty()},
        "candidate_s": {"chains": candidate_s, "fired": !candidate_s.is_empty()},
        "candidate_g": {"chains": candidate_g, "fired": !candidate_g.is_empty()},
    })
}
