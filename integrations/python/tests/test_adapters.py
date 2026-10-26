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
    ess = az.ess(idata)
    ess_array = ess.dataset.to_array() if hasattr(ess, "dataset") else ess.to_array()
    assert float(ess_array.min()) > 200


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
    # Structured metrics are admitted against the RunConfig ceiling (no
    # budgeted facade variant): at the sampler defaults the exact worst case
    # of 2 x 1,000 transitions (0.78e9) is above the conservative 113M
    # ceiling, which `Limits::admit_worst_case` raises under the `research`
    # feature, and below the hard 1e9 research maximum, which nothing can
    # raise (4 x 1,000 transitions, 1.56e9, cannot be admitted at depth 10).
    report = owalnuts.preflight(3, chains=2, warmup=200, draws=800, mass=mass,
                                adaptation=owalnuts.Adaptation(adapt_mass=False))
    assert 113_000_000 < report["worst_case_target_evaluations"] <= 10**9
    r = owalnuts.sample(target, 3, mass=mass, chains=2, warmup=200, draws=800, seed=93_002,
                        adaptation=owalnuts.Adaptation(adapt_mass=False))
    np.testing.assert_allclose(r.samples.var((0, 1)), 1 / diag, rtol=0.2)
    retained_depth = r.depth[:, 200:]
    assert np.percentile(retained_depth, 95) <= 5


def test_preflight_reports_zero_callbacks():
    report = owalnuts.preflight(5, warmup=100, draws=100)
    assert report["total_transitions"] == 800
    assert report["worst_case_target_evaluations"] <= report["admission_ceiling"]


def test_defaults_admit_worst_case_above_conservative_ceiling():
    # Four chains x 3,000 transitions at the sampler defaults (depth 10, eight
    # refinement levels) exceed the conservative 113M preflight ceiling; the
    # default admit_worst_case=True admits the run with its exact worst case,
    # as Rust's Limits::admit_worst_case does, and an explicit budget works
    # on the diagonal path.
    report = owalnuts.preflight(10, chains=4, warmup=1000, draws=2000)
    assert report["worst_case_target_evaluations"] > 113_000_000
    assert report["admission_ceiling"] >= report["worst_case_target_evaluations"]
    with pytest.raises(RuntimeError, match="resource limit"):
        owalnuts.preflight(10, chains=4, warmup=1000, draws=2000, admit_worst_case=False)
    # An explicit budget is also the admission ceiling (Limits::max_target_evaluations).
    budgeted = owalnuts.preflight(10, chains=4, warmup=1000, draws=2000, max_target_evaluations=5 * 10**9)
    assert budgeted["worst_case_target_evaluations"] == report["worst_case_target_evaluations"]
    assert budgeted["admission_ceiling"] == 5 * 10**9
    with pytest.raises(RuntimeError, match="resource limit"):
        owalnuts.preflight(10, chains=4, warmup=1000, draws=2000, max_target_evaluations=10**9)
    small = owalnuts.preflight(3, chains=4, warmup=100, draws=100, tuning=owalnuts.Tuning(step_size=0.1, max_depth=8),
                               admit_worst_case=False)
    assert small["admission_ceiling"] == 113_000_000
    assert small["worst_case_target_evaluations"] <= 113_000_000


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


def test_worker_threads_keep_python_thread_state_across_callbacks():
    """threading.local survives between callbacks on a sampler worker thread
    (STUDIES/python_callpath_v1): one initialisation per OS thread, not per
    call, and the draws are those of threads=1."""
    import threading

    local = threading.local()
    inits = []
    lock = threading.Lock()

    def target(q):
        if not hasattr(local, "seen"):
            local.seen = True
            with lock:
                inits.append(threading.get_ident())
        return -0.5 * float(q @ q), -q

    out4 = owalnuts.sample(target, 3, chains=4, warmup=100, draws=100, seed=31, threads=4)
    out1 = owalnuts.sample(target, 3, chains=4, warmup=100, draws=100, seed=31, threads=1)
    assert out4.target_calls > 1000
    assert len(inits) <= 5, len(inits)  # <= 4 workers + the calling thread
    assert np.array_equal(out1.samples, out4.samples)
    # Repeated runs stay healthy after the pinned states are released.
    again = owalnuts.sample(target, 3, chains=4, warmup=50, draws=50, seed=32, threads=4)
    assert np.isfinite(again.samples).all()


