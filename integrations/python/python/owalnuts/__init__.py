"""oWALNUTS for Python: within-orbit adaptive leapfrog NUTS on any differentiable target.

The lowest common denominator is a callable ``f(q) -> (log_density, gradient)``
taking and returning ``float64`` numpy arrays. Adapters wrap JAX, PyTorch and
PyMC models into that shape. Every run goes through the Rust ``walnutpie``
facade; this module only marshals arrays and configuration.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Sequence

import numpy as np

from . import _owalnuts

ALGORITHM_REVISION: str = _owalnuts.ALGORITHM_REVISION
PAPER_ADAPTATION_REVISION: str = _owalnuts.PAPER_ADAPTATION_REVISION
STOP_CODES: tuple[str, ...] = tuple(_owalnuts.STOP_CODES)

LogpGrad = Callable[[np.ndarray], tuple[float, np.ndarray]]


class ZeroDensityError(Exception):
    """Raise from a target to declare the position outside the support.

    The kernel treats it as an infinite endpoint energy error: the macro step
    is refined, and only if every refinement level still fails does the leaf
    receive zero weight. Returning ``-np.inf`` has the same effect.
    """


# ── Configuration ────────────────────────────────────────────────────────


@dataclass(frozen=True)
class PaperAdaptation:
    """JMLR Appendix C adaptation: K-quantile rule for the local error
    threshold and a Gamma-target rule for the macro step."""

    global_energy_bound: float = 2.0
    quantile_probability: float = 0.95
    unrefined_fraction_target: float = 0.8
    adapt_local_error: bool = True
    minimum_orbits: int | None = None
    step_statistic: str | None = None  # "per_transition" | "cumulative"
    restart_policy: str | None = None  # "continue" | "restart"

    def to_dict(self) -> dict[str, Any]:
        return {k: v for k, v in self.__dict__.items() if v is not None}


@dataclass(frozen=True)
class Tuning:
    """Kernel tuning. ``step_size`` is the macro step ``h``; ``max_error`` is
    the local energy-error threshold ``delta``. The defaults match
    ``owalnuts::sampler::Tuning::default()`` (``h = 0.5``, depth 10, eight
    refinement levels, ``delta = 1``); the 0.1 package used ``h = 0.1`` and
    depth 8. The kernel rules are the frozen ``walnutpie`` ones (endpoint
    U-turn rule, unit-variance metric prior); the Rust ``sampler`` defaults
    are ``MomentumSum`` and Stan's metric prior since the post-WP31 default
    change, which the next extension build follows."""

    step_size: float = 0.5
    max_depth: int = 10
    min_micro_steps: int = 1
    max_refinement_levels: int = 8
    max_error: float = 1.0
    divergence_threshold: float = 1000.0


@dataclass(frozen=True)
class Adaptation:
    """Warmup adaptation during the discarded transitions."""

    target_accept: float = 0.8
    adapt_step_size: bool = True
    adapt_mass: bool = True
    paper: PaperAdaptation | None = None


@dataclass
class SampleResult:
    samples: np.ndarray  # (chains, draws, dim)
    chains: list[dict[str, Any]]
    algorithm_revision: str
    wall_seconds: float
    target_calls: int
    target_recoverable_failures: int
    target_attached_seconds: float
    config: dict[str, Any] = field(default_factory=dict)
    refresh_updates: list[dict[str, Any]] | None = None

    # convenience --------------------------------------------------------
    @property
    def depth(self) -> np.ndarray:
        return np.stack([c["depth"] for c in self.chains])

    @property
    def divergent(self) -> np.ndarray:
        return np.stack([c["divergent"] for c in self.chains])

    @property
    def retained_target_calls(self) -> int:
        return int(sum(c["work_retained"]["target_calls_total"] for c in self.chains))

    @property
    def final_step_size(self) -> np.ndarray:
        return np.array([c["metadata"]["final_step_size"] for c in self.chains])

    @property
    def final_max_error(self) -> np.ndarray:
        return np.array([c["metadata"]["final_max_error"] for c in self.chains])

    def to_inferencedata(self, var_names: Sequence[str] | None = None, warmup: int | None = None):
        return to_inferencedata(self, var_names=var_names, warmup=warmup)

    def summary(self, var_names: Sequence[str] | None = None) -> list[dict[str, Any]]:
        """Stan/ArviZ-style per-parameter rows from ``owalnuts::diagnostics``.

        Each row is a dict with ``name``, ``mean``, ``sd``, ``mcse_mean``,
        ``q5``, ``q50``, ``q95``, ``ess_bulk``, ``ess_tail`` and ``rhat``
        (rank-normalised folded split R-hat and bulk/tail ESS after Vehtari
        et al. 2021, matching ``az.rhat``/``az.ess``/``az.mcse``). Pure
        Python objects; no pandas.
        """
        return summary(self.samples, var_names)

    def health(self) -> dict[str, Any]:
        """Pooled sampler-health counts over the retained transitions:
        ``transitions``, ``divergences``, ``maximum_depth_stops``,
        ``refinement_exhaustion_stops``, ``invalid_evaluation_stops``,
        ``zero_density_evaluations``, ``target_calls``, ``mean_tree_depth``
        and ``step_size`` (mean over chains)."""
        n = int(self.config.get("warmup", 0))
        work = [c["work_retained"] for c in self.chains]
        depth = np.concatenate([np.asarray(c["depth"])[n:] for c in self.chains])
        return {
            "transitions": int(sum(w["transitions"] for w in work)),
            "divergences": int(sum(w["divergences"] for w in work)),
            "maximum_depth_stops": int(sum(w["maximum_depth_stops"] for w in work)),
            "refinement_exhaustion_stops": int(sum(w["refinement_exhaustion_stops"] for w in work)),
            "invalid_evaluation_stops": int(sum(w["invalid_evaluation_stops"] for w in work)),
            "zero_density_evaluations": int(sum(w["zero_density_evaluations"] for w in work)),
            "target_calls": int(sum(w["target_calls_total"] for w in work)),
            "mean_tree_depth": float(depth.mean()) if depth.size else float("nan"),
            "step_size": float(self.final_step_size.mean()),
        }


# ── Core entry points ────────────────────────────────────────────────────


def _config_dict(
    *,
    warmup: int,
    draws: int,
    seed: int,
    threads: int,
    tuning: Tuning,
    adaptation: Adaptation | None,
    mass: Any,
    max_target_evaluations: int | None,
    max_depth_stop_limit: int | None,
    admit_worst_case: bool = True,
) -> dict[str, Any]:
    cfg: dict[str, Any] = {
        "warmup": int(warmup),
        "draws": int(draws),
        "seed": int(seed),
        "threads": int(threads),
        "step_size": float(tuning.step_size),
        "max_depth": int(tuning.max_depth),
        "min_micro_steps": int(tuning.min_micro_steps),
        "max_refinement_levels": int(tuning.max_refinement_levels),
        "max_error": float(tuning.max_error),
        "divergence_threshold": float(tuning.divergence_threshold),
        "mass": _normalize_mass(mass),
        "max_target_evaluations": max_target_evaluations,
        "max_depth_stop_limit": max_depth_stop_limit,
        "admit_worst_case": bool(admit_worst_case),
    }
    if adaptation is None:
        cfg["adapt"] = False
    else:
        cfg["adapt"] = True
        cfg["target_accept"] = float(adaptation.target_accept)
        cfg["adapt_step_size"] = bool(adaptation.adapt_step_size)
        cfg["adapt_mass"] = bool(adaptation.adapt_mass)
        cfg["paper_adaptation"] = adaptation.paper.to_dict() if adaptation.paper else None
    return cfg


def _normalize_mass(mass: Any) -> Any:
    if mass is None:
        return None
    if isinstance(mass, np.ndarray):
        return np.ascontiguousarray(mass, dtype=np.float64)
    if isinstance(mass, (list, tuple)):
        blocks = []
        for block in mass:
            block = dict(block)
            for key in ("diagonal", "subdiagonal", "scale"):
                if key in block:
                    block[key] = np.ascontiguousarray(block[key], dtype=np.float64)
            blocks.append(block)
        return blocks
    raise TypeError("mass must be None, a 1-D float64 array (momentum covariance diagonal), or a list of block dicts")


def _starts(init: Any, dim: int, chains: int, seed: int, jitter: float) -> np.ndarray:
    if isinstance(init, str):
        raise ValueError(f"init={init!r}: only init='uniform' is a named start rule")
    if init is None:
        rng = np.random.default_rng(seed)
        starts = rng.uniform(-jitter, jitter, size=(chains, dim))
    else:
        starts = np.asarray(init, dtype=np.float64)
        if starts.ndim == 1:
            rng = np.random.default_rng(seed)
            starts = starts[None, :] + rng.uniform(-jitter, jitter, size=(chains, dim))
    starts = np.ascontiguousarray(starts, dtype=np.float64)
    if starts.shape != (chains, dim):
        raise ValueError(f"init must have shape ({chains}, {dim}); got {starts.shape}")
    return starts


@dataclass(frozen=True)
class CFuncTarget:
    """A compiled C-ABI target: GIL-free, so ``threads > 1`` really parallelises.

    ``address`` is a function with the exact ABI
    ``float64(intp dim, const double* q, double* grad_out, void* user_data)``
    (numba signature string in ``RAW_CFUNC_SIGNATURE``). ``keep_alive`` holds
    the compiled object (and any arrays it closes over) for the target's life.
    """

    address: int
    dim: int
    user_data: int = 0
    parameter_names: tuple[str, ...] | None = None
    keep_alive: Any = None


def numba_raw_signature():
    """The numba signature object matching ``RAW_CFUNC_SIGNATURE``."""
    from numba import types

    return types.float64(
        types.intp,
        types.CPointer(types.float64),
        types.CPointer(types.float64),
        types.voidptr,
    )


def from_cfunc(
    cfunc_or_address: Any,
    dim: int,
    *,
    user_data: int = 0,
    parameter_names: Sequence[str] | None = None,
) -> CFuncTarget:
    """Wrap a numba/Cython ``cfunc`` (or a raw address) as a GIL-free target.

    The callback must be thread-safe, reentrant, deterministic, write every
    gradient element on finite returns, return ``-inf`` for zero-density
    points (refined, then zero weight), and never raise across the ABI.
    """
    address = getattr(cfunc_or_address, "address", cfunc_or_address)
    return CFuncTarget(
        address=int(address),
        dim=int(dim),
        user_data=int(user_data),
        parameter_names=tuple(parameter_names) if parameter_names else None,
        keep_alive=cfunc_or_address,
    )


def wrap_callable(fn: LogpGrad) -> LogpGrad:
    """Coerce a target's outputs to ``(float, contiguous float64 array)``."""

    def target(q: np.ndarray) -> tuple[float, np.ndarray]:
        value, grad = fn(q)
        return float(value), np.ascontiguousarray(grad, dtype=np.float64).reshape(-1)

    return target


