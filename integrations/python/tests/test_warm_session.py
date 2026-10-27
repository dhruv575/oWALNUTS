"""Resident warm session (``owalnuts.WarmSession``) and the state remaps
(``WarmState.remap`` / ``shift_window``): every ``refresh(k)`` must be
bit-identical to ``sample_warm`` under the seed rule (call ``n`` uses
``seed + n * chains``), for callable and ``CFuncTarget`` targets, before and
after a ``retarget``; a fixed-lag loop must chain over ticks."""
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
    return owalnuts.sample(target, dim, init=starts(chains, dim), chains=chains, warmup=120, draws=10, seed=91,
                           threads=1, tuning=owalnuts.Tuning(max_depth=5)).warm_state()


TUNING = owalnuts.Tuning(max_depth=6)


def assert_state_equal(observed: owalnuts.WarmState, expected: owalnuts.WarmState) -> None:
    np.testing.assert_array_equal(observed.positions, expected.positions)
    np.testing.assert_array_equal(observed.step_sizes, expected.step_sizes)
    np.testing.assert_array_equal(observed.mass_diagonal, expected.mass_diagonal)


def assert_chunk_equals(chunk: owalnuts.WarmChunk, expected: owalnuts.SampleResult, seed: int) -> None:
    assert chunk.seed == seed
    np.testing.assert_array_equal(chunk.samples, expected.samples)
    assert chunk.target_calls == expected.target_calls
    for c, chain in enumerate(expected.chains):
        for key in ("depth", "stop", "target_evaluations", "divergent", "max_abs_energy_error", "leaves_built"):
            np.testing.assert_array_equal(chunk.diagnostics[c][key], chain[key])
        assert chunk.metadata[c]["effective_seed"] == chain["metadata"]["effective_seed"]
        assert chunk.metadata[c]["final_step_size"] == chain["metadata"]["final_step_size"]
        np.testing.assert_array_equal(chunk.metadata[c]["mass_diagonal"], chain["metadata"]["mass_diagonal"])
    assert_state_equal(chunk.warm_state(), expected.warm_state())


@pytest.mark.parametrize("threads", [1, 4])
def test_refresh_is_bit_identical_to_sample_warm_under_the_seed_rule(threads):
    dim, chains = 6, 4
    target = gaussian(dim)
    start = adapted(target, dim, chains)
    with owalnuts.WarmSession(target, start, seed=500, threads=threads, tuning=TUNING) as session:
        assert session.threads == threads and session.chains == chains and session.calls == 0
        assert_state_equal(session.state(), start)
        for call, draws in enumerate([5, 10, 7]):
            seed = 500 + call * chains
            assert session.next_seed == seed == session.seed_for_call(call)
            before = session.state()
            expected = owalnuts.sample_warm(target, before, draws=draws, seed=seed, threads=threads, tuning=TUNING)
            chunk = session.refresh(draws)
            assert chunk.call_index == call and chunk.samples.shape == (chains, draws, dim)
            assert_chunk_equals(chunk, expected, seed)
            assert_state_equal(session.state(), expected.warm_state())
            assert session.calls == call + 1
        assert not session.terminal


@pytest.mark.parametrize("threads", [1, 4])
def test_cfunc_session_is_bit_identical_to_sample_warm_and_to_the_callable(threads):
    dim = 5
    target = cfunc_gaussian(dim)
    start = adapted(target, dim)
    with owalnuts.WarmSession(target, start, seed=42, threads=threads) as session:
        expected = owalnuts.sample_warm(target, start, draws=20, seed=42, threads=threads)
        chunk = session.refresh(20)
        assert_chunk_equals(chunk, expected, 42)
        via_callable = owalnuts.sample_warm(gaussian(dim), start, draws=20, seed=42)
        np.testing.assert_array_equal(chunk.samples, via_callable.samples)
        # Second call, the seed rule: 42 + 1 * 4.
        expected = owalnuts.sample_warm(target, session.state(), draws=8, seed=46, threads=threads)
        assert_chunk_equals(session.refresh(8), expected, 46)