def test_interpreter_exits_cleanly_after_threaded_callable_run():
    """The pinned worker thread states are released before `sample` returns,
    so the interpreter can finalise right after a threads > 1 run."""
    import subprocess
    import sys

    code = (
        "import owalnuts; "
        "f = lambda q: (-0.5 * float(q @ q), -q); "
        "owalnuts.sample(f, 3, chains=4, warmup=20, draws=20, seed=1, threads=4)"
    )
    done = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=300)
    assert done.returncode == 0, (done.returncode, done.stderr[-2000:])


def test_from_pymc_thread_safe_compiles_once_per_worker_thread():
    pymc = pytest.importorskip("pymc")

    with pymc.Model() as model:
        x = pymc.Normal("x", 0.0, 1.0, shape=2)
        pymc.Normal("y", x.sum(), 1.0, observed=np.array([0.3, -0.2, 0.5]))
    compiles = []
    original = type(model).logp_dlogp_function

    def counted(self, *args, **kwargs):
        compiles.append(1)
        return original(self, *args, **kwargs)

    type(model).logp_dlogp_function = counted
    try:
        target, dim, _, _, _ = owalnuts.from_pymc(model, thread_safe=True)
        serial, _, _, _, _ = owalnuts.from_pymc(model)
        out4 = owalnuts.sample(target, dim, chains=4, warmup=100, draws=100, seed=33, threads=4)
    finally:
        type(model).logp_dlogp_function = original
    out1 = owalnuts.sample(serial, dim, chains=4, warmup=100, draws=100, seed=33, threads=1)
    assert len(compiles) <= 1 + 5, len(compiles)  # the serial wrapper + one per thread
    assert np.array_equal(out1.samples, out4.samples)


def test_uniform_init_retries_until_evaluable_and_is_deterministic():
    # Log density is only finite for x0 > 0.5, so about three quarters of
    # uniform(-2, 2) draws must be rejected and redrawn.
    def target(q):
        if q[0] <= 0.5:
            return -np.inf, np.zeros_like(q)
        return -0.5 * float(q @ q), -q

    starts = owalnuts.uniform_starts(target, 3, chains=4, seed=17)
    assert starts.shape == (4, 3)
    assert (starts[:, 0] > 0.5).all() and (np.abs(starts) <= 2.0).all()
    np.testing.assert_array_equal(starts, owalnuts.uniform_starts(target, 3, chains=4, seed=17))
    r1 = owalnuts.sample(target, 3, init="uniform", chains=2, warmup=100, draws=100, seed=17)
    r2 = owalnuts.sample(target, 3, init="uniform", chains=2, warmup=100, draws=100, seed=17)
    np.testing.assert_array_equal(r1.samples, r2.samples)
    assert (r1.samples[..., 0] > 0.5).all()
    with pytest.raises(ValueError, match="uniform"):
        owalnuts.sample(target, 3, init="random", warmup=10, draws=10)


def test_uniform_init_fails_closed_when_no_start_is_evaluable():
    def never(q):
        return -np.inf, np.zeros_like(q)

    with pytest.raises(RuntimeError, match="no evaluable start"):
        owalnuts.uniform_starts(never, 2, chains=1, seed=1, max_attempts=5)


def test_default_tuning_matches_rust_sampler_defaults():
    d = owalnuts.DEFAULTS
    t = owalnuts.Tuning()
    assert (t.step_size, t.max_depth, t.min_micro_steps, t.max_refinement_levels, t.max_error,
            t.divergence_threshold) == (d["step_size"], d["max_depth"], d["min_micro_steps"],
                                        d["max_refinement_levels"], d["max_error"], d["divergence_threshold"])
    assert (t.u_turn_rule, t.exhaustion_rule) == (None, None)
    a = owalnuts.Adaptation()
    assert (a.target_accept, a.adapt_mass, a.metric_regularization) == (d["target_accept"], d["adapt_mass"], None)
    # The post-WP31 sampler defaults, as documented in CHANGELOG 0.2.0.
    assert d["u_turn_rule"] == "momentum_sum"
    assert d["metric_regularization"] == "stan"
    assert d["warmup_exhaustion_rule"] == "accept_unless_divergent"
    assert d["chain_rescue"] is None
    assert d["cache_initial_evaluation"] is True and d["admit_worst_case"] is True
    assert d["algorithm_revision"] == owalnuts.ALGORITHM_REVISION
    assert (d["init_radius"], d["init_max_attempts"]) == (2.0, 100)
    with pytest.raises(TypeError):
        owalnuts.DEFAULTS["max_depth"] = 3  # read-only
    r = owalnuts.sample(lambda q: (-0.5 * float(q @ q), -q), 2, warmup=50, draws=20, seed=3, chains=1)
    assert r.chains[0]["metadata"]["max_depth"] == d["max_depth"]
    assert r.chains[0]["metadata"]["max_refinement_levels"] == d["max_refinement_levels"]


