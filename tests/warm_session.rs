//! Resident warm session (`Sampler::start_warm_session`, `WarmSession`) and
//! the sliding-window state remap (`WarmState::remap`, `shift_window`):
//! every `refresh(k)` must be bit-identical to `Sampler::run_warm` under the
//! documented seed rule (call `n` uses `seed + n * chains`), before and
//! after a retarget, and the remaps must agree with `extend_to` where both
//! apply.

use std::sync::Arc;
use std::sync::atomic::{AtomicBool, Ordering};

use owalnuts::sampler::{
    Adaptation, Cancellation, ErrorKind, Limits, Metric, Posterior, Sampler, Target, TargetError,
    Tuning, WarmChain, WarmChunk, WarmState,
};

/// Independent Gaussian coordinates with scales `1, 2, 3, ...`.
struct Gaussian(usize);

impl Target for Gaussian {
    fn dimension(&self) -> usize {
        self.0
    }
    fn log_density_gradient(&self, q: &[f64], gradient: &mut [f64]) -> Result<f64, TargetError> {
        let mut value = 0.0;
        for (i, (g, x)) in gradient.iter_mut().zip(q).enumerate() {
            let variance = (1 + i) as f64;
            *g = -x / variance;
            value -= 0.5 * x * x / variance;
        }
        Ok(value)
    }
}

const SEED: u64 = 0x5eed_0091;

fn starts(chains: usize, dimension: usize) -> Vec<Vec<f64>> {
    (0..chains)
        .map(|c| {
            (0..dimension)
                .map(|i| 0.3 * (c as f64 + 1.0) * if (c + i) % 2 == 0 { 1.0 } else { -1.0 })
                .collect()
        })
        .collect()
}

fn adapted(dimension: usize, chains: usize) -> WarmState {
    Sampler::new()
        .warmup(120)
        .draws(10)
        .seed(SEED)
        .threads(2)
        .tuning(Tuning::new().max_depth(5))
        .run(&Gaussian(dimension), &starts(chains, dimension))
        .unwrap()
        .warm_state()
        .unwrap()
}

fn tuning() -> Tuning {
    Tuning::new().max_depth(6)
}

/// The oracle: `run_warm` with the call's base seed on the state before
/// the call.
fn oracle(
    target: &Gaussian,
    state: &WarmState,
    seed: u64,
    draws: usize,
    threads: usize,
) -> Posterior {
    Sampler::new()
        .draws(draws)
        .seed(seed)
        .threads(threads)
        .tuning(tuning())
        .run_warm(target, state)
        .unwrap()
}

fn assert_chunk_equals(chunk: &WarmChunk, expected: &Posterior, seed: u64) {
    assert_eq!(chunk.seed, seed);
    assert_eq!(chunk.chains.len(), expected.chain_count());
    assert_eq!(chunk.dimension, expected.dimension());
    assert_eq!(chunk.draws, expected.draws_per_chain());
    assert_eq!(chunk.target_calls, expected.total_target_calls());
    for (chain, (observed, oracle)) in chunk.chains.iter().zip(expected.chains()).enumerate() {
        assert_eq!(observed.samples, oracle.samples(), "chain {chain} draws");
        assert_eq!(
            observed.diagnostics,
            oracle.diagnostics(),
            "chain {chain} diagnostics"
        );
        assert_eq!(observed.effective_seed, oracle.metadata().effective_seed());
        assert_eq!(observed.step_size, oracle.metadata().tuning().step_size());
        assert_eq!(observed.mass_diagonal, oracle.metadata().mass_diagonal());
        assert_eq!(
            observed.telemetry.total().target_calls_total(),
            oracle.telemetry().total().target_calls_total()
        );
    }
    assert_eq!(chunk.warm_state().unwrap(), expected.warm_state().unwrap());
}

