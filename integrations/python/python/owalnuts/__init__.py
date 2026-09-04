"""oWALNUTS for Python: within-orbit adaptive leapfrog NUTS on any differentiable target.

The lowest common denominator is a callable ``f(q) -> (log_density, gradient)``
taking and returning ``float64`` numpy arrays. Adapters wrap JAX, PyTorch and
PyMC models into that shape. Every run builds an ``owalnuts::sampler::Sampler``
in Rust, so the defaults are the sampler's (``DEFAULTS``); this module only
marshals arrays and configuration.
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from types import MappingProxyType
from typing import Any, Callable, Mapping, Sequence

import numpy as np

from . import _owalnuts

try:  # the installed distribution's version; the source tree has none
    from importlib.metadata import version as _dist_version

    __version__ = _dist_version("owalnuts")
except Exception:  # pragma: no cover - source checkout without metadata
    __version__ = "0.2.0"

ALGORITHM_REVISION: str = _owalnuts.ALGORITHM_REVISION
PAPER_ADAPTATION_REVISION: str = _owalnuts.PAPER_ADAPTATION_REVISION
STOP_CODES: tuple[str, ...] = tuple(_owalnuts.STOP_CODES)
#: Whether the extension was built with BridgeStan support. On Windows 0.2,
#: ``from_stan`` remains disabled even when this is true.
HAS_STAN: bool = bool(getattr(_owalnuts, "HAS_STAN", False))

#: The ``owalnuts::sampler`` defaults this package inherits, read from the
#: Rust constants at import time (read-only): ``step_size``, ``max_depth``,
#: ``min_micro_steps``, ``max_refinement_levels``, ``max_error``,
#: ``divergence_threshold``, ``u_turn_rule`` (``DEFAULT_U_TURN_RULE``),
#: ``exhaustion_rule`` (retained transitions), ``warmup_exhaustion_rule``
#: (``DEFAULT_WARMUP_EXHAUSTION``), ``metric_regularization``
#: (``DEFAULT_METRIC_REGULARIZATION``), ``target_accept``, ``adapt_mass``,
#: ``init_radius``, ``init_max_attempts``, ``cache_initial_evaluation``,
#: ``admit_worst_case``, ``chain_rescue`` (``None`` after WP36),
#: ``algorithm_revision`` and
#: ``paper_adaptation_revision``. ``Tuning()`` and ``Adaptation()`` take
#: their defaults from here, and ``sample`` sends only what you set, so a
#: Rust default change reaches the package without any edit here.
DEFAULTS: Mapping[str, Any] = MappingProxyType(dict(_owalnuts.DEFAULTS))

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
    the local energy-error threshold ``delta``. The defaults are
    ``owalnuts::sampler::Tuning::default()`` read from ``DEFAULTS`` (``h =
    0.5``, depth 10, eight refinement levels, ``delta = 1``, the momentum-sum
    U-turn rule); the 0.1 package used ``h = 0.1`` and depth 8.

    ``u_turn_rule`` (``"endpoints"`` | ``"endpoints_with_cross"`` |
    ``"momentum_sum"``) and ``exhaustion_rule`` (``"stop"`` |
    ``"accept_below_divergence_threshold"`` | ``"accept_unless_divergent"``)
    override the kernel options of the retained transitions
    (``Tuning::kernel_options``); ``None`` keeps the sampler default
    (``DEFAULTS["u_turn_rule"]``, ``DEFAULTS["exhaustion_rule"]``). The
    frozen ``v10`` kernel is ``u_turn_rule="endpoints"``."""

    step_size: float = DEFAULTS["step_size"]
    max_depth: int = DEFAULTS["max_depth"]
    min_micro_steps: int = DEFAULTS["min_micro_steps"]
    max_refinement_levels: int = DEFAULTS["max_refinement_levels"]
    max_error: float = DEFAULTS["max_error"]
    divergence_threshold: float = DEFAULTS["divergence_threshold"]
    u_turn_rule: str | None = None
    exhaustion_rule: str | None = None