def _sequential_gaussian(q: np.ndarray) -> tuple[float, np.ndarray]:
    # Same operation order as the Rust `StandardGaussian` reference target
    # (index-order `s += x * x`, then `-0.5 * s`), so values agree bitwise.
    s = 0.0
    for x in q:
        s += x * x
    return -0.5 * s, -q


def test_sample_with_explicit_defaults_is_bit_identical_to_rust_sampler():
    d = owalnuts.DEFAULTS
    dim, chains, warmup, draws, seed = 3, 4, 200, 300, 0x5EED
    starts = np.random.default_rng(1).uniform(-2.0, 2.0, size=(chains, dim))
    reference = np.asarray(owalnuts._owalnuts.reference_gaussian_sampler_run(starts, warmup, draws, seed))
    assert reference.shape == (chains, draws, dim)
    explicit = owalnuts.sample(
        _sequential_gaussian, dim, init=starts, chains=chains, warmup=warmup, draws=draws, seed=seed,
        threads=1,
        tuning=owalnuts.Tuning(
            step_size=d["step_size"], max_depth=d["max_depth"], min_micro_steps=d["min_micro_steps"],
            max_refinement_levels=d["max_refinement_levels"], max_error=d["max_error"],
            divergence_threshold=d["divergence_threshold"], u_turn_rule=d["u_turn_rule"],
            exhaustion_rule=d["exhaustion_rule"],
        ),
        adaptation=owalnuts.Adaptation(
            target_accept=d["target_accept"], adapt_step_size=True, adapt_mass=d["adapt_mass"],
            metric_regularization=d["metric_regularization"],
        ),
        mass=None, admit_worst_case=d["admit_worst_case"],
        cache_initial_evaluation=d["cache_initial_evaluation"],
    )
    np.testing.assert_array_equal(explicit.samples, reference)
    implicit = owalnuts.sample(_sequential_gaussian, dim, init=starts, chains=chains, warmup=warmup, draws=draws,
                               seed=seed)
    np.testing.assert_array_equal(implicit.samples, reference)
    # The frozen v10 kernel rules are a different sampler.
    frozen = owalnuts.sample(
        _sequential_gaussian, dim, init=starts, chains=chains, warmup=warmup, draws=draws, seed=seed,
        tuning=owalnuts.Tuning(u_turn_rule="endpoints"),
        adaptation=owalnuts.Adaptation(metric_regularization="toward_unit"),
    )
    assert not np.array_equal(frozen.samples, reference)
    with pytest.raises(ValueError, match="u_turn_rule"):
        owalnuts.sample(_sequential_gaussian, dim, warmup=10, draws=10, tuning=owalnuts.Tuning(u_turn_rule="stan"))


def test_summary_rows_match_arviz():
    dim = 3
    result = owalnuts.sample(lambda q: (-0.5 * float(q @ q), -q), dim, warmup=300, draws=600, seed=93_010, chains=4)
    rows = result.summary(["a", "b", "c"])
    assert [r["name"] for r in rows] == ["a", "b", "c"]
    assert set(rows[0]) == {"name", "mean", "sd", "mcse_mean", "q5", "q50", "q95", "ess_bulk", "ess_tail", "rhat"}
    assert all(isinstance(v, float) for r in rows for k, v in r.items() if k != "name")
    assert owalnuts.summary(result.samples)[1]["name"] == "theta.2"
    health = result.health()
    assert health["transitions"] == 4 * 600 and health["divergences"] == 0
    assert health["target_calls"] == result.retained_target_calls
    az = pytest.importorskip("arviz")
    idata = result.to_inferencedata(var_names=["a", "b", "c"])
    for row in rows:
        name = row["name"]
        assert row["mean"] == pytest.approx(float(idata.posterior[name].mean()), rel=1e-9, abs=1e-12)
        assert row["rhat"] == pytest.approx(float(az.rhat(idata)[name]), rel=1e-6)
        assert row["ess_bulk"] == pytest.approx(float(az.ess(idata, method="bulk")[name]), rel=1e-6)
        tail = az.ess(idata, method="tail")
        if hasattr(tail, "dataset"):
            # ArviZ 1.x changed its tail quantile implementation; the frozen
            # 0.23 fixture retains the strict cross-language oracle.
            assert row["ess_tail"] > 0 and float(tail[name]) > 0
        else:
            assert row["ess_tail"] == pytest.approx(float(tail[name]), rel=1e-6)
        assert row["mcse_mean"] == pytest.approx(float(az.mcse(idata, method="mean")[name]), rel=1e-6)
        assert row["sd"] == pytest.approx(float(idata.posterior[name].std(ddof=1)), rel=1e-9)


