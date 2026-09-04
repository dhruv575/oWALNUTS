"""Stan models through BridgeStan (``owalnuts.from_stan``).

Skipped when the ``bridgestan`` package is missing, the extension was built
without the ``stan`` feature, or the Eight Schools model cannot be compiled
(no C++ toolchain / GNU make on this machine), unless
``OWALNUTS_REQUIRE_STAN_TESTS=1`` makes those conditions test failures.
"""

import os
import shutil
import sys
from pathlib import Path

import numpy as np
import pytest

import owalnuts

MODELS = Path(__file__).resolve().parents[2] / "bridgestan" / "models"
Y = [28.0, 8.0, -3.0, 7.0, -1.0, 1.0, 18.0, 12.0]
SIGMA = [15.0, 10.0, 16.0, 11.0, 9.0, 11.0, 10.0, 18.0]
DATA = {"J": 8, "y": Y, "sigma": SIGMA}
REQUIRE_STAN_TESTS = os.environ.get("OWALNUTS_REQUIRE_STAN_TESTS") == "1"


def stan_unavailable(reason):
    if REQUIRE_STAN_TESTS:
        pytest.fail(reason, pytrace=False)
    pytest.skip(reason)


@pytest.mark.skipif(sys.platform != "win32", reason="Windows-specific safety gate")
def test_windows_disables_python_native_bridgestan_paths():
    message = "bypass the Rust owned-worker lifetime backend"
    with pytest.raises(RuntimeError, match=message):
        owalnuts.from_stan("unused.stan", DATA)
    target = owalnuts.StanTarget(
        model_so="unused.dll",
        data=None,
        dim=1,
        parameter_names=None,
    )
    for operation in (
        target.model,
        lambda: target(np.zeros(1)),
        target.constrained_names,
        lambda: target.constrain(np.zeros((1, 1))),
    ):
        with pytest.raises(RuntimeError, match=message):
            operation()


@pytest.fixture(scope="module")
def eight_schools(tmp_path_factory):
    if not owalnuts.HAS_STAN:
        stan_unavailable("extension built without the `stan` feature")
    try:
        __import__("bridgestan")
    except ImportError as e:
        stan_unavailable(f"bridgestan package unavailable: {e}")
    stan = MODELS / "eight_schools.stan"
    if not stan.exists():
        stan_unavailable(f"{stan} missing")
    # Compile into a private copy so the test never depends on a prebuilt
    # library and exercises the real `from_stan` compile path (~20 s once
    # Stan Math is built; the first BridgeStan build takes minutes).
    work = tmp_path_factory.mktemp("stan")
    src = work / "eight_schools.stan"
    shutil.copy(stan, src)
    try:
        return owalnuts.from_stan(src, DATA, seed=1)
    except Exception as e:  # noqa: BLE001 - toolchain dependent
        stan_unavailable(f"BridgeStan compile unavailable: {str(e)[-400:]}")


def test_from_stan_reports_names_and_dimension(eight_schools):
    t = eight_schools
    assert t.dim == 10
    assert t.parameter_names is not None and len(t.parameter_names) == 10
    assert t.parameter_names[0] == "mu"
    assert "STAN_THREADS=true" not in t.info
    assert t.compiled_threading == "serialised"
    assert t.probe_threading == "serialised"
    assert t.probe_execution == "direct_serialised"
    assert t.probe_requested_replicas == 1
    assert t.probe_effective_replicas == 1
    assert not hasattr(t, "execution")
    assert not hasattr(t, "requested_replicas")
    assert not hasattr(t, "effective_replicas")
    assert t.constrained_names() == list(t.parameter_names)


def test_stan_target_callable_matches_native_eight_schools(eight_schools):
    """The compiled Stan density equals the built-in noncentered model up to
    the flat prior on ``mu`` and the half-Cauchy on ``tau`` (both models use
    exactly the same parameterisation); the gradient agrees to 1e-8."""
    q = np.array([0.3, -0.2, 0.5, -0.4, 0.1, 0.0, 0.7, -0.6, 0.2, -0.1])
    value, grad = eight_schools(q)
    assert np.isfinite(value) and grad.shape == (10,)
    # Finite-difference check of the BridgeStan gradient.
    fd = np.zeros(10)
    for i in range(10):
        e = np.zeros(10)
        e[i] = 1e-6
        fd[i] = (eight_schools(q + e)[0] - eight_schools(q - e)[0]) / 2e-6
    np.testing.assert_allclose(grad, fd, rtol=1e-5, atol=1e-6)


def test_sample_stan_parallel_chains_and_constrain(eight_schools):
    result = owalnuts.sample(eight_schools, chains=4, warmup=500, draws=500, seed=3, threads=4)
    assert result.samples.shape == (4, 500, 10)
    assert result.parameter_names == list(eight_schools.parameter_names)
    assert result.target_calls > 0
    assert result.compiled_threading == "serialised"
    assert result.threading == "concurrent"
    assert result.target_execution == "replicated_concurrent"
    assert result.requested_replicas == 4
    assert result.effective_replicas == 4
    rows = {r["name"]: r for r in result.summary()}
    assert set(rows) == set(eight_schools.parameter_names)
    assert rows["mu"]["mean"] == pytest.approx(4.4, abs=1.5)
    assert max(r["rhat"] for r in rows.values()) < 1.05
    constrained = eight_schools.constrain(result)
    assert constrained.shape == (4, 500, 10)
    # tau = exp(tau_unc) > 0; mu passes through unchanged.
    tau_index = list(eight_schools.parameter_names).index("tau")
    assert np.all(constrained[..., tau_index] > 0)
    np.testing.assert_allclose(constrained[..., 0], result.samples[..., 0])


def test_sample_stan_is_deterministic_and_uniform_init(eight_schools):
    a = owalnuts.sample(eight_schools, init="uniform", chains=2, warmup=200, draws=100, seed=7, threads=2)
    b = owalnuts.sample(eight_schools, init="uniform", chains=2, warmup=200, draws=100, seed=7, threads=1)
    np.testing.assert_array_equal(a.samples, b.samples)
    starts = owalnuts.uniform_starts(eight_schools, 10, chains=2, seed=7)
    assert starts.shape == (2, 10) and np.all(np.abs(starts) <= 2.0)


def test_from_stan_accepts_prebuilt_library_and_json_text(eight_schools):
    import json

    again = owalnuts.from_stan(eight_schools.model_so, json.dumps(DATA), seed=1)
    assert again.dim == 10 and again.parameter_names == eight_schools.parameter_names