@dataclass(frozen=True)
class Adaptation:
    """Warmup adaptation during the discarded transitions: the sampler's
    ``Adaptation::DualAveraging`` (or ``Adaptation::Paper`` with ``paper``),
    which applies ``DEFAULT_WARMUP_EXHAUSTION`` and
    ``DEFAULT_METRIC_REGULARIZATION`` (``DEFAULTS["warmup_exhaustion_rule"]``,
    ``DEFAULTS["metric_regularization"]``). ``metric_regularization``
    (``"stan"`` | ``"toward_unit"``) overrides the diagonal-metric prior;
    ``adapt_step_size=False`` and an override are expressed through
    ``Adaptation::Custom`` with the same warmup exhaustion rule."""

    target_accept: float = DEFAULTS["target_accept"]
    adapt_step_size: bool = True
    adapt_mass: bool = DEFAULTS["adapt_mass"]
    paper: PaperAdaptation | None = None
    metric_regularization: str | None = None


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
    compiled_threading: str | None = None
    #: Effective metadata from the target actually used for this sample run.
    threading: str | None = None
    target_execution: str | None = None
    requested_replicas: int | None = None
    effective_replicas: int | None = None
    #: Unconstrained parameter names when the target provides them (Stan,
    #: ``from_cfunc(parameter_names=...)``); the default labels for
    #: ``summary`` and ``to_inferencedata``.
    parameter_names: list[str] | None = None

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
        return summary(self.samples, self.parameter_names if var_names is None else var_names)

    def summary_table(self, var_names: Sequence[str] | None = None) -> str:
        """``summary()`` rendered as a fixed-width, Stan-style text table
        followed by one line of pooled health; what ``print(result)`` shows."""
        return format_summary(self.summary(var_names), self.health(), self.wall_seconds)

    def __str__(self) -> str:
        return self.summary_table()

    def __repr__(self) -> str:
        chains, draws, dim = self.samples.shape
        return f"SampleResult(chains={chains}, draws={draws}, dim={dim}, wall_seconds={self.wall_seconds:.3g})"

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
    cache_initial_evaluation: bool | None = None,
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
        "u_turn_rule": tuning.u_turn_rule,
        "exhaustion_rule": tuning.exhaustion_rule,
        "mass": _normalize_mass(mass),
        "max_target_evaluations": max_target_evaluations,
        "max_depth_stop_limit": max_depth_stop_limit,
        "admit_worst_case": bool(admit_worst_case),
        "cache_initial_evaluation": cache_initial_evaluation,
    }
    if adaptation is None:
        cfg["adapt"] = False
    else:
        cfg["adapt"] = True
        cfg["target_accept"] = float(adaptation.target_accept)
        cfg["adapt_step_size"] = bool(adaptation.adapt_step_size)
        cfg["adapt_mass"] = bool(adaptation.adapt_mass)
        cfg["paper_adaptation"] = adaptation.paper.to_dict() if adaptation.paper else None
        cfg["metric_regularization"] = adaptation.metric_regularization
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


# ── Stan models (BridgeStan) ─────────────────────────────────────────────

_WINDOWS_STAN_UNSUPPORTED = (
    "owalnuts 0.2 disables Python from_stan and direct bridgestan.StanModel "
    "operations on Windows because those Python-native calls bypass the Rust "
    "owned-worker lifetime backend; use owalnuts-bridgestan from Rust, or run "
    "the Python Stan integration on Linux/macOS"
)


def _require_python_stan_supported() -> None:
    if sys.platform == "win32":
        raise RuntimeError(_WINDOWS_STAN_UNSUPPORTED)