def test_version_and_printed_summary():
    assert owalnuts.__version__
    result = owalnuts.sample(lambda q: (-0.5 * float(q @ q), -q), dim=2, warmup=200, draws=200, seed=3)
    text = str(result)
    assert text.splitlines()[0].startswith("name")
    assert "theta.1" in text and "theta.2" in text and text.splitlines()[-1].startswith("health:")
    assert repr(result).startswith("SampleResult(chains=4, draws=200, dim=2")
    assert owalnuts.format_summary(result.summary()) == text.rsplit("\n", 1)[0]


def test_from_pymc_gil_free_recovers_nonfinite_density_and_gradient():
    """Boundary derivatives and overflow must refine, not abort raw sampling."""
    import ctypes
    pytest.importorskip("numba")
    pm = pytest.importorskip("pymc")
    pt = pytest.importorskip("pytensor.tensor")
    with pm.Model() as model:
        x = pm.Flat("x", initval=np.float64(1.0))
        pm.Potential("positive_density", -pt.sqrt(x)-pt.exp(x))
    target, dim, _, _, _ = owalnuts.from_pymc(model, gil_free=True)
    prototype = ctypes.CFUNCTYPE(ctypes.c_double, ctypes.c_ssize_t,
        ctypes.POINTER(ctypes.c_double), ctypes.POINTER(ctypes.c_double), ctypes.c_void_p)
    caller = prototype(target.address)
    def evaluate(value):
        q = np.array([value], dtype=np.float64)
        grad = np.full(1, 123.0)
        logp = caller(dim, q.ctypes.data_as(ctypes.POINTER(ctypes.c_double)),
                      grad.ctypes.data_as(ctypes.POINTER(ctypes.c_double)), None)
        return logp, grad
    logp, grad = evaluate(1.0)
    np.testing.assert_allclose(logp, -1.0-math.e, rtol=1e-12)
    np.testing.assert_allclose(grad, [-0.5-math.e], rtol=1e-12)
    # x=0 has finite logp=-1 but an infinite derivative. x<0 is outside
    # the density's domain; x=1000 overflows its exponential.
    for invalid in (0.0, -1.0, 1000.0):
        logp, grad = evaluate(invalid)
        assert logp == -np.inf
        np.testing.assert_array_equal(grad, np.zeros(1))
    result = owalnuts.sample(target, dim, init=np.full((2, 1), 0.1), chains=2,
        warmup=80, draws=100, seed=19, threads=1,
        tuning=owalnuts.Tuning(step_size=0.5, max_depth=6))
    assert np.isfinite(result.samples).all()
    assert (result.samples > 0).all()
    assert sum(int(c["work_total"]["zero_density_evaluations"]) for c in result.chains) > 0


def test_from_pymc_gil_free_still_rejects_invalid_initial_point():
    pytest.importorskip("numba")
    pm = pytest.importorskip("pymc")
    pt = pytest.importorskip("pytensor.tensor")
    with pm.Model() as model:
        x = pm.Flat("x", initval=np.float64(0.0))
        pm.Potential("boundary", -pt.sqrt(x)-pt.exp(x))
    with pytest.raises(NotImplementedError, match="disagreed"):
        owalnuts.from_pymc(model, gil_free=True)


def _evaluate_raw_pymc_target(target, q):
    """Evaluate the public raw target without adding stochastic sampling noise."""
    import ctypes
    q = np.ascontiguousarray(q, dtype=np.float64)
    gradient = np.full(q.size, np.nan)
    prototype = ctypes.CFUNCTYPE(
        ctypes.c_double, ctypes.c_ssize_t, ctypes.POINTER(ctypes.c_double),
        ctypes.POINTER(ctypes.c_double), ctypes.c_void_p,
    )
    value = prototype(target.address)(
        q.size, q.ctypes.data_as(ctypes.POINTER(ctypes.c_double)),
        gradient.ctypes.data_as(ctypes.POINTER(ctypes.c_double)), None,
    )
    return value, gradient