def sample(
    logp_and_grad: LogpGrad,
    dim: int,
    *,
    init: Any = None,
    chains: int = 4,
    warmup: int = 1000,
    draws: int = 1000,
    seed: int = 0,
    threads: int = 1,
    tuning: Tuning = Tuning(),
    adaptation: Adaptation | None = Adaptation(),
    mass: Any = None,
    nonfinite: str = "zero_density",
    max_target_evaluations: int | None = None,
    max_depth_stop_limit: int | None = None,
    admit_worst_case: bool = True,
    init_jitter: float = 2.0,
    init_radius: float = 2.0,
    init_max_attempts: int = 100,
    coerce: bool = True,
    refresh: Callable[..., Any] | None = None,
    refresh_restart: str = "continue",
) -> SampleResult:
    """Sample ``logp_and_grad`` with oWALNUTS.

    ``init`` is ``None`` (independent uniform(-``init_jitter``, ``init_jitter``)
    starts drawn in numpy without evaluating the target), a ``(dim,)`` point
    (jittered per chain), a ``(chains, dim)`` array, or ``"uniform"``: Stan's
    rule as implemented by ``owalnuts::sampler::Init::uniform`` — uniform
    (-``init_radius``, ``init_radius``) starts redrawn up to
    ``init_max_attempts`` times per chain until the log density and gradient
    are finite, deterministic given ``seed`` and identical to the Rust
    sampler's starts for the same seed.

    ``mass`` is the momentum covariance: ``None`` (identity), a 1-D array
    (diagonal), or a list of structured blocks such as
    ``tridiagonal_precision_mass(...)``. Diagonal mass adaptation is disabled
    automatically for structured masses (the facade does not adapt them).

    ``refresh`` (structured mass + callable transport only) is called at every
    slow-window boundary as ``refresh(window_index, transition, sample_count,
    mean, variance)`` and returns ``None`` to keep the current metric or a
    list of mass blocks to install (same schema as ``mass``). Raising keeps
    the previous metric (typed ``RefreshFailed`` fallback in the facade).
    ``refresh_restart`` is ``"continue"`` (default) or ``"restart"`` for the
    dual-averaging state at installs.

    ``max_target_evaluations`` is an exact ceiling on started target
    evaluations across all chains (the run is also admitted against it).
    Without one, ``admit_worst_case=True`` (the default, mirroring the Rust
    ``Limits::admit_worst_case``) admits a run whose exact worst-case
    evaluation count exceeds the conservative default preflight ceiling —
    which the sampler defaults (depth 10, eight refinement levels) do at four
    chains of a few thousand transitions; ``admit_worst_case=False`` keeps
    the conservative ceiling and fails such runs at admission.
    """
    cfg = _config_dict(
        warmup=warmup, draws=draws, seed=seed, threads=threads, tuning=tuning,
        adaptation=adaptation, mass=mass, max_target_evaluations=max_target_evaluations,
        max_depth_stop_limit=max_depth_stop_limit, admit_worst_case=admit_worst_case,
    )
    if isinstance(logp_and_grad, CFuncTarget):
        if refresh is not None:
            raise ValueError(
                "refresh requires the callable transport; pass the plain "
                "logp_and_grad (e.g. from_pymc(model) without gil_free)"
            )
        cft = logp_and_grad
        if cft.dim != dim:
            raise ValueError(f"CFuncTarget dim {cft.dim} != sample dim {dim}")
        if isinstance(init, str) and init == "uniform":
            starts = _owalnuts.uniform_starts_cfunc(
                cft.address, cft.dim, chains, seed, init_radius, init_max_attempts, cft.user_data,
            )
        else:
            starts = _starts(init, dim, chains, seed, init_jitter)
        raw = _owalnuts.sample_cfunc(
            cft.address, cft.dim, starts, cfg, cft.user_data,
            list(cft.parameter_names) if cft.parameter_names else None,
        )
        return _result(raw, cfg)
    target = wrap_callable(logp_and_grad) if coerce else logp_and_grad
    if isinstance(init, str) and init == "uniform":
        starts = _owalnuts.uniform_starts_callable(
            target, dim, chains, seed, init_radius, init_max_attempts, nonfinite,
        )
    else:
        starts = _starts(init, dim, chains, seed, init_jitter)
    raw = _owalnuts.sample_callable(target, starts, cfg, nonfinite, refresh, refresh_restart)
    return _result(raw, cfg)