@dataclass(frozen=True)
class StanTarget:
    """A BridgeStan-compiled Stan model as a GIL-free oWALNUTS target.

    ``sample`` loads ``model_so`` through the Rust
    ``owalnuts_bridgestan::ReplicatedStanTarget`` and evaluates it with the
    interpreter detached. Off Windows, independent snapshotted replicas give
    parallel chains for a model built without ``STAN_THREADS``.
    Positions are Stan's unconstrained parameters (``bs_param_unc_names``);
    the log density is ``propto=False, jacobian=True``; a Stan exception or a
    nonfinite value is a zero-density (refined, then rejected) proposal.

    Off Windows the object is also a plain ``logp_and_grad`` callable through
    the ``bridgestan`` Python package, and ``constrain`` maps draws back to
    constrained parameters. owalnuts 0.2 disables those direct Python-native
    paths and ``from_stan`` on Windows because they bypass the Rust owned
    worker. ``probe_*`` fields describe only the one-replica Rust load used to
    discover model metadata. They do not predict a later ``sample`` call;
    ``SampleResult`` reports that run's actual requested/effective execution.
    """

    model_so: str
    data: str | None
    dim: int
    parameter_names: tuple[str, ...] | None
    seed: int = 1
    preload: tuple[str, ...] = ()
    info: str = ""
    compiled_threading: str = ""
    probe_threading: str = ""
    probe_execution: str = ""
    probe_requested_replicas: int = 1
    probe_effective_replicas: int = 1
    _cache: dict = field(default_factory=dict, repr=False, compare=False)

    def model(self):
        """The ``bridgestan.StanModel`` for this library and data (lazy)."""
        _require_python_stan_supported()
        if "model" not in self._cache:
            import bridgestan as bs

            self._cache["model"] = bs.StanModel(self.model_so, data=self.data, seed=int(self.seed))
        return self._cache["model"]

    def __call__(self, q: np.ndarray) -> tuple[float, np.ndarray]:
        value, grad = self.model().log_density_gradient(np.ascontiguousarray(q, dtype=np.float64),
                                                        propto=False, jacobian=True)
        return float(value), np.asarray(grad, dtype=np.float64)

    def constrained_names(self, *, include_tp: bool = False, include_gq: bool = False) -> list[str]:
        """Names of the constrained parameters (``bs_param_names``)."""
        return list(self.model().param_names(include_tp=include_tp, include_gq=include_gq))

    def constrain(self, draws: "np.ndarray | SampleResult", *, include_tp: bool = False,
                  include_gq: bool = False) -> np.ndarray:
        """Map unconstrained draws ``(..., dim)`` (or a ``SampleResult``) to the
        constrained parameters with ``bs_param_constrain``; returns
        ``(..., n_constrained)``. Generated quantities use the model's RNG."""
        samples = draws.samples if isinstance(draws, SampleResult) else np.asarray(draws, dtype=np.float64)
        model = self.model()
        flat = samples.reshape(-1, self.dim)
        out = np.empty((flat.shape[0], model.param_num(include_tp=include_tp, include_gq=include_gq)))
        rng = model.new_rng(int(self.seed)) if include_gq else None
        for i, q in enumerate(flat):
            out[i] = model.param_constrain(np.ascontiguousarray(q), include_tp=include_tp,
                                           include_gq=include_gq, rng=rng)
        return out.reshape(samples.shape[:-1] + (out.shape[1],))


def _stan_data_json(data: Any) -> str | None:
    """CmdStan-JSON text from a dict (numpy arrays allowed), a ``.json`` path or a JSON string."""
    import json

    if data is None:
        return None
    if isinstance(data, (bytes, bytearray)):
        return bytes(data).decode("utf-8")
    if isinstance(data, os.PathLike) or (isinstance(data, str) and data.strip().endswith(".json")):
        return Path(data).read_text(encoding="utf-8")
    if isinstance(data, str):
        return data

    def default(value: Any):
        if isinstance(value, np.ndarray):
            return value.tolist()
        if isinstance(value, np.generic):
            return value.item()
        raise TypeError(f"cannot encode {type(value).__name__} as Stan data")

    return json.dumps(dict(data), default=default)


