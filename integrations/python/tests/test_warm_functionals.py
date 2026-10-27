"""Streaming functionals on the warm session (``WarmSession.refresh_functionals``,
WP95): the values must be the functionals of ``refresh``'s draws under the
same seed, bit for bit, for Python callables and ``CFuncFunctional``s; the
draws and diagnostics must not depend on the functionals; and the pooled
statistics must be numpy's over the per-draw values."""
import numpy as np
import pytest

import owalnuts

SCALES = np.array([1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0])


def gaussian(dim: int):
    scales = SCALES[:dim]

    def logp_and_grad(q):
        return float(-0.5 * np.sum(q * q / scales)), -q / scales

    return logp_and_grad


def cfunc_gaussian(dim: int):
    numba = pytest.importorskip("numba")

    @numba.cfunc(owalnuts.numba_raw_signature(), nopython=True, error_model="numpy")
    def callback(n, q, g, user):
        value = 0.0
        for i in range(n):
            scale = 1.0 + i
            g[i] = -q[i] / scale
            value -= 0.5 * q[i] * q[i] / scale
        return value

    return owalnuts.from_cfunc(callback, dim)


def starts(chains: int, dim: int) -> np.ndarray:
    return np.array([[0.3 * (c + 1) * (1.0 if (c + i) % 2 == 0 else -1.0) for i in range(dim)] for c in range(chains)])


def adapted(target, dim: int, chains: int = 4) -> owalnuts.WarmState:
    return owalnuts.sample(target, dim, init=starts(chains, dim), chains=chains, warmup=120, draws=10, seed=95,
                           threads=1, tuning=owalnuts.Tuning(max_depth=5)).warm_state()


TUNING = owalnuts.Tuning(max_depth=6)


def sigma(q):
    """exp(x_last / 2): one output."""
    return np.exp(q[-1] / 2.0)


def last_three(q):
    return q[-3:]


def expected_values(samples: np.ndarray) -> np.ndarray:
    """``[sigma, last three]`` of every draw, ``(chains, draws, 4)``."""
    return np.concatenate([np.exp(samples[:, :, -1:] / 2.0), samples[:, :, -3:]], axis=2)


def cfunc_functionals():
    numba = pytest.importorskip("numba")
    sig = owalnuts.numba_functional_signature()

    @numba.cfunc(sig, nopython=True, error_model="numpy")
    def sigma_c(dim, q, out, n_out, user):
        out[0] = np.exp(q[dim - 1] / 2.0)

    @numba.cfunc(sig, nopython=True, error_model="numpy")
    def last_three_c(dim, q, out, n_out, user):
        for j in range(n_out):
            out[j] = q[dim - n_out + j]

    return [owalnuts.from_cfunc_functional(sigma_c, 1), owalnuts.from_cfunc_functional(last_three_c, 3)]


def assert_state_equal(observed: owalnuts.WarmState, expected: owalnuts.WarmState) -> None:
    np.testing.assert_array_equal(observed.positions, expected.positions)
    np.testing.assert_array_equal(observed.step_sizes, expected.step_sizes)
    np.testing.assert_array_equal(observed.mass_diagonal, expected.mass_diagonal)


def assert_matches_refresh(chunk: owalnuts.FunctionalChunk, plain: owalnuts.WarmChunk) -> None:
    assert chunk.seed == plain.seed and chunk.call_index == plain.call_index
    assert chunk.target_calls == plain.target_calls
    assert chunk.values.shape == (plain.samples.shape[0], plain.samples.shape[1], 4)
    assert chunk.offsets == (0, 1, 4)
    np.testing.assert_array_equal(chunk.values, expected_values(plain.samples))
    np.testing.assert_array_equal(chunk.positions, plain.samples[:, -1, :])
    for c in range(plain.samples.shape[0]):
        for key in ("depth", "stop", "target_evaluations", "divergent", "max_abs_energy_error", "leaves_built"):
            np.testing.assert_array_equal(chunk.diagnostics[c][key], plain.diagnostics[c][key])
        assert chunk.metadata[c]["effective_seed"] == plain.metadata[c]["effective_seed"]
        assert chunk.work[c] == plain.work[c]
    np.testing.assert_array_equal(chunk.moments["count"], plain.samples.shape[1])
    np.testing.assert_allclose(chunk.moments["mean"], chunk.values.mean(axis=1), rtol=1e-12, atol=1e-14)
    np.testing.assert_allclose(chunk.moments["m2"], ((chunk.values - chunk.values.mean(axis=1, keepdims=True)) ** 2).sum(axis=1),
                               rtol=1e-10, atol=1e-14)
    np.testing.assert_array_equal(chunk.moments["min"], chunk.values.min(axis=1))
    np.testing.assert_array_equal(chunk.moments["max"], chunk.values.max(axis=1))
    assert_state_equal(chunk.warm_state(), plain.warm_state())


@pytest.mark.parametrize("threads", [1, 4])
def test_callable_functionals_are_the_functionals_of_refresh_draws(threads):
    dim, chains = 6, 4
    target = gaussian(dim)
    start = adapted(target, dim, chains)
    with owalnuts.WarmSession(target, start, seed=500, threads=threads, tuning=TUNING) as plain, \
            owalnuts.WarmSession(target, start, seed=500, threads=threads, tuning=TUNING) as streaming:
        for draws in [5, 10, 7]:
            expected = plain.refresh(draws)
            chunk = streaming.refresh_functionals(draws, [sigma, (last_three, 3)])
            assert chunk.samples is None
            assert_matches_refresh(chunk, expected)
            assert_state_equal(streaming.state(), plain.state())
            assert streaming.calls == plain.calls
        # Draws on request, and a plain refresh after functional calls stays in step.
        chunk = streaming.refresh_functionals(4, [sigma, last_three], retain_draws=True)
        expected = plain.refresh(4)
        np.testing.assert_array_equal(chunk.samples, expected.samples)
        assert_matches_refresh(chunk, expected)
        np.testing.assert_array_equal(streaming.refresh(3).samples, plain.refresh(3).samples)