def preflight(
    dim: int,
    *,
    chains: int = 4,
    warmup: int = 1000,
    draws: int = 1000,
    seed: int = 0,
    threads: int = 1,
    tuning: Tuning = Tuning(),
    adaptation: Adaptation | None = Adaptation(),
    mass: Any = None,
    max_target_evaluations: int | None = None,
    admit_worst_case: bool = True,
) -> dict[str, int]:
    """Zero-callback admission check: worst-case target evaluations vs ceiling."""
    starts = np.zeros((chains, dim))
    cfg = _config_dict(
        warmup=warmup, draws=draws, seed=seed, threads=threads, tuning=tuning,
        adaptation=adaptation, mass=mass, max_target_evaluations=max_target_evaluations,
        max_depth_stop_limit=None, admit_worst_case=admit_worst_case,
    )
    return dict(_owalnuts.preflight_callable(starts, cfg))


def _result(raw: dict[str, Any], cfg: dict[str, Any]) -> SampleResult:
    return SampleResult(
        samples=np.asarray(raw["samples"]),
        chains=list(raw["chains"]),
        algorithm_revision=raw["algorithm_revision"],
        wall_seconds=float(raw["wall_seconds"]),
        target_calls=int(raw["target_calls"]),
        target_recoverable_failures=int(raw["target_recoverable_failures"]),
        target_attached_seconds=float(raw["target_attached_seconds"]),
        config=cfg,
        refresh_updates=raw.get("refresh_updates"),
    )