@pytest.mark.xfail(
    raises=NotImplementedError,
    strict=False,
    reason="PyMC >= 5.28 refuses to snapshot models with explicit initvals under gil_free=True; "
    "documented limitation (wiki/release-0.3.0.md), the adapter fails closed",
)
def test_from_pymc_gil_free_snapshots_data_and_dimensions_without_mutation():
    pytest.importorskip("numba")
    pm = pytest.importorskip("pymc")
    pytest.importorskip("pymc.model.transform.optimization")
    x_a = np.array([-1., .5, 2.])
    y_a = np.array([.1, -.3, 1.2])
    with pm.Model(coords={"obs": np.arange(3)}) as model:
        x = pm.Data("x", x_a, dims="obs")
        y = pm.Data("observations", y_a, dims="obs")
        # Explicit transformed initial values and insertion order must survive
        # graph cloning, not just an all-zero scalar-model initial position.
        sigma = pm.HalfNormal("sigma", 1., initval=.7)
        beta = pm.Normal("beta", 0., 1., initval=.2)
        pm.Normal("likelihood", beta*x, sigma, observed=y, dims="obs")
    original_vars = dict(model.named_vars)
    original_initial = {name: value.copy() for name, value in model.initial_point().items()}
    expected_a, dim, q0, names, _ = owalnuts.from_pymc(model)
    probes = [q0.copy(), q0+np.array([.13, -.21])]
    reference_a = [expected_a(probe) for probe in probes]
    target_a, dim_a, q_a, names_a, _ = owalnuts.from_pymc(model, gil_free=True)
    assert dim_a == dim and names_a == names
    np.testing.assert_array_equal(q_a, q0)
    assert all(model.named_vars[name] is variable for name, variable in original_vars.items())
    np.testing.assert_array_equal(x.get_value(), x_a)
    np.testing.assert_array_equal(y.get_value(), y_a)
    assert model.dim_lengths["obs"].eval() == 3
    for name, value in model.initial_point().items():
        np.testing.assert_array_equal(value, original_initial[name])
    for probe, (value, grad) in zip(probes, reference_a):
        got, got_grad = _evaluate_raw_pymc_target(target_a, probe)
        np.testing.assert_allclose(got, value, rtol=1e-10, atol=1e-10)
        np.testing.assert_allclose(got_grad, grad, rtol=1e-10, atol=1e-10)

    # Also mutate the existing backing buffers, not only set_data's replacement
    # arrays. A snapshot that aliases shared storage would otherwise pass below.
    x.get_value(borrow=True)[...] = [5., 6., 7.]
    y.get_value(borrow=True)[...] = [-4., -5., -6.]
    for probe, (value, grad) in zip(probes, reference_a):
        got, got_grad = _evaluate_raw_pymc_target(target_a, probe)
        np.testing.assert_allclose(got, value, rtol=1e-10, atol=1e-10)
        np.testing.assert_allclose(got_grad, grad, rtol=1e-10, atol=1e-10)

    # Updating data AND its dimension must affect only newly compiled targets.
    x_b = np.array([2., 3., 4., 5.])
    y_b = np.array([-1., 2., .5, -2.])
    with model:
        pm.set_data({"x": x_b, "observations": y_b}, coords={"obs": np.arange(4)})
    expected_b, _, q_b, names_b, _ = owalnuts.from_pymc(model)
    target_b, dim_b, raw_q_b, raw_names_b, _ = owalnuts.from_pymc(model, gil_free=True)
    assert dim_b == dim and raw_names_b == names_b == names
    np.testing.assert_array_equal(raw_q_b, q_b)
    assert all(model.named_vars[name] is variable for name, variable in original_vars.items())
    np.testing.assert_array_equal(x.get_value(), x_b)
    np.testing.assert_array_equal(y.get_value(), y_b)
    assert model.dim_lengths["obs"].eval() == 4
    for name, value in model.initial_point().items():
        np.testing.assert_array_equal(value, original_initial[name])
    for probe, (old_value, old_grad) in zip(probes, reference_a):
        still_a, still_a_grad = _evaluate_raw_pymc_target(target_a, probe)
        np.testing.assert_allclose(still_a, old_value, rtol=1e-10, atol=1e-10)
        np.testing.assert_allclose(still_a_grad, old_grad, rtol=1e-10, atol=1e-10)
        new_value, new_grad = expected_b(probe)
        got_b, got_b_grad = _evaluate_raw_pymc_target(target_b, probe)
        np.testing.assert_allclose(got_b, new_value, rtol=1e-10, atol=1e-10)
        np.testing.assert_allclose(got_b_grad, new_grad, rtol=1e-10, atol=1e-10)
        assert not np.isclose(got_b, still_a)


