//! Gradient checks: every primitive against central finite differences, and
//! the reference models against their hand-written gradients.
#![forbid(unsafe_code)]

use owalnuts::walnutpie::{Target, TargetErrorKind};
use owalnuts_autodiff::models::{
    EightSchools, EightSchoolsVectorised, Funnel, LocalLevel, LocalLevelData,
    LocalLevelNoncentered, eight_schools_hand_gradient_const,
};
use owalnuts_autodiff::{
    AutodiffTarget, Const, Data, Linear, Model, NonfinitePolicy, Scalar, Shifted, Var,
    bernoulli_logit_lpmf, cauchy_lpdf, cumsum, cumsum_affine, dot, exp_constrain, exponential_lpdf,
    gamma_lpdf, gradient_with, half_normal_lpdf, interval_constrain, last_tape_stats, log_sum_exp,
    logistic_constrain, lognormal_lpdf, lower_bound_constrain, normal_lpdf, normal_lupdf,
    ordered_constrain, poisson_log_lpmf, softplus, student_t_lpdf, sum,
};
use rand::{Rng, SeedableRng, rngs::SmallRng};

/// Evaluate the same expression on the tape and by central differences of the
/// `f64` path. The value must be bit-identical between the two paths and the
/// gradient must agree to `1e-6` relative.
fn check_fd(name: &str, q: &[f64], tape: impl Fn(&[Var]) -> Var, plain: impl Fn(&[f64]) -> f64) {
    let n = q.len();
    let mut grad = vec![0.0; n];
    let value = gradient_with(q, &mut grad, |v| tape(v));
    let direct = plain(q);
    assert_eq!(
        value.to_bits(),
        direct.to_bits(),
        "{name}: tape value {value} != f64 value {direct}"
    );
    for i in 0..n {
        let h = 1e-5 * q[i].abs().max(1.0);
        let mut qp = q.to_vec();
        let mut qm = q.to_vec();
        qp[i] += h;
        qm[i] -= h;
        let fd = (plain(&qp) - plain(&qm)) / (2.0 * h);
        let scale = fd.abs().max(grad[i].abs()).max(1.0);
        assert!(
            (fd - grad[i]).abs() <= 1e-6 * scale,
            "{name}: d/dq[{i}] tape {} vs finite difference {fd}",
            grad[i]
        );
    }
}

macro_rules! fd {
    ($name:expr, $q:expr, |$v:ident| $body:expr) => {
        check_fd($name, $q, |$v: &[Var]| $body, |$v: &[f64]| $body)
    };
}

#[test]
fn elementary_operations() {
    let q = [0.7, -1.3, 2.1, 0.4];
    fd!("add", &q, |v| v[0] + v[1]);
    fd!("sub", &q, |v| v[0] - v[1]);
    fd!("mul", &q, |v| v[0] * v[1]);
    fd!("div", &q, |v| v[0] / v[1]);
    fd!("neg", &q, |v| -v[2]);
    fd!("add const", &q, |v| v[0] + 3.0);
    fd!("sub const", &q, |v| v[0] - 3.0);
    fd!("mul const", &q, |v| v[0] * 3.0);
    fd!("div const", &q, |v| v[0] / 3.0);
    fd!("rdiv", &q, |v| v[2].rdiv(3.0));
    fd!("rsub", &q, |v| v[2].rsub(3.0));
    fd!("exp", &q, |v| v[0].exp());
    fd!("ln", &q, |v| v[2].ln());
    fd!("sqrt", &q, |v| v[2].sqrt());
    fd!("powi", &q, |v| v[1].powi(3));
    fd!("powf", &q, |v| v[2].powf(1.7));
    fd!("tanh", &q, |v| v[1].tanh());
    fd!("log1p", &q, |v| v[3].log1p());
    fd!("expm1", &q, |v| v[3].expm1());
    fd!("abs", &q, |v| v[1].abs() + v[0].abs());
    fd!("square", &q, |v| v[1].square());
    fd!("recip", &q, |v| v[1].recip());
    fd!("softplus", &q, |v| softplus(v[1]) + softplus(v[2]));
    fd!("sigmoid", &q, |v| v[1].sigmoid());
    fd!("assign ops", &q, |v| {
        let mut a = v[0];
        a += v[1];
        a *= v[2];
        a -= v[3];
        a /= v[2];
        a += 1.5;
        a *= 2.0;
        a -= 0.5;
        a /= 4.0;
        a
    });
    fd!("iterator sum", &q, |v| v.iter().map(|x| x.square()).sum());
    fd!("composite", &q, |v| {
        (v[0] * v[1]).exp() / (v[2].ln() + v[3].square()) - (v[0] - v[3]).tanh()
    });
    fd!("same operand twice", &q, |v| v[0] * v[0] + v[0] / v[0]);
    fd!("constant output", &q, |_v| Scalar::from_f64(2.5));
}