# ── Diagnostics ──────────────────────────────────────────────────────────


def summary(samples: np.ndarray, var_names: Sequence[str] | None = None) -> list[dict[str, Any]]:
    """Per-parameter summary rows for a ``(chains, draws, dim)`` array of
    retained draws, computed by ``owalnuts::diagnostics`` (see
    ``SampleResult.summary``). Default names are ``theta.1 .. theta.d``."""
    samples = np.ascontiguousarray(samples, dtype=np.float64)
    if samples.ndim != 3:
        raise ValueError(f"samples must be (chains, draws, dim); got shape {samples.shape}")
    names = [str(n) for n in var_names] if var_names is not None else None
    return list(_owalnuts.summary(samples, names))


def uniform_starts(logp_and_grad: LogpGrad, dim: int, *, chains: int = 4, seed: int = 0,
                   radius: float = 2.0, max_attempts: int = 100, nonfinite: str = "zero_density",
                   coerce: bool = True) -> np.ndarray:
    """Draw ``(chains, dim)`` starts by the ``init="uniform"`` rule without sampling."""
    if isinstance(logp_and_grad, CFuncTarget):
        return np.asarray(_owalnuts.uniform_starts_cfunc(
            logp_and_grad.address, logp_and_grad.dim, chains, seed, radius, max_attempts,
            logp_and_grad.user_data))
    target = wrap_callable(logp_and_grad) if coerce else logp_and_grad
    return np.asarray(_owalnuts.uniform_starts_callable(target, dim, chains, seed, radius, max_attempts, nonfinite))