def test_from_pymc_gil_free_rejects_unregistered_shared_inputs():
    pytest.importorskip("numba")
    pm = pytest.importorskip("pymc")
    pytensor = pytest.importorskip("pytensor")
    external = pytensor.shared(np.array([1., 2.]), name="external_data")
    with pm.Model() as model:
        mu = pm.Normal("mu", 0., 1.)
        pm.Potential("external_likelihood", -.5*((external-mu)**2).sum())
    with pytest.raises(NotImplementedError, match="snapshot.*shared|snapshot PyMC"):
        owalnuts.from_pymc(model, gil_free=True)
    np.testing.assert_array_equal(external.get_value(), [1., 2.])


def test_from_pymc_gil_free_ordinary_model_still_supported(monkeypatch):
    pytest.importorskip("numba")
    pm = pytest.importorskip("pymc")
    with pm.Model() as model:
        pm.Normal("x", 0., 1., initval=.3)
    # No snapshot transform is needed when there are no shared inputs or dims.
    import pymc.model.transform
    def unexpected_freeze(*args, **kwargs):
        raise AssertionError("ordinary model should not require graph cloning")
    # Patch every layout the adapter may import from (PyMC 5.28+ has it only
    # in pymc.model.transform.optimization).
    monkeypatch.setattr(pymc.model.transform, "freeze_dims_and_data", unexpected_freeze, raising=False)
    try:
        import pymc.model.transform.optimization as optimization
    except ImportError:
        pass
    else:
        monkeypatch.setattr(optimization, "freeze_dims_and_data", unexpected_freeze, raising=False)
    target, dim, q0, names, _ = owalnuts.from_pymc(model, gil_free=True)
    assert dim == 1 and names == ["x"]
    np.testing.assert_array_equal(q0, [.3])
    value, gradient = _evaluate_raw_pymc_target(target, np.array([.8]))
    np.testing.assert_allclose(value, -.5*LOG_2PI-.5*.8**2, rtol=1e-12)
    np.testing.assert_allclose(gradient, [-.8], rtol=1e-12)


def _trap(q: np.ndarray) -> tuple[float, np.ndarray]:
    # Standard Gaussian plus a negligible narrow spike at (15, 15) that a chain
    # started inside never leaves (the Rust tests/chain_warnings.rs trap).
    main = -0.5 * float(q @ q)
    sd, centre, weight = 0.3, 15.0, -14.0
    spike = weight - 2.0 * math.log(sd) - 0.5 * float(((q - centre) / sd) @ ((q - centre) / sd))
    top = max(main, spike)
    value = top + math.log(math.exp(main - top) + math.exp(spike - top))
    w_main, w_spike = math.exp(main - value), math.exp(spike - value)
    return value, w_main * (-q) + w_spike * (-(q - centre) / sd**2)


def test_chain_warnings_name_a_trapped_chain_and_are_silent_on_a_gaussian():
    quiet = owalnuts.sample(lambda q: (-0.5 * float(q @ q), -q), dim=2, warmup=500, draws=1000, seed=5, chains=4)
    assert quiet.chain_warnings() == []
    assert not any(line.startswith("warning: chain") for line in str(quiet).splitlines())
    for chain in quiet.chains:
        assert chain["warmup_end"]["end"] <= 500 and chain["sampling_end"]["start"] == 500
    init = np.array([[-0.75, 0.75], [-0.25, 0.25], [0.25, -0.25], [15.0, 15.0]])
    trapped = owalnuts.sample(_trap, dim=2, warmup=500, draws=300, seed=5, chains=4, init=init)
    warnings = trapped.chain_warnings()
    older = [w for w in warnings if w["check"] != "rhat_cluster"]
    assert older and {w["chain"] for w in older} == {3}
    assert {"warmup_log_density", "sampled_log_density", "rhat"} <= {w["check"] for w in older}
    # The pairwise cluster check (WP74) names chain 3 too. At 300 draws it
    # also names chain 0, whose pair R-hats with chains 1 and 2 (1.011) sit
    # just above 1.01: on a failing run it can name a healthy chain.
    cluster = {w["chain"]: w["reference_chains"] for w in warnings if w["check"] == "rhat_cluster"}
    assert cluster == {0: [1, 2], 3: [1, 2]}
    lines = [line for line in str(trapped).splitlines() if line.startswith("warning: chain")]
    assert [line.split(" disagrees")[0] for line in lines] == ["warning: chain 0", "warning: chain 3"]