def from_stan(stan_file: "str | os.PathLike[str]", data: Any = None, *, seed: int = 1,
              make_args: Sequence[str] = (), stanc_args: Sequence[str] = (),
              preload: Sequence[str] = ()) -> StanTarget:
    """Compile a Stan program with the ``bridgestan`` package and wrap it.

    Linux/macOS only in owalnuts 0.2. ``pip install owalnuts[stan]``;
    BridgeStan downloads its own Stan sources on first use and needs a C++17
    toolchain and GNU make. ``stan_file`` may also be an
    already built ``*_model.so``/``.dll``/``.dylib``. ``data`` is a dict
    (numpy arrays allowed), a ``.json`` path, JSON text, or ``None``.

    The library is built **without** ``STAN_THREADS`` unless ``make_args``
    says otherwise; independent non-Windows replicas provide parallel chains.
    ``seed`` is the Stan model seed (construction and generated quantities);
    the sampling seed is ``sample(seed=...)``.
    """
    _require_python_stan_supported()
    if not _owalnuts.HAS_STAN:
        raise RuntimeError("this owalnuts build was compiled without the `stan` feature")
    path = Path(stan_file)
    if path.suffix.lower() in {".so", ".dll", ".dylib"}:
        model_so = path
    else:
        import bridgestan as bs
        import bridgestan.compile as bs_compile

        # bridgestan reads MAKE once at import; honour a value set afterwards.
        bs_compile.MAKE = os.environ.get("MAKE", bs_compile.MAKE)
        model_so = Path(bs.compile_model(path, stanc_args=list(stanc_args), make_args=list(make_args)))
    data_json = _stan_data_json(data)
    info = _owalnuts.stan_model_info(str(model_so), data_json, int(seed), list(preload) or None)
    names = info["parameter_names"]
    return StanTarget(
        model_so=str(model_so), data=data_json, dim=int(info["dimension"]),
        parameter_names=tuple(names) if names else None, seed=int(seed),
        preload=tuple(preload), info=str(info["info"]),
        compiled_threading=str(info["compiled_threading"]),
        probe_threading=str(info["probe_threading"]),
        probe_execution=str(info["probe_execution"]),
        probe_requested_replicas=int(info["probe_requested_replicas"]),
        probe_effective_replicas=int(info["probe_effective_replicas"]),
    )


def wrap_callable(fn: LogpGrad) -> LogpGrad:
    """Coerce a target's outputs to ``(float, contiguous float64 array)``."""

    def target(q: np.ndarray) -> tuple[float, np.ndarray]:
        value, grad = fn(q)
        return float(value), np.ascontiguousarray(grad, dtype=np.float64).reshape(-1)

    return target


