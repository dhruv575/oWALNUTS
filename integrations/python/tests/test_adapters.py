import math

import numpy as np
import pytest

import owalnuts

Y = np.array([28.0, 8.0, -3.0, 7.0, -1.0, 1.0, 18.0, 12.0])
SE = np.array([15.0, 10.0, 16.0, 11.0, 9.0, 11.0, 10.0, 18.0])
LOG_2PI = math.log(2 * math.pi)


def eight_schools_numpy(q: np.ndarray) -> float:
    mu, log_tau, z = q[0], q[1], q[2:]
    tau = np.exp(log_tau)
    theta = mu + tau * z
    lp = -0.5 * LOG_2PI - math.log(5.0) - 0.5 * (mu / 5.0) ** 2
    lp += math.log(2.0 / (math.pi * 5.0 * (1.0 + (tau / 5.0) ** 2))) + log_tau
    lp += np.sum(-0.5 * LOG_2PI - np.log(SE) - 0.5 * ((Y - theta) / SE) ** 2)
    lp += np.sum(-0.5 * LOG_2PI - 0.5 * z**2)
    return float(lp)


def finite_difference(f, q, h=1e-6):
    g = np.zeros_like(q)
    for i in range(q.size):
        e = np.zeros_like(q)
        e[i] = h
        g[i] = (f(q + e) - f(q - e)) / (2 * h)
    return g


def _check_target(target, q, rel=1e-5):
    value, grad = target(q)
    assert isinstance(value, float)
    assert grad.dtype == np.float64 and grad.shape == q.shape
    ref_value, ref_grad = owalnuts.eight_schools_logp_grad(Y, SE, q)
    assert value == pytest.approx(ref_value, rel=1e-10, abs=1e-10)
    np.testing.assert_allclose(grad, ref_grad, rtol=rel, atol=1e-7)


Q0 = np.array([0.3, -0.2, 0.5, -0.4, 0.1, 0.0, 0.7, -0.6, 0.2, -0.1])


def test_native_eight_schools_matches_finite_differences():
    value, grad = owalnuts.eight_schools_logp_grad(Y, SE, Q0)
    assert value == pytest.approx(eight_schools_numpy(Q0), rel=1e-12)
    np.testing.assert_allclose(grad, finite_difference(eight_schools_numpy, Q0), rtol=1e-6, atol=1e-7)


def test_from_numpy_adapter():
    target = owalnuts.from_numpy(eight_schools_numpy, lambda q: finite_difference(eight_schools_numpy, q))
    _check_target(target, Q0, rel=1e-5)


def test_from_jax_adapter():
    jax = pytest.importorskip("jax")
    jnp = jax.numpy

    def logp(q):
        mu, log_tau, z = q[0], q[1], q[2:]
        tau = jnp.exp(log_tau)
        theta = mu + tau * z
        lp = -0.5 * LOG_2PI - jnp.log(5.0) - 0.5 * (mu / 5.0) ** 2
        lp += jnp.log(2.0 / (jnp.pi * 5.0 * (1.0 + (tau / 5.0) ** 2))) + log_tau
        lp += jnp.sum(-0.5 * LOG_2PI - jnp.log(SE) - 0.5 * ((Y - theta) / SE) ** 2)
        lp += jnp.sum(-0.5 * LOG_2PI - 0.5 * z**2)
        return lp

    _check_target(owalnuts.from_jax(logp), Q0, rel=1e-9)


def test_from_torch_adapter():
    torch = pytest.importorskip("torch")
    y = torch.tensor(Y)
    se = torch.tensor(SE)

    def logp(q):
        mu, log_tau, z = q[0], q[1], q[2:]
        tau = torch.exp(log_tau)
        theta = mu + tau * z
        lp = -0.5 * LOG_2PI - math.log(5.0) - 0.5 * (mu / 5.0) ** 2
        lp = lp + torch.log(2.0 / (math.pi * 5.0 * (1.0 + (tau / 5.0) ** 2))) + log_tau
        lp = lp + torch.sum(-0.5 * LOG_2PI - torch.log(se) - 0.5 * ((y - theta) / se) ** 2)
        lp = lp + torch.sum(-0.5 * LOG_2PI - 0.5 * z**2)
        return lp

    _check_target(owalnuts.from_torch(logp), Q0, rel=1e-9)