def test_retarget_grows_the_dimension_and_continues_the_seed_sequence():
    small, large = gaussian(6), gaussian(7)
    start = adapted(small, 6)
    session = owalnuts.WarmSession(small, start, seed=9, threads=2)
    session.refresh(4)
    session.refresh(4)
    grown = session.state().extend_to(7, position=0.0, mass=1.0)       # WP88: one latent appended
    session.retarget(large, grown)
    assert_state_equal(session.state(), grown)
    assert session.calls == 2
    expected = owalnuts.sample_warm(large, grown, draws=6, seed=9 + 2 * 4, threads=2)
    assert_chunk_equals(session.refresh(6), expected, 9 + 2 * 4)
    session.close()
    with pytest.raises(RuntimeError):
        session.refresh(1)


def test_retarget_rejects_a_mismatched_state_or_target_kind_without_ending_the_session():
    dim = 6
    target = gaussian(dim)
    start = adapted(target, dim)
    with owalnuts.WarmSession(target, start, seed=3) as session:
        two_chains = owalnuts.WarmState(start.positions[:2], start.step_sizes[:2], start.mass_diagonal[:2])
        with pytest.raises(ValueError):
            session.retarget(target, two_chains)
        with pytest.raises(TypeError):
            session.retarget(cfunc_gaussian(dim), start)
        with pytest.raises(ValueError):
            session.refresh(0)
        assert not session.terminal and session.calls == 0
        expected = owalnuts.sample_warm(target, start, draws=4, seed=3)
        assert_chunk_equals(session.refresh(4), expected, 3)
    cf = cfunc_gaussian(4)
    with owalnuts.WarmSession(cf, adapted(cf, 4), seed=1) as session:
        with pytest.raises(TypeError):
            session.retarget(gaussian(4), session.state())
        with pytest.raises(ValueError):
            session.retarget(cfunc_gaussian(5), session.state())   # cfunc dim != state dim
    # A callable of another dimension takes its dimension from the state, so
    # the mismatch surfaces at the first evaluation (a gradient of the wrong
    # length), which is a fatal execution error.
    with owalnuts.WarmSession(target, start, seed=3) as session:
        session.retarget(gaussian(8), start)
        with pytest.raises(RuntimeError, match="dimension|not evaluable"):
            session.refresh(2)
        assert session.terminal


def test_fixed_lag_window_chains_over_twenty_ticks():
    """One scale plus five latents; each tick drops the oldest latent and
    appends one at the prior fill, so the dimension stays 6 and the
    session's draws match ``sample_warm`` on the shifted state."""
    dim, chains = 6, 3

    def make_target(tick):
        scales = SCALES[:dim] * (1.0 + 0.01 * tick)        # the "new observation" changes the target

        def logp_and_grad(q):
            return float(-0.5 * np.sum(q * q / scales)), -q / scales

        return logp_and_grad

    state = adapted(make_target(0), dim, chains)
    with owalnuts.WarmSession(make_target(0), state, seed=11, threads=3) as session:
        for tick in range(20):
            current = session.state()
            shifted = current.remap(dim, lambda j: 0 if j == 0 else (j + 1 if j < dim - 1 else None),
                                    fill=lambda chain, j: (0.1 * chain, 1.0))
            np.testing.assert_array_equal(shifted.positions[:, 0], current.positions[:, 0])
            np.testing.assert_array_equal(shifted.positions[:, 1:-1], current.positions[:, 2:])
            np.testing.assert_array_equal(shifted.positions[:, -1], 0.1 * np.arange(chains))
            session.retarget(make_target(tick + 1), shifted)
            seed = 11 + tick * chains
            expected = owalnuts.sample_warm(make_target(tick + 1), shifted, draws=5, seed=seed, threads=3)
            assert_chunk_equals(session.refresh(5), expected, seed)
        assert session.calls == 20