@pytest.mark.parametrize("threads", [1, 4])
def test_cfunc_functionals_match_the_callables_and_refresh(threads):
    dim = 5
    target = cfunc_gaussian(dim)
    start = adapted(target, dim)
    functionals = cfunc_functionals()
    with owalnuts.WarmSession(target, start, seed=42, threads=threads) as plain, \
            owalnuts.WarmSession(target, start, seed=42, threads=threads) as compiled, \
            owalnuts.WarmSession(target, start, seed=42, threads=threads) as mixed:
        expected = plain.refresh(20)
        chunk = compiled.refresh_functionals(20, functionals)
        assert_matches_refresh(chunk, expected)
        # A cfunc and a callable in one call, on a cfunc target.
        via_mixed = mixed.refresh_functionals(20, [functionals[0], last_three])
        np.testing.assert_array_equal(via_mixed.values, chunk.values)
        # The second call follows the seed rule (42 + 1 * 4).
        expected = plain.refresh(8)
        assert expected.seed == 46
        assert_matches_refresh(compiled.refresh_functionals(8, functionals), expected)


def test_functionals_follow_a_retarget_and_sample_warm():
    small, large = gaussian(6), gaussian(7)
    start = adapted(small, 6)
    with owalnuts.WarmSession(small, start, seed=9, threads=2) as session:
        session.refresh_functionals(4, [sigma])
        grown = session.state().extend_to(7, position=0.0, mass=1.0)
        session.retarget(large, grown)
        chunk = session.refresh_functionals(6, [sigma, (last_three, 3)])
        assert chunk.call_index == 1 and chunk.values.shape == (4, 6, 4)
        expected = owalnuts.sample_warm(large, grown, draws=6, seed=9 + 4, threads=2)
        np.testing.assert_array_equal(chunk.values, expected_values(expected.samples))
        assert_state_equal(chunk.warm_state(), expected.warm_state())
        assert_state_equal(session.state(), expected.warm_state())


def test_pooled_statistics_are_numpys_over_the_values():
    dim = 4
    target = gaussian(dim)
    start = adapted(target, dim, chains=3)
    with owalnuts.WarmSession(target, start, seed=5, tuning=TUNING) as session:
        chunk = session.refresh_functionals(9, [sigma, last_three])
    assert chunk.chains == 3 and chunk.draws == 9 and chunk.outputs == 4
    for output in range(4):
        values = chunk.values[:, :, output]
        np.testing.assert_array_equal(chunk.output(output), values)
        assert chunk.mean(output) == float(values.mean())
        np.testing.assert_array_equal(chunk.mean(output, per_chain=True), values.mean(axis=1))
        assert chunk.variance(output) == float(values.var(ddof=1))
        np.testing.assert_array_equal(chunk.variance(output, per_chain=True), values.var(axis=1, ddof=1))
        for q in (0.0, 0.05, 0.5, 0.9, 1.0):
            assert chunk.quantile(q, output) == np.quantile(values.reshape(-1), q)
            np.testing.assert_array_equal(chunk.quantile(q, output, per_chain=True), np.quantile(values, q, axis=1))
        np.testing.assert_array_equal(chunk.quantile([0.05, 0.95], output), np.quantile(values.reshape(-1), [0.05, 0.95]))
        # Pooled over every chain, not the mean of per-chain quantiles.
        pooled = np.sort(values.reshape(-1))
        assert chunk.quantile(0.5, output) == pooled[13]
    np.testing.assert_array_equal(chunk.functional(0), chunk.values[:, :, :1])
    np.testing.assert_array_equal(chunk.functional(1), chunk.values[:, :, 1:])
    np.testing.assert_array_equal(chunk.output(0), np.exp(chunk.output(3) / 2.0))
    with pytest.raises(IndexError):
        chunk.output(4)
    with pytest.raises(IndexError):
        chunk.functional(2)


def test_functional_errors_end_the_call_and_bad_inputs_are_rejected():
    dim = 4
    target = gaussian(dim)
    start = adapted(target, dim, chains=2)
    with owalnuts.WarmSession(target, start, seed=5) as session:
        with pytest.raises(ValueError):
            session.refresh_functionals(0, [sigma])
        with pytest.raises(TypeError):
            session.refresh_functionals(3, sigma)
        with pytest.raises(TypeError):
            session.refresh_functionals(3, [3.0])
        with pytest.raises(ValueError):
            session.refresh_functionals(3, [(sigma, -1)])
        with pytest.raises(ValueError):
            owalnuts.from_cfunc_functional(1, -1)
        assert session.calls == 0
        empty = session.refresh_functionals(3, [])
        assert empty.values.shape == (2, 3, 0) and empty.offsets == (0,)
        assert session.calls == 1
        # A declared output count the callable does not honour is an execution error.
        with pytest.raises(RuntimeError, match="values"):
            session.refresh_functionals(3, [(last_three, 2)])
        assert session.terminal

    def boom(q):
        raise ValueError("no quote")

    with owalnuts.WarmSession(target, start, seed=5) as session:
        with pytest.raises(RuntimeError, match="no quote"):
            session.refresh_functionals(3, [(boom, 1)])
        assert session.terminal
        with pytest.raises(RuntimeError):
            session.refresh(1)
