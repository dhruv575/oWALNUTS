#!/usr/bin/env python3
"""Writes protocol.json (the machine-readable preregistration of WP94). Run once before the freeze; the
committed protocol.json is the frozen copy and governs where PREREGISTRATION.md differs."""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent

HOUSE = [
    "eight_schools-eight_schools_noncentered", "eight_schools-eight_schools_centered", "diamonds-diamonds",
    "earnings-logearn_interaction", "mesquite-logmesquite_logvash", "kidiq-kidscore_momhsiq", "sblrc-blr",
    "nes2000-nes", "arK-arK", "arma-arma11", "garch-garch11", "gp_pois_regr-gp_pois_regr", "hmm_example-hmm_example",
    "bball_drive_event_0-hmm_drive_0", "one_comp_mm_elim_abs-one_comp_mm_elim_abs", "hudson_lynx_hare-lotka_volterra",
    "mcycle_gp-accel_gp",
]
HARD = ["GLMM_Poisson_data-GLMM_Poisson_model", "seeds_data-seeds_centered_model", "kilpisjarvi_mod-kilpisjarvi",
        "science_irt-grsm_latent_reg_irt", "radon_all-radon_hierarchical_intercept_centered"]
GATES_ONLY = ["GLMM_Poisson_data-GLMM_Poisson_model", "seeds_data-seeds_centered_model", "science_irt-grsm_latent_reg_irt",
              "radon_all-radon_hierarchical_intercept_centered"]
CANDIDATE = "gradinit"
NOGUARD = "gradinit-noguard"
ARMS = ["defaults", CANDIDATE, NOGUARD]
FUNNEL_ARMS = ["diag", CANDIDATE, NOGUARD, "diag-best16", f"{CANDIDATE}-best16"]
# S: 9490101-9490222 minus the two numbers that occur in STUDIES/options_flow_v1's seed-audit files (9490211, 9490212).
SEEDS = {"P": list(range(9450101, 9450107)), "F": list(range(9480301, 9480331)),
         "S": [s for s in range(9490101, 9490223) if s not in (9490211, 9490212)]}
assert len(SEEDS["S"]) == 120
SMOKE_SEED = 9459901