#[test]
fn comparisons_use_values() {
    let q = [1.0, 2.0];
    fd!("branch", &q, |v| if v[0] < v[1] {
        v[0] * v[1]
    } else {
        v[0]
    });
    let a = Var::constant(1.0);
    let b = Var::constant(2.0);
    assert!(a < b);
    assert!(a != b);
    assert!(a.is_constant());
}

#[test]
fn normal_lpdf_broadcasting() {
    let q = [0.3, -0.7, 1.2, 0.1, 0.9, 2.0];
    // Scalars, all parameters.
    fd!("normal scalar", &q, |v| normal_lpdf(v[0], v[1], v[2].exp()));
    // Vector x, scalar parameters.
    fd!("normal vec x", &q, |v| normal_lpdf(
        &v[..3],
        v[3],
        v[4].exp()
    ));
    // Vector x and vector mu, data sigma.
    fd!("normal vec x vec mu", &q, |v| normal_lpdf(
        &v[..3],
        &v[3..6],
        Const(0.8)
    ));
    // Data x, vector mu, scalar sigma.
    fd!("normal data x", &q, |v| normal_lpdf(
        Data(&[0.1, 0.2, 0.3]),
        &v[..3],
        v[5]
    ));
    // Everything a vector.
    fd!("normal all vec", &q, |v| normal_lpdf(
        &v[..2],
        &v[2..4],
        &[v[4].exp(), v[5]][..]
    ));
    // Shifted mean and a data vector of sigmas.
    fd!("normal shifted", &q, |v| normal_lpdf(
        &v[1..4],
        Shifted(&v[..3], 0.25),
        Data(&[0.5, 0.6, 0.7])
    ));
    // Broadcast scalar Var x against a vector of means.
    fd!("normal scalar x vec mu", &q, |v| normal_lpdf(
        v[0],
        &v[1..4],
        Const(1.5)
    ));
    // Linear predictor operand, contiguous and scattered.
    fd!("normal linear", &q, |v| normal_lpdf(
        Data(&[0.1, 0.2, 0.3]),
        Linear::new(v[3], v[4], &v[..3]),
        v[5].exp()
    ));
    fd!("normal linear scattered", &q, |v| {
        let x = [v[0] * v[1], v[2], v[3].exp()];
        normal_lpdf(&v[3..6], Linear::new(v[0], v[5], &x), Const(2.0))
    });
    fd!("normal linear length one", &q, |v| normal_lpdf(
        Data(&[0.1]),
        Linear::new(v[3], v[4], &v[..1]),
        v[5].exp()
    ));
    // Unnormalised: data sigma drops the log term, parameter sigma keeps it.
    fd!("normal_lupdf data sigma", &q, |v| normal_lupdf(
        &v[..3],
        v[3],
        Data(&[0.5, 0.6, 0.7])
    ));
    fd!("normal_lupdf var sigma", &q, |v| normal_lupdf(
        &v[..3],
        v[3],
        v[5].exp()
    ));
    {
        let x = [0.3, -0.7, 1.2];
        let full: f64 = normal_lpdf(&x[..], 0.1, 0.8);
        let unnorm: f64 = normal_lupdf(&x[..], 0.1, 0.8);
        let data_sigma: f64 = normal_lupdf(&x[..], 0.1, Const(0.8));
        assert!((full - unnorm + 1.5 * 1.837_877_066_409_345_3).abs() < 1e-12);
        assert!((unnorm - data_sigma + 3.0 * (0.8f64).ln()).abs() < 1e-12);
    }
    // Vec<S> operands.
    fd!("normal vec ref", &q, |v| {
        let x: Vec<_> = v[..3].to_vec();
        normal_lpdf(&x, Const(0.0), Const(1.0))
    });
}