#[test]
fn refresh_is_bit_identical_to_run_warm_under_the_seed_rule() {
    let target = Gaussian(6);
    let chains = 4;
    let start = adapted(6, chains);
    for threads in [1, 4] {
        let mut session = Sampler::new()
            .seed(SEED)
            .threads(threads)
            .tuning(tuning())
            .start_warm_session(Gaussian(6), start.clone())
            .unwrap();
        assert_eq!(session.threads(), threads);
        assert_eq!(session.state(), &start);
        for (call, draws) in [5usize, 10, 7].into_iter().enumerate() {
            assert_eq!(session.calls(), call);
            let seed = SEED + (call * chains) as u64;
            assert_eq!(session.next_seed(), seed);
            assert_eq!(session.seed_for_call(call), seed);
            let before = session.state().clone();
            let expected = oracle(&target, &before, seed, draws, threads);
            let chunk = session.refresh(draws).unwrap();
            assert_eq!(chunk.call_index, call);
            assert_chunk_equals(&chunk, &expected, seed);
            assert_eq!(session.state(), &expected.warm_state().unwrap());
        }
        assert!(!session.is_terminal());
        session.close().unwrap();
    }
}

#[test]
fn refresh_matches_run_warm_with_the_worst_case_budget() {
    let target = Gaussian(5);
    let state = adapted(5, 3);
    let limits = Limits::new().admit_worst_case();
    let mut session = Sampler::new()
        .seed(7)
        .threads(3)
        .tuning(tuning())
        .limits(limits.clone())
        .start_warm_session(Gaussian(5), state.clone())
        .unwrap();
    let expected = Sampler::new()
        .draws(12)
        .seed(7)
        .threads(3)
        .tuning(tuning())
        .limits(limits)
        .run_warm(&target, &state)
        .unwrap();
    let chunk = session.refresh(12).unwrap();
    assert_chunk_equals(&chunk, &expected, 7);
}

#[test]
fn retarget_runs_on_the_new_target_and_continues_the_seed_sequence() {
    let chains = 4;
    let state = adapted(6, chains);
    let mut session = Sampler::new()
        .seed(SEED)
        .threads(2)
        .tuning(tuning())
        .start_warm_session(Gaussian(6), state)
        .unwrap();
    session.refresh(4).unwrap();
    session.refresh(4).unwrap();
    // WP88: one latent appended at the end.
    let grown = session.state().extend_to(7, 0.0, 1.0).unwrap();
    session.retarget(Gaussian(7), grown.clone()).unwrap();
    assert_eq!(session.state(), &grown);
    assert_eq!(session.calls(), 2);
    let seed = SEED + 2 * chains as u64;
    let expected = oracle(&Gaussian(7), &grown, seed, 6, 2);
    let chunk = session.refresh(6).unwrap();
    assert_chunk_equals(&chunk, &expected, seed);
    // A retarget to a smaller dimension is allowed too.
    let shrunk = session
        .state()
        .shift_window(2, 0, |_, _| (0.0, 1.0))
        .unwrap();
    session.retarget(Gaussian(5), shrunk.clone()).unwrap();
    let seed = SEED + 3 * chains as u64;
    let expected = oracle(&Gaussian(5), &shrunk, seed, 3, 2);
    assert_chunk_equals(&session.refresh(3).unwrap(), &expected, seed);
}

#[test]
fn fixed_lag_window_through_the_session_matches_run_warm_every_tick() {
    // A 1 + 5 state (a scale and five latents) that slides by one latent per
    // tick: the oldest latent is dropped, one new latent is appended at the
    // prior fill, the scale stays. Dimension is constant, so the target
    // type does not change; the target is rebuilt per tick as a real model
    // would be.
    let chains = 3;
    let state = adapted(6, chains);
    let mut session = Sampler::new()
        .seed(11)
        .threads(3)
        .tuning(tuning())
        .start_warm_session(Gaussian(6), state)
        .unwrap();
    for tick in 0..20usize {
        let next = session
            .state()
            .remap(
                6,
                |j| match j {
                    0 => Some(0),
                    1..=4 => Some(j + 1),
                    _ => None,
                },
                |chain, _| (0.1 * chain as f64, 1.0),
            )
            .unwrap();
        session.retarget(Gaussian(6), next.clone()).unwrap();
        let seed = 11 + (tick * chains) as u64;
        let expected = oracle(&Gaussian(6), &next, seed, 5, 3);
        assert_chunk_equals(&session.refresh(5).unwrap(), &expected, seed);
    }
    assert_eq!(session.calls(), 20);
}