# ── Structured metrics ───────────────────────────────────────────────────


def tridiagonal_cholesky(diag: np.ndarray, off: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Lower-bidiagonal Cholesky factor ``L`` of a symmetric positive-definite
    tridiagonal matrix with main diagonal ``diag`` and sub-diagonal ``off``."""
    diag = np.asarray(diag, dtype=np.float64)
    off = np.asarray(off, dtype=np.float64)
    n = diag.shape[0]
    if off.shape[0] != n - 1:
        raise ValueError("off must have length len(diag) - 1")
    l_diag = np.empty(n)
    l_sub = np.empty(max(n - 1, 0))
    l_diag[0] = np.sqrt(diag[0])
    for i in range(1, n):
        l_sub[i - 1] = off[i - 1] / l_diag[i - 1]
        v = diag[i] - l_sub[i - 1] ** 2
        if not v > 0:
            raise ValueError("matrix is not positive definite")
        l_diag[i] = np.sqrt(v)
    return l_diag, l_sub


def tridiagonal_precision_mass(diag: np.ndarray, off: np.ndarray) -> list[dict[str, Any]]:
    """Momentum covariance ``M = H`` for a tridiagonal target precision ``H``
    (the whitening metric for a Gaussian path block), as a structured block."""
    l_diag, l_sub = tridiagonal_cholesky(diag, off)
    return [{"type": "bidiagonal_cholesky", "diagonal": l_diag, "subdiagonal": l_sub}]


def diagonal_block(diagonal: np.ndarray) -> dict[str, Any]:
    return {"type": "diagonal", "diagonal": np.asarray(diagonal, dtype=np.float64)}


# ── Adapters ─────────────────────────────────────────────────────────────


def from_numpy(logp: Callable[[np.ndarray], float], grad: Callable[[np.ndarray], np.ndarray]) -> LogpGrad:
    def target(q: np.ndarray) -> tuple[float, np.ndarray]:
        return float(logp(q)), np.asarray(grad(q), dtype=np.float64)

    return target


def from_jax(logp_fn: Callable[[Any], Any], *, jit: bool = True) -> LogpGrad:
    """Wrap a JAX scalar log density. Enables x64 (the kernel is binary64)."""
    import jax
    import jax.numpy as jnp

    jax.config.update("jax_enable_x64", True)
    vg = jax.value_and_grad(logp_fn)
    if jit:
        vg = jax.jit(vg)

    def target(q: np.ndarray) -> tuple[float, np.ndarray]:
        value, grad = vg(jnp.asarray(q))
        return float(value), np.asarray(grad, dtype=np.float64)

    return target


def from_torch(logp_fn: Callable[[Any], Any], *, device: str = "cpu") -> LogpGrad:
    """Wrap a PyTorch scalar log density taking a float64 tensor."""
    import torch

    def target(q: np.ndarray) -> tuple[float, np.ndarray]:
        x = torch.from_numpy(np.array(q, dtype=np.float64)).to(device).requires_grad_(True)
        value = logp_fn(x)
        (grad,) = torch.autograd.grad(value, x)
        return float(value.detach().cpu().item()), grad.detach().cpu().numpy().astype(np.float64)

    return target


def _pymc_layout(model) -> tuple[np.ndarray, int, list[str], Callable[[np.ndarray], dict[str, np.ndarray]]]:
    initial = model.initial_point()
    names: list[str] = []
    sizes: list[int] = []
    flat_parts = []
    for rv in model.value_vars:
        value = np.asarray(initial[rv.name], dtype=np.float64)
        names.append(rv.name)
        sizes.append(int(value.size))
        flat_parts.append(value.ravel())
    q0 = np.concatenate(flat_parts) if flat_parts else np.zeros(0)
    offsets = np.cumsum([0, *sizes])

    def unravel(q: np.ndarray) -> dict[str, np.ndarray]:
        return {name: q[..., offsets[i]:offsets[i + 1]] for i, name in enumerate(names)}

    return q0, int(q0.size), names, unravel


def _from_pymc_gil_free(model) -> tuple[CFuncTarget, int, np.ndarray, list[str], Callable[[np.ndarray], dict[str, np.ndarray]]]:
    """nutpie-style transport: PyMC's numba-compiled joint logp/grad wrapped
    in a ``numba.cfunc`` with the RawTarget ABI, verified against the ordinary
    compiled function before use. Shared-variable values are snapshotted at
    compile time. Raises ``NotImplementedError`` when the PyTensor numba
    backend cannot supply a wrappable jit function.
    """
    import ctypes

    import numba

    fn = model.logp_dlogp_function(ravel_inputs=True, mode="NUMBA")
    fn.set_extra_values({})
    q0, dim, names, unravel = _pymc_layout(model)
    inner = getattr(getattr(fn._pytensor_function, "vm", None), "jit_fn", None)
    if inner is None:
        raise NotImplementedError(
            "PyTensor NUMBA mode did not expose vm.jit_fn; use gil_free=False"
        )
    n = dim
    sig = numba_raw_signature()

    def build(extract):
        @numba.cfunc(sig, nopython=True)
        def raw(dim_, x_ptr, grad_ptr, _user):
            x = numba.carray(x_ptr, (n,))
            logp, grad = inner(x)
            g = numba.carray(grad_ptr, (n,))
            for i in range(n):
                g[i] = grad[i]
            return extract(logp)

        return raw

    errors: list[str] = []
    raw = None
    for extract in (
        numba.njit(lambda v: v.sum()),  # 0-d / 1-element array log density
        numba.njit(lambda v: v),  # scalar log density
    ):
        try:
            raw = build(extract)
            break
        except Exception as error:  # noqa: BLE001 - report all attempts
            errors.append(f"{type(error).__name__}: {error}")
    if raw is None:
        raise NotImplementedError(
            "could not wrap the PyTensor numba function as a cfunc: "
            + " | ".join(errors)
        )

    # Verify once through ctypes against the ordinary compiled path.
    proto = ctypes.CFUNCTYPE(
        ctypes.c_double,
        ctypes.c_ssize_t,
        ctypes.POINTER(ctypes.c_double),
        ctypes.POINTER(ctypes.c_double),
        ctypes.c_void_p,
    )
    caller = proto(raw.address)
    probe = np.ascontiguousarray(q0, dtype=np.float64)
    grad_out = np.zeros(dim, dtype=np.float64)
    value = caller(
        dim,
        probe.ctypes.data_as(ctypes.POINTER(ctypes.c_double)),
        grad_out.ctypes.data_as(ctypes.POINTER(ctypes.c_double)),
        None,
    )
    ref_value, ref_grad = fn(probe)
    if not (
        np.isfinite(value)
        and abs(value - float(ref_value)) <= 1e-8 * (1.0 + abs(float(ref_value)))
        and np.allclose(grad_out, np.asarray(ref_grad, dtype=np.float64), rtol=1e-8, atol=1e-10)
    ):
        raise NotImplementedError(
            "cfunc wrapper disagreed with the compiled PyMC function; use gil_free=False"
        )

    target = CFuncTarget(
        address=int(raw.address),
        dim=dim,
        user_data=0,
        parameter_names=None,
        keep_alive=(raw, inner, fn),
    )
    return target, dim, q0, names, unravel


def from_pymc(model: Any, *, mode: str | None = None, gil_free: bool = False,
              thread_safe: bool = False) -> tuple[LogpGrad, int, np.ndarray, list[str], Callable[[np.ndarray], dict[str, np.ndarray]]]:
    """Wrap a PyMC model's compiled joint log density and gradient over the
    raveled unconstrained (transformed) variables.

    Returns ``(target, dim, initial_point, var_names, unravel)`` where
    ``unravel`` maps a raveled draw back to a dict of transformed values.

    A compiled PyTensor function reuses internal storage and is NOT safe to
    call from concurrent sampler threads. ``thread_safe=True`` lazily compiles
    one function per calling thread (a small one-time cost per thread), which
    restores ``threads > 1`` sampling on the callable transport. The default
    single-function wrapper is only safe with ``threads=1``.
    """
    import pymc as pm  # noqa: F401

    if gil_free:
        return _from_pymc_gil_free(model)

    q0, dim, names, unravel = _pymc_layout(model)

    if thread_safe:
        import threading

        local = threading.local()
        compile_lock = threading.Lock()

        def _fn():
            fn = getattr(local, "fn", None)
            if fn is None:
                # PyTensor compilation itself is not reentrant; serialize it.
                with compile_lock:
                    fn = model.logp_dlogp_function(ravel_inputs=True, mode=mode)
                    fn.set_extra_values({})
                local.fn = fn
            return fn

        def target(q: np.ndarray) -> tuple[float, np.ndarray]:
            logp, grad = _fn()(np.asarray(q, dtype=np.float64))
            return float(logp), np.asarray(grad, dtype=np.float64)

        return target, dim, q0, names, unravel

    fn = model.logp_dlogp_function(ravel_inputs=True, mode=mode)
    fn.set_extra_values({})

    def target(q: np.ndarray) -> tuple[float, np.ndarray]:
        logp, grad = fn(np.asarray(q, dtype=np.float64))
        return float(logp), np.asarray(grad, dtype=np.float64)

    return target, dim, q0, names, unravel


# ── ArviZ ────────────────────────────────────────────────────────────────


def to_inferencedata(result: SampleResult, var_names: Sequence[str] | None = None, warmup: int | None = None):
    """Build an ``arviz.InferenceData`` with ``posterior`` and ``sample_stats``.

    ``sample_stats`` carries ``tree_depth``, ``diverging``, ``n_steps`` (fused
    target calls), ``energy_error``, ``stop_reason`` (code, see ``STOP_CODES``),
    ``refinement_level`` and ``zero_density_evaluations`` for retained draws.
    """
    import arviz as az

    chains, draws, dim = result.samples.shape
    if var_names is None:
        var_names = [f"q{i}" for i in range(dim)]
    posterior = {name: result.samples[:, :, i] for i, name in enumerate(var_names)} if len(var_names) == dim else {
        "q": result.samples
    }
    n_discarded = int(result.config.get("warmup", 0)) if warmup is None else int(warmup)

    def retained(key: str) -> np.ndarray:
        return np.stack([np.asarray(c[key])[n_discarded:] for c in result.chains])

    stats = {
        "tree_depth": retained("depth").astype(np.int64),
        "diverging": retained("divergent").astype(bool),
        "n_steps": retained("target_evaluations").astype(np.int64),
        "energy_error": retained("max_abs_energy_error"),
        "stop_reason": retained("stop").astype(np.int64),
        "refinement_level": retained("selected_refinement_level").astype(np.int64),
        "zero_density_evaluations": retained("zero_density_evaluations").astype(np.int64),
    }
    dims = {"q": ["q_dim"]} if "q" in posterior else None
    idata = az.from_dict(posterior=posterior, sample_stats=stats, dims=dims,
                         attrs={"algorithm_revision": result.algorithm_revision,
                                "sampler": "owalnuts", "wall_seconds": result.wall_seconds,
                                "target_calls": result.target_calls})
    return idata


# ── Built-in native targets (for benchmarking against hand-written Rust) ─


def sample_native_eight_schools(y: np.ndarray, se: np.ndarray, *, init: Any, chains: int = 4, warmup: int = 1000,
                                draws: int = 1000, seed: int = 0, threads: int = 1, tuning: Tuning = Tuning(),
                                adaptation: Adaptation | None = Adaptation(), mass: Any = None,
                                max_target_evaluations: int | None = None) -> SampleResult:
    y = np.ascontiguousarray(y, dtype=np.float64)
    se = np.ascontiguousarray(se, dtype=np.float64)
    dim = 2 + y.size
    starts = _starts(init, dim, chains, seed, 0.0)
    cfg = _config_dict(warmup=warmup, draws=draws, seed=seed, threads=threads, tuning=tuning, adaptation=adaptation,
                       mass=mass, max_target_evaluations=max_target_evaluations, max_depth_stop_limit=None)
    return _result(_owalnuts.sample_eight_schools(y, se, starts, cfg), cfg)


def sample_native_local_level(y: np.ndarray, r: np.ndarray, *, init: Any, chains: int = 4, warmup: int = 500,
                              draws: int = 2000, seed: int = 0, threads: int = 1, tuning: Tuning = Tuning(),
                              adaptation: Adaptation | None = Adaptation(), mass: Any = None,
                              m0: float = 0.0, tau0: float = 1.0, mu: float = 0.01, sigma_x: float = 0.08,
                              max_target_evaluations: int | None = None) -> SampleResult:
    y = np.ascontiguousarray(y, dtype=np.float64)
    r = np.ascontiguousarray(r, dtype=np.float64)
    dim = y.size
    starts = _starts(init, dim, chains, seed, 0.0)
    cfg = _config_dict(warmup=warmup, draws=draws, seed=seed, threads=threads, tuning=tuning, adaptation=adaptation,
                       mass=mass, max_target_evaluations=max_target_evaluations, max_depth_stop_limit=None)
    return _result(_owalnuts.sample_local_level(y, r, starts, cfg, m0, tau0, mu, sigma_x), cfg)


def eight_schools_logp_grad(y: np.ndarray, se: np.ndarray, q: np.ndarray) -> tuple[float, np.ndarray]:
    return _owalnuts.eight_schools_logp_grad(np.ascontiguousarray(y, dtype=np.float64),
                                              np.ascontiguousarray(se, dtype=np.float64),
                                              np.ascontiguousarray(q, dtype=np.float64))


__all__ = [
    "ALGORITHM_REVISION", "PAPER_ADAPTATION_REVISION", "STOP_CODES", "ZeroDensityError",
    "PaperAdaptation", "Tuning", "Adaptation", "SampleResult", "sample", "preflight",
    "summary", "uniform_starts", "CFuncTarget", "from_cfunc", "numba_raw_signature",
    "tridiagonal_cholesky", "tridiagonal_precision_mass", "diagonal_block",
    "from_numpy", "from_jax", "from_torch", "from_pymc", "to_inferencedata", "wrap_callable",
    "sample_native_eight_schools", "sample_native_local_level", "eight_schools_logp_grad",
]