#[test]
fn distribution_primitives() {
    let q = [0.3, -0.7, 1.2, 0.1, 0.9, 2.0];
    fd!("student_t scalar", &q, |v| student_t_lpdf(
        v[0],
        3.5,
        v[1],
        v[2].exp()
    ));
    fd!("student_t vec", &q, |v| student_t_lpdf(
        &v[..3],
        7.0,
        v[3],
        v[4].exp()
    ));
    fd!("cauchy scalar", &q, |v| cauchy_lpdf(v[0], v[1], v[2].exp()));
    fd!("cauchy vec", &q, |v| cauchy_lpdf(&v[..4], v[4], v[5]));
    fd!("lognormal", &q, |v| lognormal_lpdf(v[2], v[1], v[5].exp()));
    fd!("lognormal vec", &q, |v| lognormal_lpdf(
        &[v[2], v[4], v[5]][..],
        v[1],
        v[0].exp()
    ));
    fd!("exponential", &q, |v| exponential_lpdf(v[2], v[4]));
    fd!("exponential vec", &q, |v| exponential_lpdf(
        &v[2..6],
        v[0].exp()
    ));
    fd!("gamma", &q, |v| gamma_lpdf(v[2], v[4] * 3.0, v[5]));
    fd!("gamma vec", &q, |v| gamma_lpdf(
        &[v[2], v[4], v[5]][..],
        v[0].exp() * 2.0,
        v[3].exp()
    ));
    fd!("half_normal", &q, |v| half_normal_lpdf(v[2], v[4]));
    fd!("half_normal vec", &q, |v| half_normal_lpdf(
        &[v[2], v[4], v[5]][..],
        v[0].exp()
    ));
    fd!("bernoulli_logit vec", &q, |v| bernoulli_logit_lpmf(
        Data(&[1.0, 0.0, 1.0, 1.0, 0.0, 0.0]),
        v
    ));
    fd!("bernoulli_logit scalar eta", &q, |v| bernoulli_logit_lpmf(
        Data(&[1.0, 0.0, 1.0]),
        v[1]
    ));
    fd!("bernoulli_logit scalar", &q, |v| bernoulli_logit_lpmf(
        Const(1.0),
        v[2]
    ));
    fd!("poisson_log vec", &q, |v| poisson_log_lpmf(
        Data(&[0.0, 3.0, 1.0, 7.0, 2.0, 0.0]),
        v
    ));
    fd!("poisson_log scalar", &q, |v| poisson_log_lpmf(
        Const(4.0),
        v[2]
    ));
}

#[test]
fn reductions() {
    let q = [0.3, -0.7, 1.2, 0.1, 0.9, 2.0];
    fd!("dot vec vec", &q, |v| dot(&v[..3], &v[3..6]));
    fd!("dot same", &q, |v| dot(&v[..4], &v[..4]));
    fd!("dot vec scalar", &q, |v| dot(&v[..5], v[5]));
    fd!("dot vec data", &q, |v| dot(
        v,
        Data(&[1.0, 2.0, 3.0, 4.0, 5.0, 6.0])
    ));
    fd!("dot scalar scalar", &q, |v| dot(v[0], v[1]));
    fd!("sum", &q, |v| sum(v));
    fd!("sum scalar", &q, |v| sum(v[2]));
    fd!("log_sum_exp", &q, |v| log_sum_exp(v));
    fd!("log_sum_exp scalar", &q, |v| log_sum_exp(v[2]));
    fd!("cumsum", &q, |v| {
        let c = cumsum(v);
        dot(&c, Data(&[1.0, -2.0, 3.0, 0.5, -1.0, 2.0]))
    });
    fd!("cumsum squared", &q, |v| {
        let c = cumsum(v);
        dot(&c, &c)
    });
    // Block node over a contiguous input, chain fallback over scattered input.
    fd!("cumsum_affine contiguous", &q, |v| {
        let c = cumsum_affine(&v[1..5], 0.3, -0.2);
        dot(&c, Data(&[1.0, -2.0, 3.0, 0.5]))
    });
    fd!("cumsum_affine scattered", &q, |v| {
        let x = [v[0] * v[1], v[2].exp(), v[3] * v[4]];
        let c = cumsum_affine(&x, 0.3, -0.2);
        dot(&c, &c) + c[0] * v[5]
    });
    fd!("cumsum then normal", &q, |v| {
        let c = cumsum(&v[2..]);
        normal_lpdf(Data(&[0.1, 0.2, 0.3, 0.4]), &c, Const(0.5))
    });
    fd!("cumsum output used twice", &q, |v| {
        let c = cumsum(v);
        sum(&c) + c[2] * c[5]
    });
}

