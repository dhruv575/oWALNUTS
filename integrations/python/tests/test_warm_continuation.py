"""Warm continuation: ``sample_warm`` must be bit-identical, chain by chain,
to the single-chain ``sample`` calls the WP84 harness built from the public
API, for callable and ``CFuncTarget`` targets."""
from dataclasses import replace

import numpy as np
import pytest

import owalnuts

SCALES = np.array([1.0, 2.0, 3.0, 4.0, 5.0, 6.0])


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


def adapted(target, dim: int, chains: int = 4) -> owalnuts.SampleResult:
    return owalnuts.sample(target, dim, init=starts(chains, dim), chains=chains, warmup=120, draws=10, seed=84,
                           threads=1, tuning=owalnuts.Tuning(max_depth=5))


def harness_chain(target, dim: int, state: owalnuts.WarmState, chain: int, seed: int, draws: int,
                  tuning: owalnuts.Tuning) -> owalnuts.SampleResult:
    """One warm chain as the WP84 harness built it: a single-chain run from
    the carried start with the carried step and fixed diagonal mass, no
    warmup, no adaptation, seed ``seed + chain``."""
    return owalnuts.sample(
        target, dim, init=state.positions[chain:chain + 1], chains=1, warmup=0, draws=draws, seed=seed + chain,
        adaptation=None, mass=state.mass_diagonal[chain], tuning=replace(tuning, step_size=float(state.step_sizes[chain])),
    )


def assert_identical(warm: owalnuts.SampleResult, oracle: list[owalnuts.SampleResult]) -> None:
    assert warm.samples.shape[0] == len(oracle)
    for c, expected in enumerate(oracle):
        np.testing.assert_array_equal(warm.samples[c], expected.samples[0])
        for key in ("depth", "stop", "target_evaluations", "divergent", "max_abs_energy_error", "leaves_built"):
            np.testing.assert_array_equal(warm.chains[c][key], expected.chains[0][key])
        assert warm.chains[c]["metadata"]["effective_seed"] == expected.chains[0]["metadata"]["effective_seed"]
        assert warm.chains[c]["metadata"]["final_step_size"] == expected.chains[0]["metadata"]["final_step_size"]
        np.testing.assert_array_equal(warm.chains[c]["metadata"]["mass_diagonal"],
                                      expected.chains[0]["metadata"]["mass_diagonal"])


def test_warm_state_is_the_last_draw_final_step_and_mass():
    dim = 6
    result = adapted(gaussian(dim), dim)
    state = result.warm_state()
    assert (state.chains, state.dim) == (4, dim)
    np.testing.assert_array_equal(state.positions, result.samples[:, -1, :])
    np.testing.assert_array_equal(state.step_sizes, result.final_step_size)
    for c in range(4):
        np.testing.assert_array_equal(state.mass_diagonal[c], result.chains[c]["metadata"]["mass_diagonal"])
    assert state.step_sizes[0] != state.step_sizes[1]
    assert not np.array_equal(state.mass_diagonal[0], state.mass_diagonal[1])


@pytest.mark.parametrize("threads", [1, 4])
def test_sample_warm_callable_is_bit_identical_to_per_chain_sample(threads):
    dim = 6
    target = gaussian(dim)
    state = adapted(target, dim).warm_state()
    tuning = owalnuts.Tuning(max_depth=6)
    oracle = [harness_chain(target, dim, state, c, 777, 50, tuning) for c in range(4)]
    warm = owalnuts.sample_warm(target, state, draws=50, seed=777, threads=threads, tuning=tuning)
    assert_identical(warm, oracle)
    assert warm.samples.shape == (4, 50, dim)
    assert all(c["metadata"]["thread_count"] == threads for c in warm.chains)
    assert warm.config["warmup"] == 0 and warm.config["adapt"] is False


@pytest.mark.parametrize("threads", [1, 4])
def test_sample_warm_cfunc_is_bit_identical_to_per_chain_sample(threads):
    dim = 5
    target = cfunc_gaussian(dim)
    state = adapted(target, dim).warm_state()
    tuning = owalnuts.Tuning()
    oracle = [harness_chain(target, dim, state, c, 4242, 40, tuning) for c in range(4)]
    warm = owalnuts.sample_warm(target, state, draws=40, seed=4242, threads=threads, tuning=tuning)
    assert_identical(warm, oracle)
    # The cfunc and callable transports of the same density agree bit for bit.
    via_callable = owalnuts.sample_warm(gaussian(dim), state, draws=40, seed=4242, tuning=tuning)
    np.testing.assert_array_equal(warm.samples, via_callable.samples)


def test_sample_warm_one_chain_equals_sample_with_the_same_seed():
    dim = 4
    target = gaussian(dim)
    state = adapted(target, dim, chains=1).warm_state()
    warm = owalnuts.sample_warm(target, state, draws=30, seed=9)
    plain = owalnuts.sample(target, dim, init=state.positions, chains=1, warmup=0, draws=30, seed=9, adaptation=None,
                            mass=state.mass_diagonal[0], tuning=owalnuts.Tuning(step_size=float(state.step_sizes[0])))
    np.testing.assert_array_equal(warm.samples, plain.samples)
    for key, value in plain.chains[0]["metadata"].items():
        np.testing.assert_array_equal(warm.chains[0]["metadata"][key], value)