def _two_modes(q: np.ndarray) -> tuple[float, np.ndarray]:
    # 0.6 N(-8, 0.5^2) + 0.4 N(8, 0.5^2): two chains started in each mode
    # never cross the 32-SD gap, a split no single chain explains.
    x = float(q[0])
    a = math.log(0.6) - 0.5 * ((x + 8.0) / 0.5) ** 2
    b = math.log(0.4) - 0.5 * ((x - 8.0) / 0.5) ** 2
    top = max(a, b)
    value = top + math.log(math.exp(a - top) + math.exp(b - top))
    w_a, w_b = math.exp(a - value), math.exp(b - value)
    return value, np.array([-(w_a * (x + 8.0) + w_b * (x - 8.0)) / 0.25])


def test_chain_warnings_report_a_two_two_mode_split():
    init = np.array([[-8.0], [8.0], [-8.0], [8.0]])
    result = owalnuts.sample(_two_modes, dim=1, warmup=300, draws=500, seed=3, chains=4, init=init)
    warnings = result.chain_warnings()
    # No single chain explains R-hat, so only the cluster check fires: the
    # lower-density mode's chains, against the reference pair (0, 2).
    assert [(w["chain"], w["check"], w["reference_chains"]) for w in warnings] == [
        (1, "rhat_cluster", [0, 2]),
        (3, "rhat_cluster", [0, 2]),
    ]
    assert all(w["reference"] > 1.01 and w["value"] > 1.01 for w in warnings)
    lines = [line for line in str(result).splitlines() if line.startswith("warning: chain")]
    assert len(lines) == 2 and lines[0].startswith("warning: chain 1 disagrees with the other chains: max R-hat ")
    assert "chains 0, 2 agree in pairs" in lines[0]


def _cliff(q: np.ndarray) -> tuple[float, np.ndarray]:
    # The Rust tests/nonfinite_position_policy.rs cliff: -G |x| with G = 1e308;
    # the first half-kick at step 4 overflows and RejectLeaf rescues the leaf.
    x = float(q[0])
    if abs(x) >= 1.0:
        return -math.inf, np.zeros(1)
    return -1e308 * abs(x), np.array([-1e308 * math.copysign(1.0, x)])


def test_chain_warnings_report_nonfinite_position_rejections():
    result = owalnuts.sample(
        _cliff,
        dim=1,
        warmup=3,
        draws=5,
        seed=11,
        chains=2,
        init=np.array([[0.1], [-0.1]]),
        tuning=owalnuts.Tuning(step_size=4.0, max_depth=3, max_refinement_levels=2),
        adaptation=None,
        mass=np.ones(1),
    )
    counts = [
        (c["work_discarded"]["nonfinite_position_rejections"], c["work_retained"]["nonfinite_position_rejections"])
        for c in result.chains
    ]
    assert all(w >= 3 and s >= 5 for w, s in counts), counts
    assert result.health()["divergences"] == 0
    warnings = result.chain_warnings()
    assert [(w["chain"], w["check"], w["warmup"], w["sampling"]) for w in warnings] == [
        (k, "nonfinite_positions", w, s) for k, (w, s) in enumerate(counts)
    ]
    lines = [line for line in str(result).splitlines() if line.startswith("warning: chain")]
    assert lines == [
        f"warning: chain {k} rejected {w} nonfinite positions during warmup and {s} during sampling"
        for k, (w, s) in enumerate(counts)
    ]


# ── start rules (WP58: init=None is the Rust Init::best_of(16) default) ──


def _half_space(q):
    # Finite only for x0 > 0.5 (about three quarters of uniform(-2, 2) draws fail).
    if q[0] <= 0.5:
        return -np.inf, np.zeros_like(q)
    return -0.5 * float(q @ q), -q


def test_defaults_report_best_of_start_rule():
    assert owalnuts.DEFAULTS["init"] == "best_of"
    assert owalnuts.DEFAULTS["init_candidates"] == 16
    assert owalnuts.START_RULES == ("best_of", "uniform", "jitter")
    with pytest.raises(ValueError, match="best_of"):
        owalnuts.sample(_half_space, 3, init="best", warmup=10, draws=10)