protocol = {
    "study": "grad_init_metric_v1",
    "ledger_id": "WP94-GRAD-INIT-METRIC-V1",
    "status": "FROZEN_BEFORE_FIRST_EVIDENCE_CELL",
    "frozen_utc": "2026-10-27",
    "question": "Does the gradient-scaled initial metric (nutpie's initial mass matrix: per chain mass_i = clamp(|g_i(start)|, 1e-20, 1e20) before any warmup transition; WP89's `nutpie_init`, which took oWALNUTS from 8/480 to 1/240 trapped chains on the SV model without any guard) qualify as a default-flip candidate on top of the shipped defaults (which since WP90 carry the trapped-chain guard), and does it alone, without the guard, remove the SV traps at the cause? Tested on the 22 v7 posteriors x 6 fresh seeds, the funnel tail check at 30 fresh seeds and the WP84 SV model at 120 fresh seeds, against the shipped defaults.",
    "base_commit_of_main": "a042a728",
    "library_under_test": "wt/grad-init-metric = main a042a728 plus the research flag WarmupConfig::with_initial_metric(InitialMetric::GradientScaled { lower, upper }) (InitialMetric::nutpie() = bounds 1e-20, 1e20), applied once per chain in ChainRun::start_from after the start is chosen and before the initial-step search; off by default (InitialMetric::AsGiven) and bit-identical when off (tests/grad_init_metric.rs; the kernel fingerprints are untouched). The `defaults` / `diag` arms are Sampler::new() as shipped, in the same `research` build (the feature changes no default; the smoke's custom_noop must be bit-identical to defaults).",
    "candidate": {
        "name": CANDIDATE,
        "rule": "Per chain, once, right after the chain's start is chosen (the facade's best-of-16 start; a trapped-chain replacement start is scaled from its own gradient the same way) and before the initial-step search and the first transition: the diagonal mass the chain starts warmup with is mass_i = clamp(|g_i(start)|, 1e-20, 1e20), g the log-density gradient at the start (an entry that is not finite becomes 1). This is nutpie's `update_diag_grad` initial rule (nuts-rs 0.17.3, src/mass_matrix/adapt.rs Strategy::init -> src/mass_matrix/diagonal.rs update_diag_grad -> src/cpu_math.rs array_update_var_inv_std_grad: variance_i = 1 / clamp(|g_i|, 1e-20, 1e20), non-finite -> 1; nutpie 0.16.8 pins nuts-rs 0.17.3). Everything after the first transition is unchanged: Stan's windows, the draw-variance estimator, the Stan regularisation, dual averaging from the same initial step, the WP90 guard at the first slow-window close. One extra target evaluation per chain start, counted in the admission bound.",
        "why": "WP89 (STUDIES/sv_stuck_chains_v1) found the mechanism of the SV traps: a stiff high-log_sigma start whose first transitions are rejected under the identity metric, a step collapse to 1e-7, and the Stan floor installed on every coordinate at transition 99. nutpie never traps and its initial metric alone (`nutpie_init`, oWALNUTS's own starts and adaptation) took the rate from 8/480 to 1/240; WP90 confirmed the restart guard, which removes the symptom (0/480) by restarting the trapped chain. The gradient-scaled initial metric fixes the cause (the first slow window is sampled with a sane metric), and because it changes the metric of the first 100 transitions on every model it needs the full house test.",
        "arms": {
            "defaults": "Sampler::new() with only the run shape (4 chains, 1,000/1,000 or the funnel's 2,000/20,000), seed, threads and Limits::new().admit_worst_case(); funnel: Metric::diagonal() and Adaptation::default() (`diag`); SV: Metric::diagonal(), Init::best_of(16) starts drawn in the cell exactly as Sampler::run_with_init draws them. Adaptation::default() carries DEFAULT_TRAPPED_CHAIN_RESTART (TrappedChainRestartConfig::guard(), WP90).",
            CANDIDATE: "the same plus Adaptation::Custom(WarmupConfig::new(0.8).with_warmup_exhaustion_rule(DEFAULT_WARMUP_EXHAUSTION).with_metric_regularization(DEFAULT_METRIC_REGULARIZATION).with_trapped_chain_restart(DEFAULT_TRAPPED_CHAIN_RESTART).with_initial_metric(InitialMetric::nutpie())), i.e. the configuration Adaptation::default() builds plus the candidate.",
            NOGUARD: "the candidate with the guard opted out: ...without_trapped_chain_restart().with_initial_metric(InitialMetric::nutpie()). Measures whether the cause-level fix alone removes the traps (R6) and what the guard adds on top of it; not itself a default-flip candidate.",
        },
    },
    "machine": "AWS c7a.4xlarge owalnuts-bench (i-05c712c79c74ae7f8, us-east-2), Ubuntu 24.04, rustc 1.88.0, lanes 1-2 (cores 0-7): two cells at a time, each pinned to 4 cores (taskset -c 0-3 and 4-7), RAYON_NUM_THREADS=4, OMP_NUM_THREADS=1, files under ~/lanes/grad_init_metric_v1/ only; co-tenanted with another study on cores 8-15 (shared L3 and memory bandwidth): walls are 'pinned, co-tenanted' and are not used in any rule; trapped counts, draw hashes, gates, ESS and gradient counts are unaffected.",
    "dispatch": "Part 1: owalnuts_bridgestan::ReplicatedStanTarget with 4 replicas (as WP85 / WP89 / WP90), 4 threads for 4 chains; BridgeStan 2.9.0 model libraries built by WP85 in its lane (copied byte-identically; sha256 recorded in artifacts/models.sha256). Parts 2-3: analytic Rust targets, 4 threads.",
    "models": HOUSE + HARD,
    "house_models": HOUSE,
    "hard_models": HARD,
    "gates_only_models": GATES_ONLY,
    "parameter_set": {
        "reference_posteriors": "columns of the posteriordb reference draws (18 posteriors: the 17 house models and kilpisjarvi); oWALNUTS draws constrained through BridgeStan with transformed parameters included (v6 rule); per-chain shift = max over reference parameters of |chain mean - reference mean| / reference SD",
        "gates_only_posteriors": "the four posteriors without posteriordb reference draws: every constrained parameter-block coordinate, transformed parameters and generated quantities excluded (WP46 rule); no z, no shift",
    },
    "posteriordb": {"path": "~/infra/posteriordb/posterior_database (read-only)", "commit": "28f8d3d", "reader": "files read directly; no posteriordb package"},
    "sv_model": {
        "target": "STUDIES/online_sv_quote_v1/rust/src/main.rs Sv, copied verbatim via WP89 / WP90 src/bin/sv_cell.rs; data models/data.json = WP84 simulate.py seed 84084 (sha256 9c183c8af22ac868bdbc8b59ee368e572dbbb4422a1e19baba794ad521dcf5c8), N = 250, dimension 253",
        "run_shape": "4 x 1,000/1,000, 4 threads, diagonal metric, admit_worst_case, Init::best_of(16)",
    },
    "seeds": {**SEEDS, "smoke": SMOKE_SEED},
    "seed_check": "git grep -ohwE over main a042a728 for \\b94501[0-9]{2}\\b (P), \\b94803[0-9]{2}\\b (F), \\b9490[12][0-9]{2}\\b (S) and \\b9459901\\b (smoke): the only hits were 9490211 and 9490212 (STUDIES/options_flow_v1 seed-audit files), which are excluded from S (9490101-9490222 minus those two = 120 seeds); the alternative block 9491101-9491220 had hits too (9491118, 9491123) and was not used. Sibling worktrees' STUDIES (functionals, tick-pooling, warm-drift): the same two hits only. Box lanes (~/lanes/*/repo/STUDIES/*/{protocol.json,PREREGISTRATION.md}) checked before the first cell (artifacts/environment.json box_seed_check).",
    "blocks": [
        {"name": "S", "part": "Part 3", "kind": "sv", "arms": ARMS, "seeds": SEEDS["S"],
         "note": "120 fresh seeds x {defaults, gradinit, gradinit-noguard}, seed-major; same seed = same 16 candidates and chosen start per chain in every arm"},
        {"name": "F", "part": "Part 2", "kind": "funnel", "arms": FUNNEL_ARMS, "seeds": SEEDS["F"],
         "note": "Neal's 10-D funnel, 4 x 2,000/20,000, 30 fresh seeds x {diag, gradinit, gradinit-noguard, diag-best16, gradinit-best16}, seed-major. The first three use the harness's fixed starts (omega in {-3, -1, 1, 3}, x = 0; R5 is scored on them, comparable to WP85 / WP89 / WP90); at x = 0 the x-gradients vanish and nutpie's rule puts the 1e-20 floor on 9 of 10 coordinates (seen in the Windows smoke: 3x the target calls at 200 warmup), so the two -best16 arms use the sampler's own Init::best_of(16) starts (reported: P5, firings, target calls; not ruled)"},
        {"name": "P", "part": "Part 1", "kind": "pdb", "arms": ARMS, "models": HOUSE + HARD, "seeds": SEEDS["P"],
         "note": "22 v7 posteriors (17 house + 5 hard) x 6 fresh seeds x {defaults, gradinit, gradinit-noguard} at 4 x 1,000/1,000; model-major in v7 order, seeds ascending, arms in the listed order"},
    ],
    "run_order": "S, then F, then P (the two short parts first so that the SV and funnel results exist even if the box is stopped). Two lanes: the manifest is split by position (lane 0 takes the even positions, lane 1 the odd ones), each lane runs its cells sequentially, one process per cell, pinned to its 4 cores; a started cell is never rerun; an errored or timed-out cell is a failed cell and counts against R1 / R7.",
    "funnel": {"warmup": 2000, "draws": 20000, "exact_p5": 0.0477903522728147, "statistic": "pooled mean over seeds of the retained-draw indicator omega < -5 (WP85 / WP66); s.e. = between-seed standard deviation / sqrt(30)"},
    "gates": {"max_rank_rhat": 1.01, "min_bulk_ess": 400, "min_tail_ess": 400, "sampling_divergences": 0, "finite_draws": True, "no_sampler_error": True,
              "note": "v7 gates on every parameter of the tier's parameter set (ArviZ 0.23.4, rank R-hat, bulk ESS, tail ESS at (0.05, 0.95)); WP85 scoring"},
    "sv_trapped_rule": {
        "anchor_log_sigma": -1.852786009877432, "anchor_h_last": -10.020535366127469,
        "log_sigma_tolerance": 1.0, "h_last_tolerance": 2.0,
        "definition": "WP89's frozen census with WP89's anchor (the medians over the 480 WP89 Part A nutpie chains of the chain-median retained log_sigma and h_last; artifacts/summary.json of STUDIES/sv_stuck_chains_v1): a chain is trapped iff |median retained log_sigma - anchor| > 1.0 or |median retained h_last - anchor| > 2.0. As in WP90.",
    },
    "timeouts": {"pdb_process_seconds": 2700, "funnel_process_seconds": 1800, "sv_process_seconds": 1800},
    "statistics": {
        "headline": "WP72 form (c): per model, the per-seed ratio candidate / defaults of min bulk ESS per gradient (gradients = every target call of the cell: start search, warmup, sampling, the candidate's one gradient per chain start and, on a fired cell, the abandoned run and the replacement pool) on seeds where both cells are ok, median across seeds; geomean over the 22 models, each needing at least 5 of 6 paired ok seeds (a model without 5 counts as failing R2). Reported alongside: the median of the 132 paired per-seed ratios with a 2,000-resample bootstrap 95 % interval, its range, and the same statistics for gradinit-noguard (reported, not ruled).",
        "warmup_gradients": "R3: per chain, the warmup target calls (WorkTotals of the discarded transitions, the abandoned run of a fired chain excluded as in WP90's chain totals); per cell, the ratio candidate / defaults of the median over the 4 chains; per model, the median over paired ok seeds; reported as the geomean over models and per model.",
        "gates_per_model": "R3's second clause: per model, the candidate's pass count over 6 seeds >= the defaults' pass count on that model.",
        "firings": "every TrappedChainCheck with restarted = true, per arm, counted over Parts 1-3 (gradinit-noguard has none by construction).",
    },
    "decision_rules": {
        "R1": "Part 1: gradinit passes >= defaults passes over the 132 cells per arm; every Part 1 cell of every arm completes (an error or timeout fails R1).",
        "R2": "Part 1 headline (WP72 form (c)) gradinit / defaults >= 0.98 over all 22 models, with the paired per-seed median and its bootstrap interval reported, and the per-model table.",
        "R3": "Part 1: warmup gradients per chain, the per-model median ratio gradinit / defaults reported with its geomean; and no model where the candidate's gates drop (per model, gradinit passes >= defaults passes).",
        "R4": "Part 1: no new divergences: per model, gradinit's retained divergences summed over 6 seeds <= the defaults'; and no cell that passes at the defaults has more retained divergences in the gradinit arm.",
        "R5": "Part 2: all 30 gradinit cells complete and |pooled P5(gradinit) - 0.0477903522728147| <= 2 x its between-seed s.e.; diag and gradinit-noguard reported.",
        "R6": "Part 3: gradinit-noguard trapped chains (frozen WP89 census) <= 1 of 480 (the WP89 prediction for the cause-level fix alone) AND gradinit trapped chains = 0 of 480; the guard's firing count under gradinit is reported (prediction: near 0).",
        "R7": "Library and flag-off integrity: tests/kernel_fingerprint.rs passes without and with the research feature (the fingerprints are untouched by the flag); tests/grad_init_metric.rs (flag off bit-identical, exact initial mass, 1- and 4-chain runs) and tests/trapped_chain_restart.rs pass; cargo clippy --all-targets --all-features -- -D warnings on the library and cargo clippy --all-targets -- -D warnings on the study crate pass on rustc 1.88; the smoke's custom_noop cells are bit-identical to their defaults cells (the research build changes no default).",
        "verdict": "gradinit QUALIFIES for a default-flip confirmation (proposed, not flipped) iff R1-R7 all hold; otherwise it stays research-only. Bit-identity to the defaults is NOT a rule: a candidate that changes the initial metric is allowed to change the draws everywhere. An implementation error anywhere (a cell error, a failed integrity check) fails the study.",
    },
    "predictions": {
        "P1": "Part 1 passes: defaults 88-100 of 132 (WP90: 92 on its seeds; WP85: 105); gradinit within -3..+4 of the defaults (the initial metric changes every chain's first 100 transitions; the gates are dominated by the retained window).",
        "P2": "R2 headline geomean in [0.97, 1.08]: the metric is identity-adapted by transition 100 either way, so retained ESS is unchanged in expectation and the gradient count moves with the first window's cost; paired per-seed median within [0.95, 1.10]. Models with a stiff start (kilpisjarvi, lotka_volterra, one_comp, GLMM_Poisson) gain; no model below 0.85 (reported, not ruled).",
        "P3": "R3 warmup-gradient geomean ratio gradinit / defaults in [0.80, 1.02]: fewer identity-phase gradients on the badly scaled models (the WP89 picture: 800 gradients per transition at depth 8-9 under the identity metric on the SV model), about equal elsewhere; no model's pass count drops.",
        "P4": "No new divergences on any model (R4 holds); divergence totals equal to the defaults' on at least 18 of 22 models.",
        "P5": "Funnel P5 within 2 s.e. for all three arms (WP85 diag 0.0492 +- 0.0017, WP89 0.0503 +- 0.0012, WP90 0.0458 +- 0.0016); 0 firings in the gradinit arm.",
        "P6": "SV: defaults trapped 3-16 of 480 with 6-16 guard firings (WP90: 8 and 13); gradinit-noguard trapped 0-2 of 480 (WP89 nutpie_init: 1/240); gradinit 0 of 480 with 0-3 guard firings.",
        "P7": "R7 holds: fingerprints untouched, the flag-off tests pass, clippy clean, custom_noop bit-identical to defaults on every smoke cell.",
        "verdict": "QUALIFIES for a confirmation (the SV mechanism is removed at the cause; the house set is unchanged within the rules).",
    },
    "proposed_next_step": "If every rule holds: a default-flip confirmation (WP85 / WP90 shape) of InitialMetric::nutpie() installed by Adaptation::warmup_config's with_defaults for the sampler's own adaptation modes on the identity and diagonal facades (the dense and structured facades keep rejecting it), the research gate lifted from with_initial_metric / InitialMetric, ALGORITHM_REVISION and the kernel fingerprints unchanged (tests/kernel_fingerprint.rs pins walnutpie::RunConfig runs, which take no sampler default), sampler-level draws changed everywhere (so the confirmation's rules are this study's, not bit-identity). Not applied by this study.",
    "budget": "about 3 h of lane time on two lanes once lanes 1-2 are free: Part 3 360 SV cells at about 2.3 s each plus trapped-chain overhead about 10 min on two lanes; Part 2 90 funnel cells about 3 min; Part 1 396 cells about 1.1 h on two lanes (WP90: 264 cells in 1 h 24 min on one lane); builds, library tests and the smoke about 15 min (built before the lanes are free).",
    "smoke": {"seed": SMOKE_SEED, "disclosed": "PREREGISTRATION.md, Smoke: non-evidence, before the freeze; kidiq defaults / custom_noop / gradinit / gradinit-noguard (custom_noop bit-identical to defaults expected), one gates-only cell per arm (GLMM_Poisson), one funnel quadruple, one SV quadruple, the analysis pipeline over them; on Windows before shipping, the funnel at 200/2,000 and one SV quadruple"},
    "cells_never_rerun": True,
}
(HERE / "protocol.json").write_text(json.dumps(protocol, indent=1) + "\n", encoding="utf-8")
print("protocol.json written:", sum(len(b["seeds"]) * len(b["arms"]) * len(b.get("models", [None])) for b in protocol["blocks"]), "cells")