#[test]
fn retarget_rejects_a_mismatched_state_without_ending_the_session() {
    let state = adapted(6, 4);
    let mut session = Sampler::new()
        .seed(3)
        .threads(2)
        .tuning(tuning())
        .start_warm_session(Gaussian(6), state.clone())
        .unwrap();
    let wrong_chains = WarmState::new(state.chains()[..2].to_vec()).unwrap();
    let error = session.retarget(Gaussian(6), wrong_chains).unwrap_err();
    assert_eq!(error.kind(), ErrorKind::Configuration);
    let error = session.retarget(Gaussian(8), state.clone()).unwrap_err();
    assert_eq!(error.kind(), ErrorKind::Configuration);
    assert!(!session.is_terminal());
    assert_eq!(session.state(), &state);
    let expected = oracle(&Gaussian(6), &state, 3, 4, 2);
    assert_chunk_equals(&session.refresh(4).unwrap(), &expected, 3);
}

#[test]
fn start_warm_session_validates_like_run_warm() {
    let state = adapted(6, 4);
    let error = Sampler::new()
        .chains(3)
        .start_warm_session(Gaussian(6), state.clone())
        .unwrap_err();
    assert_eq!(error.kind(), ErrorKind::Configuration);
    let error = Sampler::new()
        .start_warm_session(Gaussian(7), state.clone())
        .unwrap_err();
    assert_eq!(error.kind(), ErrorKind::Configuration);
    let error = Sampler::new()
        .threads(0)
        .start_warm_session(Gaussian(6), state)
        .unwrap_err();
    assert_eq!(error.kind(), ErrorKind::Configuration);
}

#[test]
fn zero_draws_and_a_refused_admission_leave_the_session_intact() {
    let state = adapted(4, 2);
    let mut session = Sampler::new()
        .seed(5)
        .tuning(tuning())
        .start_warm_session(Gaussian(4), state.clone())
        .unwrap();
    let error = session.refresh(0).unwrap_err();
    assert_eq!(error.kind(), ErrorKind::Configuration);
    assert!(!session.is_terminal());
    assert_eq!(session.calls(), 0);
    assert_chunk_equals(
        &session.refresh(3).unwrap(),
        &oracle(&Gaussian(4), &state, 5, 3, 2),
        5,
    );

    // A budget that admits one transition per chain but not two hundred:
    // the large call is refused before any target call, as `run_warm`
    // refuses it, and the session goes on; a budget below one transition
    // refuses the session itself.
    let one_draw = Sampler::new()
        .warmup(0)
        .adaptation(Adaptation::None)
        .metric(Metric::Identity)
        .draws(1)
        .tuning(tuning())
        .worst_case_target_evaluations(2)
        .unwrap();
    let limits = Limits::new().max_target_evaluations(one_draw);
    let mut budgeted = Sampler::new()
        .seed(5)
        .tuning(tuning())
        .limits(limits.clone())
        .start_warm_session(Gaussian(4), state.clone())
        .unwrap();
    let error = budgeted.refresh(200).unwrap_err();
    assert_eq!(error.kind(), ErrorKind::ResourceLimit);
    assert!(!budgeted.is_terminal());
    let expected = Sampler::new()
        .draws(1)
        .seed(5)
        .tuning(tuning())
        .limits(limits)
        .run_warm(&Gaussian(4), &state)
        .unwrap();
    assert_chunk_equals(&budgeted.refresh(1).unwrap(), &expected, 5);
    assert_eq!(
        Sampler::new()
            .limits(Limits::new().max_target_evaluations(8))
            .start_warm_session(Gaussian(4), state.clone())
            .unwrap_err()
            .kind(),
        ErrorKind::ResourceLimit
    );
}

#[test]
fn an_execution_error_is_terminal() {
    // A deadline already passed: the first transition's control check
    // fails inside the run, after admission.
    let state = adapted(4, 2);
    let mut session = Sampler::new()
        .seed(5)
        .threads(2)
        .limits(Limits::new().deadline(std::time::Instant::now()))
        .start_warm_session(Gaussian(4), state)
        .unwrap();
    let error = session.refresh(3).unwrap_err();
    assert_eq!(error.kind(), ErrorKind::DeadlineExceeded);
    assert!(session.is_terminal());
    assert_eq!(session.calls(), 0);
    assert_eq!(
        session.refresh(1).unwrap_err().kind(),
        ErrorKind::Configuration
    );
    assert_eq!(
        session
            .retarget(Gaussian(4), adapted(4, 2))
            .unwrap_err()
            .kind(),
        ErrorKind::Configuration
    );
    session.close().unwrap();
}

