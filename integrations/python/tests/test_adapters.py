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


def test_from_cfunc_numba_gaussian_parallel_chains():
    numba = pytest.importorskip("numba")
    sig = owalnuts.numba_raw_signature()

    @numba.cfunc(sig, nopython=True)
    def gaussian(dim, x_ptr, g_ptr, _ud):
        x = numba.carray(x_ptr, (3,))
        g = numba.carray(g_ptr, (3,))
        total = 0.0
        for i in range(3):
            g[i] = -x[i]
            total += x[i] * x[i]
        return -0.5 * total

    target = owalnuts.from_cfunc(gaussian, 3, parameter_names=["a", "b", "c"])
    r = owalnuts.sample(
        target, 3, chains=4, warmup=300, draws=800, seed=11, threads=4,
        tuning=owalnuts.Tuning(step_size=0.4, max_depth=6),
    )
    q = r.samples.reshape(-1, 3)
    assert np.isfinite(q).all()
    assert abs(q.mean()) < 0.1
    assert abs(q.var() - 1.0) < 0.15
    assert r.target_calls > 0


def test_from_cfunc_zero_density_wall_matches_truncated_moments():
    numba = pytest.importorskip("numba")
    sig = owalnuts.numba_raw_signature()

    @numba.cfunc(sig, nopython=True)
    def wall(dim, x_ptr, g_ptr, _ud):
        x = numba.carray(x_ptr, (2,))
        if x[0] < 0.0:
            return -np.inf
        g = numba.carray(g_ptr, (2,))
        g[0] = -x[0]
        g[1] = -x[1]
        return -0.5 * (x[0] * x[0] + x[1] * x[1])

    target = owalnuts.from_cfunc(wall, 2)
    r = owalnuts.sample(
        target, 2, init=np.array([1.0, 0.0]), chains=2, warmup=300, draws=1500, seed=7,
    )
    assert np.isfinite(r.samples).all()
    x0 = r.samples[..., 0].ravel()
    assert x0.min() >= 0.0
    assert abs(x0.mean() - math.sqrt(2.0 / math.pi)) < 0.08
    zero_density = sum(
        int(c["work_total"]["zero_density_evaluations"]) for c in r.chains
    )
    assert zero_density > 0


def test_from_pymc_gil_free_matches_gil_path():
    pytest.importorskip("numba")
    pm = pytest.importorskip("pymc")

    with pm.Model() as m:
        mu = pm.Normal("mu", 0.0, 5.0)
        tau = pm.HalfCauchy("tau", 5.0)
        z = pm.Normal("z", 0.0, 1.0, shape=8)
        pm.Normal("y", mu + tau * z, SE, observed=Y)

    gil_target, dim, q0, names, unravel = owalnuts.from_pymc(m)
    try:
        cf_target, dim2, q02, names2, _ = owalnuts.from_pymc(m, gil_free=True)
    except NotImplementedError as e:
        pytest.skip(f"gil-free PyMC transport unavailable: {e}")
    assert dim2 == dim and names2 == names
    np.testing.assert_allclose(q02, q0)
    r_gil = owalnuts.sample(gil_target, dim, init=q0, chains=2, warmup=200, draws=300, seed=5)
    r_cf = owalnuts.sample(cf_target, dim, init=q0, chains=2, warmup=200, draws=300, seed=5)
    # Same kernel, same seed: identical draws when the gradients agree bitwise;
    # allow tiny divergence otherwise but require matching posteriors.
    assert np.isfinite(r_cf.samples).all()
    assert abs(r_cf.samples.mean() - r_gil.samples.mean()) < 0.25


def test_refresh_callback_installs_and_reports():
    import owalnuts

    dim = 3
    calls = []

    def logp(q):
        return -0.5 * float(q @ q), -q

    def refresh(window, transition, count, mean, variance):
        calls.append((window, transition, count, mean.shape, variance.shape))
        if transition < 150:
            return None
        return [{"type": "diagonal", "diagonal": np.clip(1.0 / variance, 0.1, 10.0)}]

    mass = [{"type": "diagonal", "diagonal": np.ones(dim)}]
    out = owalnuts.sample(
        logp, dim, chains=2, warmup=200, draws=200, seed=11, threads=1,
        mass=mass, refresh=refresh,
        adaptation=owalnuts.Adaptation(adapt_mass=True),
    )
    assert out.samples.shape == (2, 200, dim)
    assert np.isfinite(out.samples).all()
    updates = out.refresh_updates
    assert updates, "no refresh telemetry"
    outcomes = {u["outcome"] for u in updates}
    assert "Installed" in outcomes
    assert calls and all(c[3] == (dim,) for c in calls)


def test_refresh_exception_keeps_previous_metric():
    import owalnuts

    dim = 2

    def logp(q):
        return -0.5 * float(q @ q), -q

    def refresh(window, transition, count, mean, variance):
        raise RuntimeError("candidate failed")

    mass = [{"type": "diagonal", "diagonal": np.ones(dim)}]
    out = owalnuts.sample(
        logp, dim, chains=1, warmup=150, draws=100, seed=12, threads=1,
        mass=mass, refresh=refresh,
        adaptation=owalnuts.Adaptation(adapt_mass=True),
    )
    assert np.isfinite(out.samples).all()
    updates = out.refresh_updates
    assert updates and all(u["outcome"] == "RefreshFailed" for u in updates)


def test_from_pymc_thread_safe_matches_single_thread():
    pymc = pytest.importorskip("pymc")
    import owalnuts

    with pymc.Model() as model:
        x = pymc.Normal("x", 0.0, 1.0)
        pymc.Normal("y", x, 1.0, observed=np.array([0.3, -0.2, 0.5]))

    t1, dim, q0, _, _ = owalnuts.from_pymc(model)
    t4, dim4, _, _, _ = owalnuts.from_pymc(model, thread_safe=True)
    assert dim == dim4
    lp1, g1 = t1(q0)
    lp4, g4 = t4(q0)
    assert lp1 == lp4 and np.allclose(g1, g4)

    out1 = owalnuts.sample(t1, dim, chains=2, warmup=150, draws=150, seed=21, threads=1)
    out4 = owalnuts.sample(t4, dim, chains=4, warmup=150, draws=300, seed=22, threads=4)
    assert np.isfinite(out4.samples).all()
    m1 = out1.samples[:, :, 0].mean()
    m4 = out4.samples[:, :, 0].mean()
    assert abs(m1 - m4) < 0.2, (m1, m4)