#[test]
fn constraining_transforms() {
    let q = [0.3, -0.7, 1.2, 0.1];
    fd!("exp_constrain", &q, |v| {
        let (x, lj) = exp_constrain(v[0]);
        x * v[1] + lj
    });
    fd!("lower_bound", &q, |v| {
        let (x, lj) = lower_bound_constrain(v[0], 2.0);
        x.ln() + lj
    });
    fd!("logistic_constrain", &q, |v| {
        let (p, lj) = logistic_constrain(v[1]);
        p.ln() * 3.0 + lj
    });
    fd!("interval_constrain", &q, |v| {
        let (x, lj) = interval_constrain(v[1], -1.0, 4.0);
        x.square() + lj
    });
    fd!("ordered_constrain", &q, |v| {
        let (x, lj) = ordered_constrain(v);
        dot(&x, Data(&[1.0, -0.5, 2.0, 0.25])) + lj
    });
    // The ordered output really is ordered.
    let (x, _) = ordered_constrain(&q);
    assert!(x.windows(2).all(|w| w[0] < w[1]));
}

fn random_points(rng: &mut SmallRng, dim: usize, n: usize, lo: f64, hi: f64) -> Vec<Vec<f64>> {
    (0..n)
        .map(|_| (0..dim).map(|_| rng.random_range(lo..hi)).collect())
        .collect()
}

fn assert_gradients_close(name: &str, a: &[f64], b: &[f64], tol: f64) {
    for (i, (x, y)) in a.iter().zip(b).enumerate() {
        assert!(
            (x - y).abs() <= tol * (1.0 + x.abs()),
            "{name}: gradient[{i}] {x} vs {y}"
        );
    }
}

#[test]
fn eight_schools_matches_hand_gradient_bitwise() {
    let model = EightSchools::default();
    let target = AutodiffTarget::new(model.clone());
    let mut rng = SmallRng::seed_from_u64(1);
    for q in random_points(&mut rng, 10, 50, -2.0, 2.0) {
        let mut gh = vec![0.0; 10];
        let mut gc = vec![0.0; 10];
        let mut ga = vec![0.0; 10];
        let vh = model.hand_gradient(&q, &mut gh);
        let vc = eight_schools_hand_gradient_const(&q, &mut gc);
        let va = target.log_density_gradient(&q, &mut ga).unwrap();
        assert_eq!(vh.to_bits(), vc.to_bits());
        assert_eq!(va.to_bits(), vh.to_bits(), "value {va} vs hand {vh}");
        assert_eq!(target.value(&q).to_bits(), vh.to_bits());
        assert_gradients_close("eight schools", &gh, &ga, 1e-10);
        assert_gradients_close("eight schools const", &gc, &ga, 1e-10);
    }
    let stats = last_tape_stats();
    // exp, normal(mu), 5 half-Cauchy nodes, 2 adds, 6 per school.
    assert_eq!(stats.nodes, 1 + 1 + 5 + 2 + 8 * 6);
    assert_eq!(target.parameter_names().unwrap().len(), 10);
}