struct Flag(AtomicBool);

impl Cancellation for Flag {
    fn is_cancelled(&self) -> bool {
        self.0.load(Ordering::Acquire)
    }
}

#[test]
fn cancellation_ends_the_session_and_close_joins() {
    let state = adapted(4, 2);
    let flag = Arc::new(Flag(AtomicBool::new(false)));
    let mut session = Sampler::new()
        .seed(1)
        .threads(2)
        .limits(Limits::new().cancellation(flag.clone()))
        .start_warm_session(Gaussian(4), state)
        .unwrap();
    session.refresh(2).unwrap();
    flag.0.store(true, Ordering::Release);
    let error = session.refresh(2).unwrap_err();
    assert_eq!(error.kind(), ErrorKind::Cancelled);
    assert!(session.is_terminal());
    session.close().unwrap();
    assert!(session.refresh(1).is_err());
}

#[test]
fn close_then_refresh_errors_and_drop_does_not_block() {
    let state = adapted(4, 2);
    let mut session = Sampler::new()
        .seed(1)
        .threads(2)
        .start_warm_session(Gaussian(4), state.clone())
        .unwrap();
    session.close().unwrap();
    assert_eq!(
        session.refresh(1).unwrap_err().kind(),
        ErrorKind::Configuration
    );
    let dropped = Sampler::new()
        .seed(1)
        .start_warm_session(Gaussian(4), state)
        .unwrap();
    assert_eq!(format!("{dropped:?}").contains("WarmSession"), true);
    drop(dropped);
}

fn two_chain_state() -> WarmState {
    WarmState::new(vec![
        WarmChain {
            position: vec![1.0, 2.0, 3.0, 4.0],
            step_size: 0.5,
            mass_diagonal: vec![10.0, 20.0, 30.0, 40.0],
        },
        WarmChain {
            position: vec![-1.0, -2.0, -3.0, -4.0],
            step_size: 0.25,
            mass_diagonal: vec![11.0, 21.0, 31.0, 41.0],
        },
    ])
    .unwrap()
}

#[test]
fn remap_copies_mapped_coordinates_and_fills_the_rest() {
    let state = two_chain_state();
    // Reversed, one duplicated, one dropped, two filled per chain.
    let mapped = state
        .remap(
            5,
            |j| match j {
                0 => Some(3),
                1 => Some(3),
                2 => Some(0),
                _ => None,
            },
            |chain, j| (100.0 * chain as f64 + j as f64, 0.5 + j as f64),
        )
        .unwrap();
    assert_eq!(mapped.dimension(), 5);
    assert_eq!(mapped.chain_count(), 2);
    assert_eq!(mapped.chains()[0].position, vec![4.0, 4.0, 1.0, 3.0, 4.0]);
    assert_eq!(
        mapped.chains()[0].mass_diagonal,
        vec![40.0, 40.0, 10.0, 3.5, 4.5]
    );
    assert_eq!(
        mapped.chains()[1].position,
        vec![-4.0, -4.0, -1.0, 103.0, 104.0]
    );
    assert_eq!(
        mapped.chains()[1].mass_diagonal,
        vec![41.0, 41.0, 11.0, 3.5, 4.5]
    );
    assert_eq!(mapped.chains()[0].step_size, 0.5);
    assert_eq!(mapped.chains()[1].step_size, 0.25);
    // The identity map is a copy.
    assert_eq!(state.remap(4, Some, |_, _| (0.0, 1.0)).unwrap(), state);
}

#[test]
fn remap_rejects_out_of_range_sources_zero_dimension_and_bad_fills() {
    let state = two_chain_state();
    let error = state
        .remap(2, |j| Some(j + 3), |_, _| (0.0, 1.0))
        .unwrap_err();
    assert_eq!(error.kind(), ErrorKind::Configuration);
    assert!(error.to_string().contains("coordinate 4"));
    let error = state.remap(0, Some, |_, _| (0.0, 1.0)).unwrap_err();
    assert_eq!(error.kind(), ErrorKind::Configuration);
    let error = state.remap(2, |_| None, |_, _| (0.0, 0.0)).unwrap_err();
    assert_eq!(error.kind(), ErrorKind::Configuration);
    let error = state
        .remap(2, |_| None, |_, _| (f64::NAN, 1.0))
        .unwrap_err();
    assert_eq!(error.kind(), ErrorKind::Configuration);
}