def test_from_pymc_adapter_matches_v38_density_up_to_constant():
    pm = pytest.importorskip("pymc")
    with pm.Model() as model:
        mu = pm.Normal("mu", 0.0, 5.0)
        tau = pm.HalfCauchy("tau", 5.0)
        z = pm.Normal("z", 0.0, 1.0, shape=8)
        pm.Normal("y", mu + tau * z, SE, observed=Y)
    target, dim, q0, names, unravel = owalnuts.from_pymc(model)
    assert dim == 10 and names == ["mu", "tau_log__", "z"]
    v1, g1 = target(Q0)
    v2, g2 = target(Q0 + 0.1)
    r1, _ = owalnuts.eight_schools_logp_grad(Y, SE, Q0)
    r2, rg2 = owalnuts.eight_schools_logp_grad(Y, SE, Q0 + 0.1)
    assert (v1 - v2) == pytest.approx(r1 - r2, rel=1e-8)
    np.testing.assert_allclose(g2, rg2, rtol=1e-7, atol=1e-8)
    parts = unravel(np.arange(10.0))
    assert parts["z"].shape == (8,) and parts["tau_log__"].shape == (1,)


def test_gaussian_moments_and_inferencedata():
    dim = 3
    result = owalnuts.sample(lambda q: (-0.5 * float(q @ q), -q), dim, warmup=300, draws=600, seed=93_000, chains=4)
    assert result.samples.shape == (4, 600, dim)
    assert abs(result.samples.mean()) < 0.1
    assert abs(result.samples.var() - 1.0) < 0.15
    assert result.target_calls == sum(c["work_total"]["target_calls_total"] for c in result.chains)
    az = pytest.importorskip("arviz")
    idata = result.to_inferencedata(var_names=["a", "b", "c"])
    assert set(idata.posterior.data_vars) == {"a", "b", "c"}
    assert idata.sample_stats["tree_depth"].shape == (4, 600)
    assert float(az.ess(idata).to_array().min()) > 200


def test_zero_density_via_neg_inf_and_exception_refines_not_stops():
    # Half-space truncated Gaussian: x0 > 0, via -inf and via ZeroDensityError.
    def neg_inf(q):
        if q[0] <= 0:
            return -np.inf, np.zeros_like(q)
        return -0.5 * float(q @ q), -q

    def raises(q):
        if q[0] <= 0:
            raise owalnuts.ZeroDensityError("x0 must be positive")
        return -0.5 * float(q @ q), -q

    for target in (neg_inf, raises):
        r = owalnuts.sample(target, 2, init=np.array([1.0, 0.0]), init_jitter=0.5, warmup=300, draws=1500,
                            seed=93_001, chains=4)
        x0 = r.samples[:, :, 0]
        assert (x0 > 0).all()
        assert abs(x0.mean() - math.sqrt(2 / math.pi)) < 0.08
        assert r.target_recoverable_failures > 0
        stops = np.concatenate([c["stop"] for c in r.chains])
        assert (stops == owalnuts.STOP_CODES.index("invalid_evaluation")).sum() == 0


def test_fatal_exception_fails_closed():
    def bad(q):
        raise RuntimeError("model broke")

    with pytest.raises(RuntimeError, match="model broke"):
        owalnuts.sample(bad, 2, warmup=10, draws=10, seed=1)
    with pytest.raises(RuntimeError):
        owalnuts.sample(lambda q: (np.nan, np.zeros_like(q)), 2, warmup=10, draws=10, seed=1, nonfinite="fatal")


def test_structured_mass_matches_diagonal_for_zero_offdiagonal():
    diag = np.array([4.0, 2.0, 1.0])
    target = lambda q: (-0.5 * float(q @ (diag * q)), -diag * q)
    mass = owalnuts.tridiagonal_precision_mass(diag, np.zeros(2))
    r = owalnuts.sample(target, 3, mass=mass, warmup=200, draws=800, seed=93_002,
                        adaptation=owalnuts.Adaptation(adapt_mass=False))
    np.testing.assert_allclose(r.samples.var((0, 1)), 1 / diag, rtol=0.2)
    retained_depth = r.depth[:, 200:]
    assert np.percentile(retained_depth, 95) <= 5


def test_preflight_reports_zero_callbacks():
    report = owalnuts.preflight(5, warmup=100, draws=100)
    assert report["total_transitions"] == 800
    assert report["worst_case_target_evaluations"] <= report["admission_ceiling"]