#[test]
fn eight_schools_vectorised_matches_hand_gradient() {
    let model = EightSchools::default();
    let target = AutodiffTarget::new(EightSchoolsVectorised::default());
    let constant: f64 = model
        .se
        .iter()
        .map(|se| 0.5 * 1.837_877_066_409_345_3 + se.ln())
        .sum();
    let mut rng = SmallRng::seed_from_u64(2);
    for q in random_points(&mut rng, 10, 50, -2.0, 2.0) {
        let mut gh = vec![0.0; 10];
        let mut ga = vec![0.0; 10];
        let vh = model.hand_gradient(&q, &mut gh);
        let va = target.log_density_gradient(&q, &mut ga).unwrap();
        assert!(
            (va - constant - vh).abs() <= 1e-12 * (1.0 + vh.abs()),
            "{va} - {constant} vs {vh}"
        );
        assert_gradients_close("eight schools vectorised", &gh, &ga, 1e-10);
    }
    let stats = last_tape_stats();
    // exp, normal(mu), cauchy(tau), two fused normals and four adds.
    assert_eq!(stats.nodes, 1 + 1 + 1 + 2 + 4);
    // Likelihood: 8 contiguous z partials plus slope and intercept; z prior: 8.
    assert_eq!(stats.partials, 8 + 2 + 8);
    assert_eq!(stats.indices, 2);
}

#[test]
fn funnel_matches_hand_gradient_bitwise() {
    let model = Funnel { dimension: 10 };
    let target = AutodiffTarget::new(model.clone());
    let mut rng = SmallRng::seed_from_u64(3);
    for q in random_points(&mut rng, 10, 50, -4.0, 4.0) {
        let mut gh = vec![0.0; 10];
        let mut ga = vec![0.0; 10];
        let vh = model.hand_gradient(&q, &mut gh);
        let va = target.log_density_gradient(&q, &mut ga).unwrap();
        assert_eq!(va.to_bits(), vh.to_bits(), "value {va} vs hand {vh}");
        assert_gradients_close("funnel", &gh, &ga, 1e-10);
    }
}

#[test]
fn funnel_overflow_is_recoverable() {
    let target = AutodiffTarget::new(Funnel { dimension: 10 });
    let mut q = vec![0.5; 10];
    q[0] = -800.0;
    let mut g = vec![0.0; 10];
    let err = target.log_density_gradient(&q, &mut g).unwrap_err();
    assert_eq!(err.kind(), TargetErrorKind::Recoverable);
    let strict = AutodiffTarget::new(Funnel { dimension: 10 })
        .with_nonfinite_policy(NonfinitePolicy::StrictFatal);
    let err = strict.log_density_gradient(&q, &mut g).unwrap_err();
    assert_eq!(err.kind(), TargetErrorKind::Recoverable);
    let mut short = vec![0.0; 9];
    let err = target
        .log_density_gradient(&q[..9], &mut short)
        .unwrap_err();
    assert_eq!(err.kind(), TargetErrorKind::Fatal);
}

#[test]
fn local_level_matches_hand_gradients() {
    for &t in &[1usize, 2, 7, 100, 1000] {
        let data = LocalLevelData::simulate(t, 11);
        let model = LocalLevel {
            data,
            normalised: true,
        };
        let target = AutodiffTarget::new(model.clone());
        let fast = AutodiffTarget::new(LocalLevel {
            data: model.data.clone(),
            normalised: false,
        });
        let mut rng = SmallRng::seed_from_u64(t as u64);
        for q in random_points(&mut rng, t, 5, -2.0, 2.0) {
            let mut gh = vec![0.0; t];
            let mut gw = vec![0.0; t];
            let mut ga = vec![0.0; t];
            let mut gf = vec![0.0; t];
            let vh = model.hand_gradient(&q, &mut gh);
            let vw = model.hand_gradient_wp4(&q, &mut gw);
            let va = target.log_density_gradient(&q, &mut ga).unwrap();
            let vf = fast.log_density_gradient(&q, &mut gf).unwrap();
            assert_eq!(va.to_bits(), vh.to_bits(), "T={t}: value {va} vs hand {vh}");
            assert!(
                (vf - vw).abs() <= 1e-12 * (1.0 + vw.abs()),
                "T={t}: {vf} vs WP4 {vw}"
            );
            assert_gradients_close("local level", &gh, &ga, 1e-10);
            assert_gradients_close("local level (WP4)", &gw, &ga, 1e-10);
            assert_gradients_close("local level unnormalised", &gw, &gf, 1e-10);
        }
        let stats = last_tape_stats();
        // Prior, transition, observation, and the two additions.
        assert_eq!(stats.nodes, 5, "T={t}");
        // A broadcast length of one records a ternary node, not a fused one;
        // every operand here is a contiguous run of inputs, so no indices.
        let expected = match t {
            1 => 0,
            2 => 2,
            _ => 3 * t - 2,
        };
        assert_eq!(stats.partials, expected, "T={t}");
        assert_eq!(stats.indices, 0, "T={t}");
    }
}