#[test]
fn extend_with_and_extend_to_agree_with_remap() {
    let state = two_chain_state();
    let fill = |chain: usize, j: usize| (chain as f64 + 0.5, 1.0 + j as f64);
    let extended = state.extend_with(6, fill).unwrap();
    let remapped = state.remap(6, |j| (j < 4).then_some(j), fill).unwrap();
    assert_eq!(extended, remapped);
    assert_eq!(
        state.extend_to(5, 0.0, 1.0).unwrap(),
        state.shift_window(0, 1, |_, _| (0.0, 1.0)).unwrap()
    );
    assert_eq!(state.extend_to(4, 9.0, 9.0).unwrap(), state);
    assert!(state.extend_with(3, fill).is_err());
    assert_eq!(
        extended.chains()[1].position,
        vec![-1.0, -2.0, -3.0, -4.0, 1.5, 1.5]
    );
    assert_eq!(
        extended.chains()[1].mass_diagonal,
        vec![11.0, 21.0, 31.0, 41.0, 5.0, 6.0]
    );
}

#[test]
fn shift_window_drops_the_oldest_and_appends() {
    let state = two_chain_state();
    // The fixed-lag case: drop the oldest latent, append one.
    let shifted = state
        .shift_window(1, 1, |chain, j| (10.0 * chain as f64, j as f64))
        .unwrap();
    assert_eq!(shifted.dimension(), 4);
    assert_eq!(shifted.chains()[0].position, vec![2.0, 3.0, 4.0, 0.0]);
    assert_eq!(
        shifted.chains()[0].mass_diagonal,
        vec![20.0, 30.0, 40.0, 3.0]
    );
    assert_eq!(shifted.chains()[1].position, vec![-2.0, -3.0, -4.0, 10.0]);
    assert_eq!(
        shifted.chains()[1].mass_diagonal,
        vec![21.0, 31.0, 41.0, 3.0]
    );
    // Shrink only, and drop everything but append.
    let shrunk = state.shift_window(3, 0, |_, _| (0.0, 1.0)).unwrap();
    assert_eq!(shrunk.chains()[0].position, vec![4.0]);
    let fresh = state.shift_window(4, 2, |_, j| (j as f64, 1.0)).unwrap();
    assert_eq!(fresh.chains()[1].position, vec![0.0, 1.0]);
    // Errors: dropping more than the dimension, or everything with nothing
    // appended.
    assert_eq!(
        state
            .shift_window(5, 1, |_, _| (0.0, 1.0))
            .unwrap_err()
            .kind(),
        ErrorKind::Configuration
    );
    assert_eq!(
        state
            .shift_window(4, 0, |_, _| (0.0, 1.0))
            .unwrap_err()
            .kind(),
        ErrorKind::Configuration
    );
}

#[test]
fn shifted_state_chains_through_run_warm_ticks() {
    // The fixed-lag loop without a session: every tick drops the oldest of
    // five latents, appends one, and runs `run_warm` on the (constant-
    // dimension) target; the WP88 case appends only.
    let mut state = adapted(6, 2);
    for tick in 0..5u64 {
        state = state
            .remap(
                6,
                |j| match j {
                    0 => Some(0),
                    1..=4 => Some(j + 1),
                    _ => None,
                },
                |_, _| (0.0, 1.0),
            )
            .unwrap();
        let posterior = Sampler::new()
            .draws(4)
            .seed(100 + tick)
            .run_warm(&Gaussian(6), &state)
            .unwrap();
        state = posterior.warm_state().unwrap();
        assert_eq!(state.dimension(), 6);
    }
    let grown = state.shift_window(0, 1, |_, _| (0.0, 1.0)).unwrap();
    assert_eq!(grown, state.extend_to(7, 0.0, 1.0).unwrap());
    let posterior = Sampler::new()
        .draws(4)
        .seed(200)
        .run_warm(&Gaussian(7), &grown)
        .unwrap();
    assert_eq!(posterior.dimension(), 7);
}