def test_refused_admission_leaves_the_session_intact_and_execution_errors_end_it():
    dim = 4
    target = gaussian(dim)
    start = adapted(target, dim, chains=2)
    # A budget that admits one transition per chain but not ten thousand.
    one_draw = owalnuts.preflight(dim, chains=2, warmup=0, draws=1, adaptation=None)["worst_case_target_evaluations"]
    with owalnuts.WarmSession(target, start, seed=5, max_target_evaluations=one_draw) as session:
        with pytest.raises(RuntimeError, match="ResourceLimit"):
            session.refresh(10_000)                       # refused at admission, no target call
        assert not session.terminal
        expected = owalnuts.sample_warm(target, start, draws=1, seed=5, max_target_evaluations=one_draw)
        assert_chunk_equals(session.refresh(1), expected, 5)
        assert session.calls == 1
    with pytest.raises(RuntimeError, match="ResourceLimit"):
        owalnuts.WarmSession(target, start, seed=5, max_target_evaluations=8)

    def fatal(q):
        raise RuntimeError("boom")

    with owalnuts.WarmSession(fatal, start, seed=5, nonfinite="fatal") as session:
        with pytest.raises(RuntimeError):
            session.refresh(3)
        assert session.terminal
        with pytest.raises(RuntimeError):
            session.refresh(1)


def test_warm_session_validates_its_inputs():
    state = adapted(gaussian(4), 4)
    with pytest.raises(TypeError):
        owalnuts.WarmSession(gaussian(4), state.positions)
    with pytest.raises(ValueError):
        owalnuts.WarmSession(gaussian(4), state, threads=0)
    with pytest.raises(ValueError):
        owalnuts.WarmSession(cfunc_gaussian(5), state)
    with pytest.raises(RuntimeError, match="dimension"):
        owalnuts.WarmSession(lambda q: (0.0, np.zeros(5)), state).refresh(1)


def two_chain_state() -> owalnuts.WarmState:
    return owalnuts.WarmState(
        positions=np.array([[1.0, 2.0, 3.0, 4.0], [-1.0, -2.0, -3.0, -4.0]]),
        step_sizes=np.array([0.5, 0.25]),
        mass_diagonal=np.array([[10.0, 20.0, 30.0, 40.0], [11.0, 21.0, 31.0, 41.0]]),
    )


def test_remap_copies_mapped_coordinates_and_fills_the_rest():
    state = two_chain_state()
    mapped = state.remap(5, lambda j: {0: 3, 1: 3, 2: 0}.get(j),
                         fill=lambda chain, j: (100.0 * chain + j, 0.5 + j))
    np.testing.assert_array_equal(mapped.positions, [[4.0, 4.0, 1.0, 3.0, 4.0], [-4.0, -4.0, -1.0, 103.0, 104.0]])
    np.testing.assert_array_equal(mapped.mass_diagonal, [[40.0, 40.0, 10.0, 3.5, 4.5], [41.0, 41.0, 11.0, 3.5, 4.5]])
    np.testing.assert_array_equal(mapped.step_sizes, state.step_sizes)
    constant = state.remap(2, lambda j: None, fill=(7.0, 2.0))
    np.testing.assert_array_equal(constant.positions, 7.0)
    np.testing.assert_array_equal(constant.mass_diagonal, 2.0)
    assert_state_equal(state.remap(4, lambda j: j), state)
    with pytest.raises(ValueError, match="coordinate 4"):
        state.remap(2, lambda j: j + 3)
    with pytest.raises(ValueError):
        state.remap(0, lambda j: j)
    with pytest.raises(ValueError):
        state.remap(2, lambda j: None, fill=(0.0, 0.0))


def test_shift_window_drops_the_oldest_and_appends_and_extend_to_agrees():
    state = two_chain_state()
    shifted = state.shift_window(1, 1, fill=lambda chain, j: (10.0 * chain, float(j)))
    np.testing.assert_array_equal(shifted.positions, [[2.0, 3.0, 4.0, 0.0], [-2.0, -3.0, -4.0, 10.0]])
    np.testing.assert_array_equal(shifted.mass_diagonal, [[20.0, 30.0, 40.0, 3.0], [21.0, 31.0, 41.0, 3.0]])
    assert_state_equal(state.shift_window(0, 1, position=0.0, mass=1.0), state.extend_to(5, position=0.0, mass=1.0))
    assert_state_equal(state.shift_window(0, 0), state)
    np.testing.assert_array_equal(state.shift_window(3, 0).positions, [[4.0], [-4.0]])
    with pytest.raises(ValueError):
        state.shift_window(5, 1)
    with pytest.raises(ValueError):
        state.shift_window(4, 0)
    with pytest.raises(ValueError):
        state.extend_to(3)