def test_extend_to_grows_onto_a_larger_target_and_chains_through_ticks():
    small, large = gaussian(4), gaussian(6)
    state = adapted(small, 4, chains=3).warm_state()
    grown = state.extend_to(6, position=0.0, mass=1.0)
    assert (grown.chains, grown.dim) == (3, 6)
    np.testing.assert_array_equal(grown.positions[:, :4], state.positions)
    np.testing.assert_array_equal(grown.positions[:, 4:], 0.0)
    np.testing.assert_array_equal(grown.mass_diagonal[:, :4], state.mass_diagonal)
    np.testing.assert_array_equal(grown.mass_diagonal[:, 4:], 1.0)
    np.testing.assert_array_equal(grown.step_sizes, state.step_sizes)
    assert state.extend_to(4).positions.shape == (3, 4)
    with pytest.raises(ValueError):
        state.extend_to(3)
    with pytest.raises(ValueError):
        state.extend_to(5, mass=0.0)

    tuning = owalnuts.Tuning()
    tick1 = owalnuts.sample_warm(large, grown, draws=25, seed=1)
    assert_identical(tick1, [harness_chain(large, 6, grown, c, 1, 25, tuning) for c in range(3)])
    nxt = tick1.warm_state()
    np.testing.assert_array_equal(nxt.positions, tick1.samples[:, -1, :])
    np.testing.assert_array_equal(nxt.step_sizes, grown.step_sizes)
    tick2 = owalnuts.sample_warm(large, nxt, draws=25, seed=2)
    assert_identical(tick2, [harness_chain(large, 6, nxt, c, 2, 25, tuning) for c in range(3)])


def test_session_chunk_warm_state_equals_the_result_warm_state():
    dim = 3
    target = cfunc_gaussian(dim)
    init = starts(2, dim)
    settings = dict(init=init, chains=2, warmup=60, seed=5, tuning=owalnuts.Tuning(max_depth=5))
    full = owalnuts.sample(target, draws=9, **settings)
    with owalnuts.start_session(target, max_draws=9, **settings) as session:
        warmup = session.adapt()
        with pytest.raises(ValueError):
            warmup.warm_state()
        first = session.draw(4)
        last = session.draw(5)
    expected = full.warm_state()
    observed = last.warm_state()
    np.testing.assert_array_equal(observed.positions, expected.positions)
    np.testing.assert_array_equal(observed.step_sizes, expected.step_sizes)
    np.testing.assert_array_equal(observed.mass_diagonal, expected.mass_diagonal)
    np.testing.assert_array_equal(first.warm_state().positions, full.samples[:, 3, :])


def test_warm_state_and_sample_warm_validate_their_inputs():
    with pytest.raises(ValueError):
        owalnuts.WarmState(np.zeros((2, 3)), np.array([0.5, 0.5]), np.ones((2, 2)))
    with pytest.raises(ValueError):
        owalnuts.WarmState(np.zeros((2, 3)), np.array([0.5, 0.0]), np.ones((2, 3)))
    with pytest.raises(ValueError):
        owalnuts.WarmState(np.zeros((2, 3)), np.array([0.5]), np.ones((2, 3)))
    with pytest.raises(ValueError):
        owalnuts.WarmState(np.full((1, 3), np.nan), np.array([0.5]), np.ones((1, 3)))
    with pytest.raises(ValueError):
        owalnuts.WarmState(np.zeros((1, 3)), np.array([0.5]), -np.ones((1, 3)))
    state = owalnuts.WarmState(np.zeros((2, 3)), np.array([0.5, 0.6]), np.ones((2, 3)))
    assert state.positions.dtype == np.float64 and state.positions.flags.c_contiguous
    with pytest.raises(TypeError):
        owalnuts.sample_warm(gaussian(3), state.positions, draws=5)
    with pytest.raises(ValueError):
        owalnuts.sample_warm(gaussian(3), state, draws=0)
    with pytest.raises(ValueError):
        owalnuts.sample_warm(cfunc_gaussian(4), state, draws=5)
    with pytest.raises(RuntimeError, match="dimension"):
        # A callable of another dimension: the target returns a gradient of
        # the wrong length, which the facade rejects.
        owalnuts.sample_warm(lambda q: (0.0, np.zeros(4)), state, draws=5)
    structured = owalnuts.sample(gaussian(3), 3, init=starts(2, 3), chains=2, warmup=0, draws=3, adaptation=None,
                                 mass=owalnuts.tridiagonal_precision_mass(np.ones(3), np.zeros(2)))
    with pytest.raises(ValueError, match="structured"):
        structured.warm_state()


def test_sample_warm_respects_the_shared_evaluation_budget():
    dim = 4
    target = gaussian(dim)
    state = adapted(target, dim).warm_state()
    with pytest.raises(RuntimeError, match="ResourceLimit|budget"):
        owalnuts.sample_warm(target, state, draws=200, max_target_evaluations=8)