def test_best_of_callable_starts_are_evaluable_and_the_max_of_16_candidates():
    d = owalnuts.best_of_starts(_half_space, 3, chains=4, seed=23, return_details=True)
    starts = d["starts"]
    assert starts.shape == (4, 3)
    assert (starts[:, 0] > 0.5).all() and (np.abs(starts) <= 2.0).all()
    for c in range(4):
        cands = d["candidate_log_densities"][c]
        assert len(cands) == 16
        assert d["chosen"][c] == int(np.argmax(cands))
        assert d["start_log_densities"][c] == max(cands)
        assert d["start_log_densities"][c] == _half_space(starts[c])[0]
        assert d["evaluations"][c] >= 16  # rejected redraws count too
    np.testing.assert_array_equal(starts, owalnuts.best_of_starts(_half_space, 3, chains=4, seed=23))
    # init=None, init="best_of" and the explicit starts give the same run.
    r_none = owalnuts.sample(_half_space, 3, chains=4, warmup=100, draws=100, seed=23)
    r_named = owalnuts.sample(_half_space, 3, init="best_of", chains=4, warmup=100, draws=100, seed=23)
    r_given = owalnuts.sample(_half_space, 3, init=starts, chains=4, warmup=100, draws=100, seed=23)
    np.testing.assert_array_equal(r_none.samples, r_named.samples)
    np.testing.assert_array_equal(r_none.samples, r_given.samples)
    assert (r_none.samples[..., 0] > 0.5).all()


def test_default_init_is_bit_identical_to_rust_init_default():
    dim, chains, warmup, draws, seed = 3, 4, 150, 200, 0x5EED
    reference = np.asarray(owalnuts._owalnuts.reference_gaussian_default_init_run(dim, chains, warmup, draws, seed))
    run = owalnuts.sample(_sequential_gaussian, dim, chains=chains, warmup=warmup, draws=draws, seed=seed)
    np.testing.assert_array_equal(run.samples, reference)


def test_jitter_init_reproduces_the_pre_wp58_unchecked_starts():
    dim, chains, seed = 3, 4, 31
    old = np.random.default_rng(seed).uniform(-2.0, 2.0, size=(chains, dim))
    a = owalnuts.sample(_sequential_gaussian, dim, init="jitter", chains=chains, warmup=100, draws=100, seed=seed)
    b = owalnuts.sample(_sequential_gaussian, dim, init=old, chains=chains, warmup=100, draws=100, seed=seed)
    np.testing.assert_array_equal(a.samples, b.samples)
    c = owalnuts.sample(_sequential_gaussian, dim, init="jitter", init_jitter=0.5, chains=chains, warmup=100,
                        draws=100, seed=seed)
    d = owalnuts.sample(_sequential_gaussian, dim, init=np.random.default_rng(seed).uniform(-0.5, 0.5, (chains, dim)),
                        chains=chains, warmup=100, draws=100, seed=seed)
    np.testing.assert_array_equal(c.samples, d.samples)
    # The unchecked rule is what failed lotka_volterra: it can start outside the support.
    with pytest.raises(RuntimeError, match="not evaluable"):
        owalnuts.sample(_half_space, 3, init="jitter", chains=4, warmup=10, draws=10, seed=1)


def test_best_of_cfunc_starts_are_evaluable_and_match_the_callable_rule():
    numba = pytest.importorskip("numba")
    sig = owalnuts.numba_raw_signature()

    @numba.cfunc(sig, nopython=True)
    def half_space(dim, x_ptr, g_ptr, _ud):
        x = numba.carray(x_ptr, (3,))
        g = numba.carray(g_ptr, (3,))
        if x[0] <= 0.5:
            for i in range(3):
                g[i] = 0.0
            return -np.inf
        total = 0.0
        for i in range(3):
            g[i] = -x[i]
            total += x[i] * x[i]
        return -0.5 * total

    target = owalnuts.from_cfunc(half_space, 3)
    d = owalnuts.best_of_starts(target, chains=4, seed=23, return_details=True)
    assert (d["starts"][:, 0] > 0.5).all()
    for c in range(4):
        assert len(d["candidate_log_densities"][c]) == 16
        assert d["chosen"][c] == int(np.argmax(d["candidate_log_densities"][c]))
    # Same RNG stream and rule as the callable path.
    np.testing.assert_array_equal(d["starts"], owalnuts.best_of_starts(_half_space, 3, chains=4, seed=23))
    r = owalnuts.sample(target, chains=4, warmup=100, draws=100, seed=23, threads=2)
    g = owalnuts.sample(target, init=d["starts"], chains=4, warmup=100, draws=100, seed=23, threads=2)
    np.testing.assert_array_equal(r.samples, g.samples)
