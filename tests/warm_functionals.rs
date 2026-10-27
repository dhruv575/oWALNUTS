//! Streaming functionals on the warm path (WP95): the values a
//! `WarmSession::refresh_functionals` / `Sampler::run_warm_functionals`
//! call reports must be the functionals applied to the draws of the plain
//! `refresh` / `run_warm` with the same seed, bit for bit; the draws and
//! diagnostics must not depend on whether functionals are registered; and
//! the pooled statistics must agree with the per-draw values.

use std::sync::Arc;
use std::sync::atomic::{AtomicUsize, Ordering};

use owalnuts::sampler::{
    ErrorKind, Functional, FunctionalChunk, FunctionalError, FunctionalFn, Functionals,
    OutputMoments, RawFunctional, Sampler, Target, TargetError, Tuning, WarmChunk, WarmState,
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

const SEED: u64 = 0x5eed_0095;

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

/// `sigma = exp(x_last / 2)` and the last three coordinates.
fn functionals() -> Functionals {
    Functionals::new()
        .with(FunctionalFn::new(1, |q: &[f64], out: &mut [f64]| {
            out[0] = (q[q.len() - 1] / 2.0).exp();
        }))
        .with(FunctionalFn::new(3, |q: &[f64], out: &mut [f64]| {
            out.copy_from_slice(&q[q.len() - 3..]);
        }))
}

/// The functionals applied to every draw of `chunk`, draw-major.
fn expected_values(chunk: &WarmChunk, functionals: &Functionals) -> Vec<Vec<f64>> {
    (0..chunk.chains.len())
        .map(|chain| {
            let mut values = Vec::new();
            for draw in 0..chunk.draws {
                let position = chunk.draw(chain, draw).unwrap();
                for functional in functionals.functionals() {
                    let mut out = vec![0.0; functional.dimension()];
                    functional.evaluate(position, &mut out).unwrap();
                    values.extend(out);
                }
            }
            values
        })
        .collect()
}

fn assert_functional_chunk_matches(
    observed: &FunctionalChunk,
    plain: &WarmChunk,
    functionals: &Functionals,
) {
    assert_eq!(observed.seed, plain.seed);
    assert_eq!(observed.call_index, plain.call_index);
    assert_eq!(observed.draws, plain.draws);
    assert_eq!(observed.dimension, plain.dimension);
    assert_eq!(observed.outputs, functionals.outputs());
    assert_eq!(observed.target_calls, plain.target_calls);
    assert_eq!(observed.chains.len(), plain.chains.len());
    let expected = expected_values(plain, functionals);
    for (chain, (streamed, kept)) in observed.chains.iter().zip(&plain.chains).enumerate() {
        assert_eq!(streamed.values, expected[chain], "chain {chain} values");
        assert_eq!(
            streamed.diagnostics, kept.diagnostics,
            "chain {chain} diagnostics"
        );
        assert_eq!(
            streamed.telemetry, kept.telemetry,
            "chain {chain} telemetry"
        );
        assert_eq!(streamed.effective_seed, kept.effective_seed);
        assert_eq!(streamed.step_size, kept.step_size);
        assert_eq!(streamed.mass_diagonal, kept.mass_diagonal);
        assert_eq!(
            streamed.position.as_slice(),
            plain.draw(chain, plain.draws - 1).unwrap()
        );
        match &streamed.samples {
            Some(samples) => assert_eq!(samples, &kept.samples),
            None => assert!(!functionals.retains_draws()),
        }
        assert_eq!(streamed.moments.len(), functionals.outputs());
        for (output, moments) in streamed.moments.iter().enumerate() {
            let mut direct = OutputMoments::default();
            for value in streamed
                .values
                .iter()
                .skip(output)
                .step_by(functionals.outputs())
            {
                direct.push(*value);
            }
            assert_eq!(moments, &direct, "chain {chain} output {output} moments");
        }
    }
    assert_eq!(
        observed.warm_state().unwrap(),
        plain.warm_state().unwrap(),
        "warm state"
    );
}

#[test]
fn refresh_functionals_reports_the_functionals_of_refresh_draws_bit_for_bit() {
    let chains = 4;
    let start = adapted(6, chains);
    let functionals = functionals();
    for threads in [1, 4] {
        for retain in [false, true] {
            let functionals = functionals.clone().retain_draws(retain);
            let mut plain = Sampler::new()
                .seed(SEED)
                .threads(threads)
                .tuning(tuning())
                .start_warm_session(Gaussian(6), start.clone())
                .unwrap();
            let mut streaming = Sampler::new()
                .seed(SEED)
                .threads(threads)
                .tuning(tuning())
                .start_warm_session(Gaussian(6), start.clone())
                .unwrap();
            for draws in [5usize, 10, 7] {
                let expected = plain.refresh(draws).unwrap();
                let observed = streaming.refresh_functionals(draws, &functionals).unwrap();
                assert_functional_chunk_matches(&observed, &expected, &functionals);
                assert_eq!(streaming.state(), plain.state());
                assert_eq!(streaming.calls(), plain.calls());
                assert_eq!(
                    observed.chains[0].samples.is_some(),
                    retain,
                    "draws retained only on request"
                );
            }
            // Mixed calls: a plain refresh after functional ones continues
            // the same seed sequence, so the two sessions stay in step.
            assert_eq!(
                streaming.refresh(4).unwrap(),
                plain.refresh(4).unwrap(),
                "a plain refresh after functional calls"
            );
            assert_eq!(
                streaming.refresh_functionals(3, &functionals).unwrap(),
                plain.refresh_functionals(3, &functionals).unwrap()
            );
        }
    }
}

#[test]
fn run_warm_functionals_matches_run_warm_and_the_session() {
    let state = adapted(5, 3);
    let functionals = functionals();
    for threads in [1, 3] {
        let sampler = Sampler::new()
            .draws(12)
            .seed(77)
            .threads(threads)
            .tuning(tuning());
        let posterior = sampler.run_warm(&Gaussian(5), &state).unwrap();
        let chunk = sampler
            .run_warm_functionals(&Gaussian(5), &state, &functionals)
            .unwrap();
        assert_eq!(chunk.seed, 77);
        assert_eq!(chunk.call_index, 0);
        assert_eq!(chunk.target_calls, posterior.total_target_calls());
        for (chain, (observed, oracle)) in chunk.chains.iter().zip(posterior.chains()).enumerate() {
            assert_eq!(observed.diagnostics, oracle.diagnostics());
            let mut expected = Vec::new();
            for draw in 0..12 {
                let position = posterior.draw(chain, draw).unwrap();
                for functional in functionals.functionals() {
                    let mut out = vec![0.0; functional.dimension()];
                    functional.evaluate(position, &mut out).unwrap();
                    expected.extend(out);
                }
            }
            assert_eq!(observed.values, expected, "chain {chain}");
            assert_eq!(
                observed.position.as_slice(),
                posterior.draw(chain, 11).unwrap()
            );
        }
        assert_eq!(chunk.warm_state().unwrap(), posterior.warm_state().unwrap());
        // Call 0 of a session on the same sampler.
        let mut session = sampler
            .start_warm_session(Gaussian(5), state.clone())
            .unwrap();
        assert_eq!(
            session.refresh_functionals(12, &functionals).unwrap(),
            chunk
        );
    }
}

#[test]
fn functionals_follow_the_session_through_a_retarget() {
    let chains = 3;
    let state = adapted(6, chains);
    let functionals = functionals();
    let mut session = Sampler::new()
        .seed(SEED)
        .threads(3)
        .tuning(tuning())
        .start_warm_session(Gaussian(6), state)
        .unwrap();
    session.refresh_functionals(4, &functionals).unwrap();
    let grown = session.state().extend_to(7, 0.0, 1.0).unwrap();
    session.retarget(Gaussian(7), grown.clone()).unwrap();
    let expected = Sampler::new()
        .draws(6)
        .seed(SEED + chains as u64)
        .threads(3)
        .tuning(tuning())
        .run_warm_functionals(&Gaussian(7), &grown, &functionals)
        .unwrap();
    let observed = session.refresh_functionals(6, &functionals).unwrap();
    assert_eq!(observed.call_index, 1);
    assert_eq!(observed.dimension, 7);
    assert_eq!(observed.seed, expected.seed);
    assert_eq!(observed.chains, expected.chains);
    assert_eq!(session.state(), &observed.warm_state().unwrap());
}

#[test]
fn pooled_and_per_chain_statistics_agree_with_the_values() {
    let state = adapted(4, 3);
    let functionals = functionals();
    let chunk = Sampler::new()
        .draws(9)
        .seed(5)
        .tuning(tuning())
        .run_warm_functionals(&Gaussian(4), &state, &functionals)
        .unwrap();
    assert_eq!(chunk.outputs, 4);
    assert_eq!(chunk.output_range(0), Some(0..1));
    assert_eq!(chunk.output_range(1), Some(1..4));
    assert_eq!(chunk.output_range(2), None);
    for output in 0..chunk.outputs {
        let pooled: Vec<f64> = chunk.output(output).collect();
        assert_eq!(pooled.len(), 27);
        let mean = pooled.iter().sum::<f64>() / 27.0;
        let variance = pooled.iter().map(|x| (x - mean).powi(2)).sum::<f64>() / 26.0;
        let moments = chunk.moments(output).unwrap();
        assert_eq!(moments.count, 27);
        assert!((chunk.mean(output).unwrap() - mean).abs() < 1e-12);
        assert!((chunk.variance(output).unwrap() - variance).abs() < 1e-12 * variance.max(1.0));
        assert_eq!(
            moments.min,
            pooled.iter().copied().fold(f64::INFINITY, f64::min)
        );
        assert_eq!(
            moments.max,
            pooled.iter().copied().fold(f64::NEG_INFINITY, f64::max)
        );
        let mut sorted = pooled.clone();
        sorted.sort_by(f64::total_cmp);
        assert_eq!(chunk.quantile(output, 0.0), Some(sorted[0]));
        assert_eq!(chunk.quantile(output, 1.0), Some(sorted[26]));
        assert_eq!(chunk.quantile(output, 0.5), Some(sorted[13]));
        // Linear interpolation between order statistics: q = 0.9 on 27
        // values is virtual index 23.4.
        let q90 = sorted[23] + 0.4 * (sorted[24] - sorted[23]);
        assert!((chunk.quantile(output, 0.9).unwrap() - q90).abs() < 1e-12);
        for chain in 0..3 {
            let own: Vec<f64> = chunk.chain_output(chain, output).collect();
            assert_eq!(own.len(), 9);
            assert_eq!(own, pooled[chain * 9..(chain + 1) * 9]);
            let mut sorted = own.clone();
            sorted.sort_by(f64::total_cmp);
            assert_eq!(chunk.chain_quantile(chain, output, 0.5), Some(sorted[4]));
            assert_eq!(
                chunk.chain_moments(chain, output).unwrap().mean,
                chunk.chains[chain].moments[output].mean
            );
            assert_eq!(chunk.value(chain, 2, output), Some(own[2]));
        }
    }
    // The sigma functional is exp of the last coordinate / 2.
    for chain in 0..3 {
        for draw in 0..9 {
            let last = chunk.value(chain, draw, 3).unwrap();
            assert_eq!(chunk.value(chain, draw, 0), Some((last / 2.0).exp()));
        }
    }
    assert_eq!(chunk.quantile(4, 0.5), None);
    assert_eq!(chunk.quantile(0, 1.5), None);
    assert_eq!(chunk.chain_quantile(3, 0, 0.5), None);
    assert_eq!(chunk.value(0, 9, 0), None);
    assert_eq!(chunk.chain_draws(0), None);
}

#[test]
fn output_moments_merge_as_one_sample() {
    let mut a = OutputMoments::default();
    let mut b = OutputMoments::default();
    let mut all = OutputMoments::default();
    for (i, x) in [1.0, 4.0, 2.5, -3.0, 7.0, 0.5, 2.0].into_iter().enumerate() {
        if i < 3 {
            a.push(x)
        } else {
            b.push(x)
        };
        all.push(x);
    }
    let merged = a.merge(&b);
    assert_eq!(merged.count, 7);
    assert!((merged.mean - all.mean).abs() < 1e-12);
    assert!((merged.m2 - all.m2).abs() < 1e-12);
    assert_eq!(merged.min, -3.0);
    assert_eq!(merged.max, 7.0);
    assert_eq!(OutputMoments::default().merge(&a), a);
    assert_eq!(a.merge(&OutputMoments::default()), a);
    assert_eq!(OutputMoments::default().variance(), None);
    let mut one = OutputMoments::default();
    one.push(2.0);
    assert_eq!(one.variance(), None);
    assert_eq!(one.mean, 2.0);
}

#[test]
fn raw_functional_evaluates_the_c_callback() {
    unsafe extern "C" fn last_two(
        dimension: usize,
        position: *const f64,
        out: *mut f64,
        outputs: usize,
        user_data: *mut core::ffi::c_void,
    ) {
        assert_eq!(outputs, 2);
        assert!(user_data.is_null());
        // SAFETY: the test passes slices of the stated lengths.
        unsafe {
            *out = *position.add(dimension - 2);
            *out.add(1) = *position.add(dimension - 1);
        }
    }
    // SAFETY: `last_two` is pure, thread-safe and only touches its buffers.
    let raw = unsafe { RawFunctional::new(2, last_two, std::ptr::null_mut()) };
    let mut out = [0.0; 2];
    raw.evaluate(&[1.0, 2.0, 3.0, 4.0], &mut out).unwrap();
    assert_eq!(out, [3.0, 4.0]);
    let functionals = Functionals::new().with_arc(Arc::new(raw));
    let state = adapted(4, 2);
    let chunk = Sampler::new()
        .draws(5)
        .seed(3)
        .run_warm_functionals(&Gaussian(4), &state, &functionals)
        .unwrap();
    let posterior = Sampler::new()
        .draws(5)
        .seed(3)
        .run_warm(&Gaussian(4), &state)
        .unwrap();
    for chain in 0..2 {
        for draw in 0..5 {
            let position = posterior.draw(chain, draw).unwrap();
            assert_eq!(chunk.value(chain, draw, 0), Some(position[2]));
            assert_eq!(chunk.value(chain, draw, 1), Some(position[3]));
        }
    }
}

struct Failing {
    calls: AtomicUsize,
}

impl Functional for Failing {
    fn dimension(&self) -> usize {
        1
    }
    fn evaluate(&self, position: &[f64], out: &mut [f64]) -> Result<(), FunctionalError> {
        if self.calls.fetch_add(1, Ordering::Relaxed) >= 2 {
            return Err(FunctionalError::new("quote failed"));
        }
        out[0] = position[0];
        Ok(())
    }
}

#[test]
fn a_failing_functional_is_an_execution_error_and_ends_the_session() {
    let state = adapted(4, 2);
    let functionals = Functionals::new().with(Failing {
        calls: AtomicUsize::new(0),
    });
    let error = Sampler::new()
        .draws(5)
        .seed(3)
        .run_warm_functionals(&Gaussian(4), &state, &functionals)
        .unwrap_err();
    assert_eq!(error.kind(), ErrorKind::Target);
    assert!(error.to_string().contains("quote failed"), "{error}");
    let functionals = Functionals::new().with(Failing {
        calls: AtomicUsize::new(0),
    });
    let mut session = Sampler::new()
        .seed(3)
        .threads(2)
        .start_warm_session(Gaussian(4), state.clone())
        .unwrap();
    let error = session.refresh_functionals(5, &functionals).unwrap_err();
    assert_eq!(error.kind(), ErrorKind::Target);
    assert!(session.is_terminal());
    assert_eq!(session.calls(), 0);
    assert_eq!(session.state(), &state);
    // Zero draws and an empty functional list are configuration-level
    // cases: refused, or allowed with no outputs.
    let mut session = Sampler::new()
        .seed(3)
        .start_warm_session(Gaussian(4), state.clone())
        .unwrap();
    assert_eq!(
        session
            .refresh_functionals(0, &Functionals::new())
            .unwrap_err()
            .kind(),
        ErrorKind::Configuration
    );
    let empty = session.refresh_functionals(3, &Functionals::new()).unwrap();
    assert_eq!(empty.outputs, 0);
    assert!(empty.chains.iter().all(|c| c.values.is_empty()));
    assert_eq!(empty.mean(0), None);
    assert_eq!(session.calls(), 1);
    assert_eq!(
        Sampler::new()
            .draws(0)
            .run_warm_functionals(&Gaussian(4), &state, &Functionals::new())
            .unwrap_err()
            .kind(),
        ErrorKind::Configuration
    );
    assert_eq!(
        Sampler::new()
            .draws(2)
            .run_warm_functionals(&Gaussian(5), &state, &Functionals::new())
            .unwrap_err()
            .kind(),
        ErrorKind::Configuration
    );
}