def sample(
    logp_and_grad: "LogpGrad | CFuncTarget | StanTarget",
    dim: int | None = None,
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
    init_radius: float = DEFAULTS["init_radius"],
    init_max_attempts: int = DEFAULTS["init_max_attempts"],
    coerce: bool = True,
    refresh: Callable[..., Any] | None = None,
    refresh_restart: str = "continue",
    cache_initial_evaluation: bool | None = None,
) -> SampleResult:
    """Sample ``logp_and_grad`` with oWALNUTS through ``owalnuts::sampler``.

    Every argument maps onto the Rust ``Sampler`` builder (``Tuning``,
    ``Adaptation``, ``Metric``, ``Limits``, ``Init``); anything not set here
    keeps the sampler default (``DEFAULTS``), including the cached initial
    evaluation (``cache_initial_evaluation=None``; pass ``False`` for the
    0.1 target-call accounting).

    ``logp_and_grad`` is a callable, a ``CFuncTarget`` (``from_cfunc``) or a
    ``StanTarget`` (``from_stan``); ``dim`` may be omitted for the latter two.

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
        cache_initial_evaluation=cache_initial_evaluation,
    )
    if isinstance(logp_and_grad, (CFuncTarget, StanTarget)):
        dim = logp_and_grad.dim if dim is None else int(dim)
    elif dim is None:
        raise ValueError("dim is required for a callable target")
    if isinstance(logp_and_grad, StanTarget):
        if refresh is not None:
            raise ValueError("refresh requires the callable transport; pass the StanTarget as a callable")
        st = logp_and_grad
        if st.dim != dim:
            raise ValueError(f"StanTarget dim {st.dim} != sample dim {dim}")
        preload = list(st.preload) or None
        if isinstance(init, str) and init == "uniform":
            starts = _owalnuts.uniform_starts_stan(
                st.model_so, st.data, chains, seed, init_radius, init_max_attempts, st.seed, preload,
            )
        else:
            starts = _starts(init, dim, chains, seed, init_jitter)
        raw = _owalnuts.sample_stan(st.model_so, st.data, starts, cfg, st.seed, preload)
        result = _result(raw, cfg)
        result.parameter_names = list(st.parameter_names) if st.parameter_names else None
        return result
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
        result = _result(raw, cfg)
        result.parameter_names = list(cft.parameter_names) if cft.parameter_names else None
        return result
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
        compiled_threading=raw.get("compiled_threading"),
        threading=raw.get("threading"),
        target_execution=raw.get("execution"),
        requested_replicas=raw.get("requested_replicas"),
        effective_replicas=raw.get("effective_replicas"),
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


def format_summary(rows: Sequence[Mapping[str, Any]], health: Mapping[str, Any] | None = None,
                   wall_seconds: float | None = None) -> str:
    """Render ``summary()`` rows as a fixed-width text table (plus an optional
    pooled-health line). Pure Python; no pandas."""
    columns = ["mean", "sd", "mcse_mean", "q5", "q50", "q95", "ess_bulk", "ess_tail", "rhat"]
    width = max([4] + [len(str(r["name"])) for r in rows])

    def cell(key: str, value: Any) -> str:
        if key in ("ess_bulk", "ess_tail"):
            return f"{value:9.0f}"
        if key == "rhat":
            return f"{value:7.3f}"
        return f"{value:10.3g}"

    header = f"{'name':<{width}} " + " ".join(
        f"{c:>9}" if c in ("ess_bulk", "ess_tail") else (f"{c:>7}" if c == "rhat" else f"{c:>10}") for c in columns)
    lines = [header]
    for r in rows:
        lines.append(f"{str(r['name']):<{width}} " + " ".join(cell(c, r[c]) for c in columns))
    if health is not None:
        extra = f", wall {wall_seconds:.2f}s" if wall_seconds is not None else ""
        lines.append(
            f"health: {health['divergences']} divergences, {health['maximum_depth_stops']} depth-cap stops, "
            f"{health['refinement_exhaustion_stops']} refinement exhaustions, mean depth {health['mean_tree_depth']:.2f}, "
            f"step {health['step_size']:.3g}, {health['target_calls']} target calls{extra}")
    return "\n".join(lines)


def uniform_starts(logp_and_grad: LogpGrad, dim: int, *, chains: int = 4, seed: int = 0,
                   radius: float = DEFAULTS["init_radius"], max_attempts: int = DEFAULTS["init_max_attempts"],
                   nonfinite: str = "zero_density",
                   coerce: bool = True) -> np.ndarray:
    """Draw ``(chains, dim)`` starts by the ``init="uniform"`` rule without sampling."""
    if isinstance(logp_and_grad, StanTarget):
        st = logp_and_grad
        return np.asarray(_owalnuts.uniform_starts_stan(
            st.model_so, st.data, chains, seed, radius, max_attempts, st.seed, list(st.preload) or None))
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
        var_names = result.parameter_names or [f"q{i}" for i in range(dim)]
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
    attrs = {"algorithm_revision": result.algorithm_revision,
             "sampler": "owalnuts", "wall_seconds": result.wall_seconds,
             "target_calls": result.target_calls}
    try:
        # ArviZ <= 0.22 returns InferenceData from group keyword arguments.
        idata = az.from_dict(posterior=posterior, sample_stats=stats, dims=dims, attrs=attrs)
    except TypeError as error:
        if "unexpected keyword argument 'posterior'" not in str(error):
            raise
        # ArviZ >= 1.0 accepts one nested group dictionary and returns DataTree.
        idata = az.from_dict(
            {"posterior": posterior, "sample_stats": stats},
            dims=dims,
            attrs={"/": attrs},
        )
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
    "ALGORITHM_REVISION", "PAPER_ADAPTATION_REVISION", "STOP_CODES", "DEFAULTS", "HAS_STAN", "ZeroDensityError",
    "PaperAdaptation", "Tuning", "Adaptation", "SampleResult", "sample", "preflight",
    "summary", "format_summary", "uniform_starts", "__version__", "CFuncTarget", "from_cfunc", "numba_raw_signature",
    "StanTarget", "from_stan",
    "tridiagonal_cholesky", "tridiagonal_precision_mass", "diagonal_block",
    "from_numpy", "from_jax", "from_torch", "from_pymc", "to_inferencedata", "wrap_callable",
    "sample_native_eight_schools", "sample_native_local_level", "eight_schools_logp_grad",
]