#[test]
fn local_level_noncentered_matches_hand_and_finite_differences() {
    for &t in &[1usize, 3, 100, 1000] {
        let data = LocalLevelData::simulate(t, 5);
        let model = LocalLevelNoncentered { data };
        let target = AutodiffTarget::new(model.clone());
        let mut rng = SmallRng::seed_from_u64(100 + t as u64);
        for q in random_points(&mut rng, t, 3, -2.0, 2.0) {
            let mut gh = vec![0.0; t];
            let mut ga = vec![0.0; t];
            let vh = model.hand_gradient(&q, &mut gh);
            let va = target.log_density_gradient(&q, &mut ga).unwrap();
            assert_eq!(va.to_bits(), vh.to_bits(), "T={t}: value {va} vs hand {vh}");
            assert_gradients_close("noncentered", &gh, &ga, 1e-10);
        }
        if t <= 100 {
            let q = random_points(&mut rng, t, 1, -1.0, 1.0).remove(0);
            let m = &model;
            check_fd(
                "noncentered fd",
                &q,
                |v| m.log_density(v),
                |v| m.log_density(v),
            );
        }
        let stats = last_tape_stats();
        // The tape is O(T): one cumsum block (T-1 indices), four fused nodes
        // and three additions; the cumsum output is contiguous, so the only
        // scattered entries are the two scalar parents of the `Linear` mean.
        assert!(stats.nodes <= t + 7, "T={t}: {} nodes", stats.nodes);
        assert!(stats.indices <= 2, "T={t}");
    }
}

#[test]
fn tape_is_reused_without_growth() {
    let target = AutodiffTarget::new(LocalLevel {
        data: LocalLevelData::simulate(50, 9),
        normalised: true,
    });
    let q = vec![0.1; 50];
    let mut g = vec![0.0; 50];
    target.log_density_gradient(&q, &mut g).unwrap();
    let first = last_tape_stats();
    for _ in 0..100 {
        target.log_density_gradient(&q, &mut g).unwrap();
        assert_eq!(last_tape_stats(), first);
    }
}

#[test]
fn parallel_threads_have_independent_tapes() {
    let model = EightSchools::default();
    let target = AutodiffTarget::new(model.clone());
    let handles: Vec<_> = (0..8)
        .map(|k| {
            let target = target.clone();
            let model = model.clone();
            std::thread::spawn(move || {
                let mut rng = SmallRng::seed_from_u64(k);
                for q in random_points(&mut rng, 10, 200, -2.0, 2.0) {
                    let mut gh = vec![0.0; 10];
                    let mut ga = vec![0.0; 10];
                    let vh = model.hand_gradient(&q, &mut gh);
                    let va = target.log_density_gradient(&q, &mut ga).unwrap();
                    assert_eq!(va.to_bits(), vh.to_bits());
                    assert_gradients_close("thread", &gh, &ga, 1e-10);
                }
            })
        })
        .collect();
    for h in handles {
        h.join().unwrap();
    }
}

#[test]
fn eight_schools_samples_with_owalnuts() {
    use owalnuts::walnutpie::{DiagonalMass, RunConfig, sample_chains};
    use std::num::NonZeroUsize;
    let target = AutodiffTarget::new(EightSchools::default());
    let starts = vec![vec![0.0; 10], vec![0.5; 10]];
    let config = RunConfig::new(100, NonZeroUsize::new(100).unwrap(), 7);
    let mass = DiagonalMass::identity(NonZeroUsize::new(10).unwrap());
    let out = sample_chains(
        &target,
        &starts,
        &mass,
        &config,
        NonZeroUsize::new(2).unwrap(),
    )
    .expect("sampling");
    assert_eq!(out.chains().len(), 2);
    assert!(out.chains().iter().all(|c| c.retained() == 100));
}
