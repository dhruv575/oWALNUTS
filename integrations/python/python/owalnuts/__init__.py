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
    __version__ = "0.3.0"

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
#: ``init`` (the default start rule, ``"best_of"`` = ``Init::default()``),
#: ``init_candidates``, ``init_radius``, ``init_max_attempts``, ``cache_initial_evaluation``,
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
    (``"stan"`` | ``"toward_unit"`` | ``"scale_free_median"`` |
    ``"scale_free_stan_median"``, the last two opt-in from WP41) overrides the
    diagonal-metric prior;
    ``adapt_step_size=False`` and an override are expressed through
    ``Adaptation::Custom`` with the same warmup exhaustion rule."""

    target_accept: float = DEFAULTS["target_accept"]
    adapt_step_size: bool = True
    adapt_mass: bool = DEFAULTS["adapt_mass"]
    paper: PaperAdaptation | None = None
    metric_regularization: str | None = None


@dataclass(frozen=True)
class WarmState:
    """Carried sampler state for a warm continuation (``sample_warm``): per
    chain, a position, a step size and a diagonal mass, all of one
    dimension (``owalnuts::sampler::WarmState`` in Rust).

    ``positions`` is ``(chains, dim)``, ``step_sizes`` is ``(chains,)`` and
    ``mass_diagonal`` is ``(chains, dim)``: the momentum covariance ``M`` in
    the library's convention (what ``chains[c]["metadata"]["mass_diagonal"]``
    reports and what ``sample(mass=...)`` takes; warmup sets it to a
    regularised reciprocal posterior variance). Obtain it from
    ``SampleResult.warm_state()`` or ``ContinuationChunk.warm_state()``; grow
    it onto a larger target with ``extend_to``.
    """

    positions: np.ndarray
    step_sizes: np.ndarray
    mass_diagonal: np.ndarray

    def __post_init__(self) -> None:
        positions = np.ascontiguousarray(self.positions, dtype=np.float64)
        step_sizes = np.ascontiguousarray(self.step_sizes, dtype=np.float64)
        mass = np.ascontiguousarray(self.mass_diagonal, dtype=np.float64)
        if positions.ndim != 2 or positions.shape[0] == 0 or positions.shape[1] == 0:
            raise ValueError("positions must be a nonempty (chains, dim) array")
        chains, dim = positions.shape
        if step_sizes.shape != (chains,):
            raise ValueError(f"step_sizes must have shape ({chains},); got {step_sizes.shape}")
        if mass.shape != (chains, dim):
            raise ValueError(f"mass_diagonal must have shape ({chains}, {dim}); got {mass.shape}")
        if not np.isfinite(positions).all():
            raise ValueError("positions must be finite")
        if not (np.isfinite(step_sizes).all() and (step_sizes > 0).all()):
            raise ValueError("step_sizes must be finite and positive")
        if not (np.isfinite(mass).all() and (mass > 0).all()):
            raise ValueError("mass_diagonal entries must be finite and positive")
        object.__setattr__(self, "positions", positions)
        object.__setattr__(self, "step_sizes", step_sizes)
        object.__setattr__(self, "mass_diagonal", mass)

    @property
    def chains(self) -> int:
        return int(self.positions.shape[0])

    @property
    def dim(self) -> int:
        return int(self.positions.shape[1])

    def extend_to(self, dim: int, position: float = 0.0, mass: float = 1.0) -> "WarmState":
        """Grow every chain to ``dim`` by appending coordinates at the end,
        each at ``position`` with mass ``mass`` (the WP84 rule for a new
        latent: its prior median 0 and prior variance 1). Step sizes are
        unchanged; ``dim`` must be at least the current dimension. Whether
        the fill is a sensible start is the caller's decision. A
        ``shift_window(0, dim - self.dim, position, mass)``."""
        dim = int(dim)
        if dim < self.dim:
            raise ValueError(f"cannot extend a warm state of dimension {self.dim} to the smaller dimension {dim}")
        return self.shift_window(0, dim - self.dim, position=position, mass=mass)

    def remap(self, dim: int, map: Callable[[int], "int | None"], fill: Any = (0.0, 1.0)) -> "WarmState":
        """Rebuild every chain onto ``dim`` coordinates
        (``WarmState::remap`` in Rust): new coordinate ``j`` carries old
        coordinate ``map(j)`` (position and mass copied; it must be below
        the current dimension) or, when ``map(j)`` is ``None``, the
        ``(position, mass)`` of ``fill`` -- a pair of floats, or a callable
        ``fill(chain, j)`` returning one. Step sizes are unchanged;
        coordinates may be dropped, reordered or duplicated. ``extend_to``
        is the identity on the old coordinates; ``shift_window`` is the
        fixed-lag case."""
        dim = int(dim)
        if dim < 1:
            raise ValueError("dim must be positive")
        sources = [map(j) for j in range(dim)]
        for source in sources:
            if source is not None and not 0 <= int(source) < self.dim:
                raise ValueError(f"remap refers to coordinate {source} of a warm state of dimension {self.dim}")
        positions = np.empty((self.chains, dim), dtype=np.float64)
        mass = np.empty((self.chains, dim), dtype=np.float64)
        for j, source in enumerate(sources):
            if source is not None:
                positions[:, j] = self.positions[:, int(source)]
                mass[:, j] = self.mass_diagonal[:, int(source)]
            elif callable(fill):
                for chain in range(self.chains):
                    positions[chain, j], mass[chain, j] = fill(chain, j)
            else:
                positions[:, j], mass[:, j] = float(fill[0]), float(fill[1])
        return WarmState(positions=positions, step_sizes=self.step_sizes.copy(), mass_diagonal=mass)

    def shift_window(self, drop_front: int, append: int, position: float = 0.0, mass: float = 1.0,
                     fill: Any = None) -> "WarmState":
        """The fixed-lag window move (``WarmState::shift_window`` in Rust):
        drop the first ``drop_front`` coordinates, keep the rest in order,
        and append ``append`` new ones at ``(position, mass)`` -- or, with
        ``fill``, at what ``fill(chain, j)`` returns. The new dimension
        ``dim - drop_front + append`` must be positive."""
        drop_front, append = int(drop_front), int(append)
        if drop_front < 0 or append < 0:
            raise ValueError("drop_front and append must be nonnegative")
        if drop_front > self.dim:
            raise ValueError(f"cannot drop {drop_front} coordinates from a warm state of dimension {self.dim}")
        kept = self.dim - drop_front
        return self.remap(kept + append, lambda j: j + drop_front if j < kept else None,
                          fill if fill is not None else (position, mass))


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

    def warm_state(self) -> "WarmState":
        """The state a warm continuation (``sample_warm``) starts from: per
        chain, its last retained draw, its final step size and its final
        diagonal mass (``Posterior::warm_state`` in Rust). Raises
        ``ValueError`` for a structured-mass run, whose metric is not a
        diagonal."""
        if isinstance(self.config.get("mass"), list):
            raise ValueError("warm continuation carries identity or diagonal metrics only; this run used a structured mass")
        if self.samples.ndim != 3 or self.samples.shape[1] == 0:
            raise ValueError("the run has no retained draws")
        return WarmState(
            positions=np.ascontiguousarray(self.samples[:, -1, :], dtype=np.float64),
            step_sizes=self.final_step_size.astype(np.float64),
            mass_diagonal=np.stack([np.asarray(c["metadata"]["mass_diagonal"], dtype=np.float64) for c in self.chains]),
        )

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
        followed by one line of pooled health and one ``warning: chain ...``
        line per chain flagged by ``chain_warnings()``; what ``print(result)``
        shows."""
        table = format_summary(self.summary(var_names), self.health(), self.wall_seconds)
        lines = self._chain_warnings()[1]
        return "\n".join([table, *lines]) if lines else table

    def chain_warnings(self) -> list[dict[str, Any]]:
        """Observe-only checks for a chain that disagrees with the others
        (``owalnuts::diagnostics::ChainWarning``; the draws are unchanged).

        One dict per finding with ``chain``, ``check`` (``warmup_step``,
        ``warmup_log_density``, ``sampled_log_density``, ``rhat`` or
        ``rhat_cluster``), the chain's ``value``, the ``reference`` it is
        compared with, the ``threshold`` (density checks) and the printed
        ``text``. Inputs are each chain's ``warmup_end`` / ``sampling_end``
        window (step, median and IQR of the selected-state log density) and
        the leave-one-chain-out and pairwise R-hat of the retained draws. These
        checks need at least three chains.

        ``rhat_cluster`` (WP74) fires when R-hat exceeds 1.01: two chains agree
        when the maximum R-hat of that pair alone is at most 1.01, and every
        chain outside the largest group of agreeing chains (size tie: the
        higher retained log density) is flagged, provided that group has at
        least two chains. Its dict adds ``reference_chains`` (that group);
        ``value`` is the chain's lowest pair R-hat with the group and
        ``reference`` the all-chain R-hat. It reports mode splits that no
        single chain explains (two chains per mode, a chain crossing modes).
        A warning is a reason to inspect the chain, not a verdict; the R-hat
        and ESS gates still apply.

        A chain that rejected nonfinite integrator positions (rescued as
        zero-density leaves by the default ``RejectLeaf`` policy, which
        records no divergence) adds one dict with ``check`` equal to
        ``nonfinite_positions``, ``warmup`` and ``sampling`` counts and
        ``value`` their sum, for any number of chains. Empty when no chain
        disagrees and none rejected a nonfinite position."""
        return [dict(w) for w in self._chain_warnings()[0]]

    def _chain_warnings(self) -> tuple[list[dict[str, Any]], list[str]]:
        warmup = [c.get("warmup_end") for c in self.chains]
        sampling = [c.get("sampling_end") for c in self.chains]
        rejections = [
            (
                int(c.get("work_discarded", {}).get("nonfinite_position_rejections", 0)),
                int(c.get("work_retained", {}).get("nonfinite_position_rejections", 0)),
            )
            for c in self.chains
        ]
        samples = np.ascontiguousarray(self.samples, dtype=np.float64)
        warnings, lines = _owalnuts.chain_warnings(samples, warmup, sampling, rejections)
        return list(warnings), list(lines)

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


#: Named start rules of ``sample(init=...)``; ``None`` means ``DEFAULTS["init"]``.
START_RULES: tuple[str, ...] = ("best_of", "uniform", "jitter")


def _start_rule(init: Any) -> str | None:
    """The named start rule ``init`` selects, or ``None`` for an explicit array."""
    if init is None:
        return str(DEFAULTS["init"])
    if isinstance(init, str):
        if init not in START_RULES:
            raise ValueError(f"init={init!r}: named start rules are {', '.join(map(repr, START_RULES))}")
        return init
    return None


def _starts(init: Any, dim: int, chains: int, seed: int, jitter: float) -> np.ndarray:
    """``init="jitter"`` (the pre-WP58 ``init=None``) and explicit arrays."""
    if isinstance(init, str) and init != "jitter":
        raise ValueError(f"init={init!r} is not an unchecked start rule")
    if init is None or (isinstance(init, str) and init == "jitter"):
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
    points (refined, then zero weight), and never raise across the ABI. A
    finite value with a nonfinite gradient is a fatal error, not a
    zero-density point. For numba, compile the ``cfunc`` and its ``njit``
    helpers with ``error_model="numpy"``: the default ``"python"`` raises
    ``ZeroDivisionError`` on a float division by zero, which cannot cross
    the ABI (STUDIES/python_callpath_v1). With that recipe it runs within
    1.15x of a native Rust target and scales with ``threads``
    (STUDIES/python_callpath_linux_v1, WP78).
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
    init_candidates: int = DEFAULTS["init_candidates"],
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

    ``init`` selects the starts (``START_RULES``):

    * ``None`` (default) or ``"best_of"``: the Rust default
      ``owalnuts::sampler::Init::best_of(init_candidates)`` (16 since WP52) —
      per chain, ``init_candidates`` evaluable uniform(-``init_radius``,
      ``init_radius``) candidates (each redrawn up to ``init_max_attempts``
      times until the log density and gradient are finite), keeping the one
      of highest log density. Identical to the Rust sampler's starts for the
      same seed. The candidate evaluations (about 64 for four chains) are
      not counted in ``target_calls``.
    * ``"uniform"``: Stan's rule, ``Init::uniform`` — one evaluable
      uniform(-``init_radius``, ``init_radius``) start per chain.
    * ``"jitter"``: independent uniform(-``init_jitter``, ``init_jitter``)
      starts drawn in numpy without evaluating the target — the ``init=None``
      behaviour before WP58 (``STUDIES/nutpie_per_gradient_gap_v1``: it
      failed every lotka_volterra run at transition 0). Kept for
      reproducibility.
    * a ``(dim,)`` point (jittered per chain by ``init_jitter``) or a
      ``(chains, dim)`` array: used as given.

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
        rule = _start_rule(init)
        if rule == "best_of":
            starts = _owalnuts.best_of_starts_stan(
                st.model_so, st.data, chains, seed, init_candidates, init_radius, init_max_attempts, st.seed,
                preload,
            )[0]
        elif rule == "uniform":
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
        rule = _start_rule(init)
        if rule == "best_of":
            starts = _owalnuts.best_of_starts_cfunc(
                cft.address, cft.dim, chains, seed, init_candidates, init_radius, init_max_attempts, cft.user_data,
            )[0]
        elif rule == "uniform":
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
    rule = _start_rule(init)
    if rule == "best_of":
        starts = _owalnuts.best_of_starts_callable(
            target, dim, chains, seed, init_candidates, init_radius, init_max_attempts, nonfinite,
        )[0]
    elif rule == "uniform":
        starts = _owalnuts.uniform_starts_callable(
            target, dim, chains, seed, init_radius, init_max_attempts, nonfinite,
        )
    else:
        starts = _starts(init, dim, chains, seed, init_jitter)
    raw = _owalnuts.sample_callable(target, starts, cfg, nonfinite, refresh, refresh_restart)
    return _result(raw, cfg)


@dataclass
class ContinuationChunk:
    """New draws/diagnostics, with explicitly cumulative work and adaptation.

    Concatenate ``samples`` along axis 1 before computing posterior diagnostics.
    A warmup chunk has no retained samples and contains warmup diagnostics.
    """
    samples: np.ndarray
    diagnostics: list[dict[str, Any]]
    cumulative_work: list[dict[str, Any]]
    metadata: list[dict[str, Any]]
    retained_start: int
    retained_end: int
    is_warmup: bool
    target_calls: int
    cumulative_target_calls: int
    initialization_target_calls: int
    wall_seconds: float

    def warm_state(self) -> "WarmState":
        """The warm state at the end of this chunk: per chain, the chunk's
        last retained draw, the session's step size and diagonal mass
        (``SessionChunk::warm_state`` in Rust). Raises ``ValueError`` on a
        warmup chunk, which has no retained draws."""
        if self.samples.ndim != 3 or self.samples.shape[1] == 0:
            raise ValueError("the chunk has no retained draws (a warmup chunk?)")
        return WarmState(
            positions=np.ascontiguousarray(self.samples[:, -1, :], dtype=np.float64),
            step_sizes=np.array([m["final_step_size"] for m in self.metadata], dtype=np.float64),
            mass_diagonal=np.stack([np.asarray(m["mass_diagonal"], dtype=np.float64) for m in self.metadata]),
        )


class CFuncSession:
    """Single-worker continuation; use as a context manager or call close().

    Warmup runs once, then draw(n) advances n additional draws per chain with
    frozen adaptation. Errors during execution make the session terminal.
    Cancel is cooperative: an arbitrary stuck native callback cannot be killed
    in-process. Dropping a session signals cancellation without waiting; the
    worker retains compiled-code ownership until its callback has returned.
    """
    def __init__(self, inner):
        self._inner = inner

    def adapt(self) -> ContinuationChunk:
        return ContinuationChunk(**self._inner.adapt())

    def draw(self, draws: int) -> ContinuationChunk:
        if isinstance(draws, bool) or not isinstance(draws, (int, np.integer)) or draws < 1:
            raise ValueError("draws must be a positive integer")
        return ContinuationChunk(**self._inner.draw(int(draws)))

    def progress(self) -> dict[str, Any]:
        """Last completed-request/error snapshot, not live execution progress.

        During adapt/draw, counters and transition indices can remain zero or
        reflect the previous completed call. Time individual requests externally
        when reporting the active phase.
        """
        return self._inner.progress()

    def cancel(self) -> None:
        self._inner.cancel()

    def close(self) -> None:
        self._inner.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()


def start_session(
    target: CFuncTarget, *, init: Any, max_draws: int, chains: int = 4,
    warmup: int = 1000, seed: int = 0, threads: int = 1,
    tuning: Tuning = Tuning(), adaptation: Adaptation | None = Adaptation(),
    mass: Any = None, max_target_evaluations: int | None = None,
    max_depth_stop_limit: int | None = None, admit_worst_case: bool = True,
    cache_initial_evaluation: bool | None = None,
) -> CFuncSession:
    """Create a CFunc-only continuation session with a fixed lifetime budget.

    ``init`` must explicitly contain every chain's start, shape (chains, dim).
    Only identity/diagonal sampling is supported. Threads bound parallel chains. Numerical kernel,
    warmup, tuning, seed derivation and cache defaults equal ordinary sample().
    Admission and max_target_evaluations cover warmup plus max_draws across all
    chains, not individual chunks. No target calls occur before adapt().
    """
    if not isinstance(target, CFuncTarget):
        raise TypeError("start_session requires a CFuncTarget")
    for name, value, minimum in [("chains", chains, 1), ("max_draws", max_draws, 1), ("warmup", warmup, 0)]:
        if isinstance(value, bool) or not isinstance(value, (int, np.integer)) or value < minimum:
            raise ValueError(f"{name} must be an integer >= {minimum}")
    if isinstance(threads, bool) or not isinstance(threads, (int, np.integer)) or threads < 1:
        raise ValueError("threads must be a positive integer")
    starts = np.ascontiguousarray(init, dtype=np.float64)
    if starts.shape != (chains, target.dim) or not np.isfinite(starts).all():
        raise ValueError("init must be a finite (chains, target.dim) matrix")
    if mass is not None and np.asarray(mass).ndim != 1:
        raise ValueError("continuation supports identity/diagonal mass only")
    cfg = _config_dict(warmup=warmup, draws=max_draws, seed=seed, threads=int(threads),
        tuning=tuning, adaptation=adaptation, mass=mass,
        max_target_evaluations=max_target_evaluations,
        max_depth_stop_limit=max_depth_stop_limit, admit_worst_case=admit_worst_case,
        cache_initial_evaluation=cache_initial_evaluation)
    inner = _owalnuts.start_cfunc_session(target, target.address, target.dim, starts,
        cfg, target.user_data, list(target.parameter_names) if target.parameter_names else None)
    return CFuncSession(inner)


@dataclass
class WarmChunk:
    """The draws of one ``WarmSession.refresh`` call: ``samples`` is
    ``(chains, draws, dim)``; ``diagnostics`` and ``metadata`` are per
    chain (``metadata[c]`` has ``effective_seed``, ``final_step_size`` and
    ``mass_diagonal``); ``work[c]`` is the chain's kernel work totals for
    this call; ``seed`` is the call's base seed and ``call_index`` its
    zero-based index; ``target_calls`` is the kernel's gradient count
    summed over chains."""
    samples: np.ndarray
    diagnostics: list[dict[str, Any]]
    metadata: list[dict[str, Any]]
    work: list[dict[str, Any]]
    seed: int
    call_index: int
    target_calls: int
    wall_seconds: float

    def warm_state(self) -> "WarmState":
        """The state at the end of this call (what ``WarmSession.state()``
        holds after it)."""
        return WarmState(
            positions=np.ascontiguousarray(self.samples[:, -1, :], dtype=np.float64),
            step_sizes=np.array([m["final_step_size"] for m in self.metadata], dtype=np.float64),
            mass_diagonal=np.stack([np.asarray(m["mass_diagonal"], dtype=np.float64) for m in self.metadata]),
        )


class WarmSession:
    """A resident warm-continuation session (``Sampler::start_warm_session``
    / ``WarmSession`` in Rust): the target, a pool of ``threads`` workers
    and every per-chain configuration stay alive across ``refresh`` calls.

    ``WarmSession(target, state, *, seed, threads, tuning, ...)`` takes a
    callable or a ``CFuncTarget`` and a ``WarmState`` of its dimension.
    ``refresh(draws)`` runs ``draws`` transitions per chain from the
    current state and returns a ``WarmChunk``; ``state()`` is the current
    ``WarmState``; ``retarget(target, state)`` swaps the target and state
    (a new dimension is allowed, the chain count must be the session's;
    the per-tick call after ``state.shift_window(...)`` or
    ``state.extend_to(...)``); ``close()`` joins the worker (also on
    leaving a ``with`` block).

    Seed rule: call ``n`` (``session.calls`` before the call) uses the base
    seed ``seed + n * chains``, and chain ``c`` of it seed ``seed + n *
    chains + c``, so call ``n`` is bit-identical to ``sample_warm(target,
    state_n, draws=k, seed=seed + n * chains, ...)`` on the state before
    the call (``tests/test_warm_continuation.py``). ``retarget`` does not
    reset the counter.

    Per call, the kernel allocates one draw buffer and one diagnostics
    vector per chain, handed over in the chunk; no pool is built and
    nothing is re-adapted or re-validated beyond admission. Limits apply
    per call. An execution error (budget exhausted, deadline,
    cancellation, a fatal target error) makes the session terminal; an
    error before any target call (``draws=0``, a refused admission, a
    ``retarget`` whose state does not fit) leaves it as it was. A Python
    callable is serialised by the GIL; use a ``CFuncTarget`` for real
    parallel chains. Dropping a session cancels without waiting; the
    worker keeps the target until its last callback has returned.
    """

    def __init__(
        self,
        target: "LogpGrad | CFuncTarget",
        state: WarmState,
        *,
        seed: int = 0,
        threads: int = 1,
        tuning: Tuning = Tuning(),
        nonfinite: str = "zero_density",
        max_target_evaluations: int | None = None,
        max_depth_stop_limit: int | None = None,
        admit_worst_case: bool = True,
        coerce: bool = True,
        cache_initial_evaluation: bool | None = None,
    ):
        if not isinstance(state, WarmState):
            raise TypeError("state must be a WarmState (SampleResult.warm_state())")
        if isinstance(threads, bool) or not isinstance(threads, (int, np.integer)) or threads < 1:
            raise ValueError("threads must be a positive integer")
        cfg = _config_dict(
            warmup=0, draws=1, seed=seed, threads=threads, tuning=tuning,
            adaptation=None, mass=None, max_target_evaluations=max_target_evaluations,
            max_depth_stop_limit=max_depth_stop_limit, admit_worst_case=admit_worst_case,
            cache_initial_evaluation=cache_initial_evaluation,
        )
        self._nonfinite = nonfinite
        self._coerce = coerce
        self._seed = int(seed)
        self._chains = state.chains
        if isinstance(target, StanTarget):
            raise TypeError("WarmSession supports callables and CFuncTarget; pass the StanTarget as a callable")
        if isinstance(target, CFuncTarget):
            if target.dim != state.dim:
                raise ValueError(f"CFuncTarget dim {target.dim} != warm state dim {state.dim}")
            self._cfunc = True
            self._inner = _owalnuts.start_warm_session_cfunc(
                target, target.address, target.dim, state.positions, state.step_sizes, state.mass_diagonal,
                cfg, target.user_data, list(target.parameter_names) if target.parameter_names else None,
            )
        else:
            self._cfunc = False
            fn = wrap_callable(target) if coerce else target
            self._inner = _owalnuts.start_warm_session_callable(
                fn, state.positions, state.step_sizes, state.mass_diagonal, cfg, nonfinite,
            )

    def refresh(self, draws: int) -> WarmChunk:
        """Run ``draws`` transitions per chain from the current state."""
        if isinstance(draws, bool) or not isinstance(draws, (int, np.integer)) or draws < 1:
            raise ValueError("draws must be a positive integer")
        return WarmChunk(**self._inner.refresh(int(draws)))

    def state(self) -> WarmState:
        """The current state: every chain's position after the last call,
        with the carried step sizes and masses."""
        positions, step_sizes, mass = self._inner.state()
        return WarmState(positions=positions, step_sizes=step_sizes, mass_diagonal=mass)

    def retarget(self, target: "LogpGrad | CFuncTarget", state: WarmState) -> None:
        """Swap the target and the state (same kind of target as the
        session was started with: callable or ``CFuncTarget``)."""
        if not isinstance(state, WarmState):
            raise TypeError("state must be a WarmState")
        if state.chains != self._chains:
            raise ValueError(f"state has {state.chains} chains; the session has {self._chains}")
        if isinstance(target, CFuncTarget):
            if not self._cfunc:
                raise TypeError("this session was started on a callable; retarget with a callable")
            if target.dim != state.dim:
                raise ValueError(f"CFuncTarget dim {target.dim} != warm state dim {state.dim}")
            self._inner.retarget_cfunc(
                target, target.address, target.dim, state.positions, state.step_sizes, state.mass_diagonal,
                target.user_data, list(target.parameter_names) if target.parameter_names else None,
            )
            return
        if self._cfunc:
            raise TypeError("this session was started on a CFuncTarget; retarget with a CFuncTarget")
        if isinstance(target, StanTarget):
            raise TypeError("WarmSession supports callables and CFuncTarget; pass the StanTarget as a callable")
        fn = wrap_callable(target) if self._coerce else target
        self._inner.retarget_callable(fn, state.positions, state.step_sizes, state.mass_diagonal, self._nonfinite)

    @property
    def calls(self) -> int:
        """Calls completed so far (the index of the next call)."""
        return int(self._inner.calls())

    @property
    def chains(self) -> int:
        return self._chains

    @property
    def threads(self) -> int:
        return int(self._inner.threads())

    @property
    def terminal(self) -> bool:
        """Whether an execution error has ended the session."""
        return bool(self._inner.is_terminal())

    def seed_for_call(self, call: int) -> int:
        """The base seed of call ``call``: ``seed + call * chains``."""
        return int(self._inner.seed_for_call(int(call)))

    @property
    def next_seed(self) -> int:
        return int(self._inner.next_seed())

    def cancel(self) -> None:
        self._inner.cancel()

    def close(self) -> None:
        self._inner.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()


def sample_warm(
    logp_and_grad: "LogpGrad | CFuncTarget",
    state: WarmState,
    *,
    draws: int,
    seed: int = 0,
    threads: int = 1,
    tuning: Tuning = Tuning(),
    nonfinite: str = "zero_density",
    max_target_evaluations: int | None = None,
    max_depth_stop_limit: int | None = None,
    admit_worst_case: bool = True,
    coerce: bool = True,
    cache_initial_evaluation: bool | None = None,
) -> SampleResult:
    """Warm continuation (``Sampler::run_warm``): ``draws`` transitions per
    chain from ``state``, with no warmup and no adaptation, each chain on
    its own carried step size and fixed diagonal mass.

    This is the WP84 (``STUDIES/online_sv_quote_v1``) warm path as a library
    call: take ``result.warm_state()`` from a completed ``sample`` (or
    ``chunk.warm_state()`` from a session), optionally ``extend_to`` it onto
    a target of larger dimension, and refresh the posterior on the new
    target in ``draws`` transitions; the result's ``warm_state()`` is the
    next state. ``logp_and_grad`` is a callable (including ``from_pymc``
    targets) or a ``CFuncTarget``; its dimension is the state's.

    Chain ``c`` is run exactly as ``sample(target, dim, init=positions[c:c+1],
    chains=1, warmup=0, draws=draws, seed=seed + c, adaptation=None,
    mass=mass_diagonal[c], tuning=replace(tuning, step_size=step_sizes[c]))``
    and its draws are bit-identical to that call (the chain seeds are
    ``splitmix64(seed + c)``, the ordinary rule). ``tuning.step_size`` is
    ignored: the state carries each chain's step. Chains run in parallel on
    up to ``threads`` workers (a Python callable is serialised by the GIL;
    use a ``CFuncTarget`` for real parallelism); admission and limits apply
    to the whole run as for ``sample``.

    Not validated by the library: whether ``draws`` transitions on a frozen
    step and metric are enough for the new target (WP84: 50–200 draws per
    chain met its calibration bar on a 250-return SV model but not an R-hat
    1.01 bar), and whether the fill of appended coordinates is a sensible
    start; both are the caller's decisions.
    """
    if not isinstance(state, WarmState):
        raise TypeError("state must be a WarmState (SampleResult.warm_state())")
    if isinstance(draws, bool) or not isinstance(draws, (int, np.integer)) or draws < 1:
        raise ValueError("draws must be a positive integer")
    if isinstance(threads, bool) or not isinstance(threads, (int, np.integer)) or threads < 1:
        raise ValueError("threads must be a positive integer")
    cfg = _config_dict(
        warmup=0, draws=draws, seed=seed, threads=threads, tuning=tuning,
        adaptation=None, mass=None, max_target_evaluations=max_target_evaluations,
        max_depth_stop_limit=max_depth_stop_limit, admit_worst_case=admit_worst_case,
        cache_initial_evaluation=cache_initial_evaluation,
    )
    if isinstance(logp_and_grad, StanTarget):
        raise TypeError("sample_warm supports callables and CFuncTarget; pass the StanTarget as a callable")
    if isinstance(logp_and_grad, CFuncTarget):
        cft = logp_and_grad
        if cft.dim != state.dim:
            raise ValueError(f"CFuncTarget dim {cft.dim} != warm state dim {state.dim}")
        raw = _owalnuts.sample_warm_cfunc(
            cft.address, cft.dim, state.positions, state.step_sizes, state.mass_diagonal, cfg,
            cft.user_data, list(cft.parameter_names) if cft.parameter_names else None,
        )
        result = _result(raw, cfg)
        result.parameter_names = list(cft.parameter_names) if cft.parameter_names else None
        return result
    target = wrap_callable(logp_and_grad) if coerce else logp_and_grad
    raw = _owalnuts.sample_warm_callable(
        target, state.positions, state.step_sizes, state.mass_diagonal, cfg, nonfinite,
    )
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


def best_of_starts(logp_and_grad: "LogpGrad | CFuncTarget | StanTarget", dim: int | None = None, *,
                   chains: int = 4, seed: int = 0, candidates: int = DEFAULTS["init_candidates"],
                   radius: float = DEFAULTS["init_radius"], max_attempts: int = DEFAULTS["init_max_attempts"],
                   nonfinite: str = "zero_density", coerce: bool = True,
                   return_details: bool = False) -> "np.ndarray | dict[str, Any]":
    """Draw ``(chains, dim)`` starts by the default ``init="best_of"`` rule
    (``owalnuts::sampler::candidate_starts``, highest density) without
    sampling: the starts ``sample(init=None, seed=seed)`` uses.

    With ``return_details=True`` returns a dict with ``starts``,
    ``start_log_densities`` (per chain), ``candidate_log_densities`` (per
    chain, every evaluable candidate in draw order), ``chosen`` (index of the
    kept candidate) and ``evaluations`` (target calls per chain, including
    redrawn non-evaluable candidates)."""
    if isinstance(logp_and_grad, StanTarget):
        st = logp_and_grad
        raw = _owalnuts.best_of_starts_stan(st.model_so, st.data, chains, seed, candidates, radius, max_attempts,
                                            st.seed, list(st.preload) or None)
    elif isinstance(logp_and_grad, CFuncTarget):
        raw = _owalnuts.best_of_starts_cfunc(logp_and_grad.address, logp_and_grad.dim, chains, seed, candidates,
                                             radius, max_attempts, logp_and_grad.user_data)
    else:
        if dim is None:
            raise ValueError("dim is required for a callable target")
        target = wrap_callable(logp_and_grad) if coerce else logp_and_grad
        raw = _owalnuts.best_of_starts_callable(target, dim, chains, seed, candidates, radius, max_attempts,
                                                nonfinite)
    starts = np.asarray(raw[0])
    if not return_details:
        return starts
    return {"starts": starts, "start_log_densities": list(raw[1]),
            "candidate_log_densities": [list(c) for c in raw[2]], "chosen": list(raw[3]),
            "evaluations": list(raw[4])}


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
    """Wrap a JAX scalar log density. Enables x64 (the kernel is binary64).

    A Python callable: use ``threads=1``. JAX's per-call dispatch adds about
    20-40 us per gradient (STUDIES/python_callpath_linux_v1, WP78), so for a
    cheap density a numba ``from_cfunc`` is much faster.
    """
    import jax
    import jax.numpy as jnp

    jax.config.update("jax_enable_x64", True)
    vg = jax.value_and_grad(logp_fn)
    if jit:
        vg = jax.jit(vg)

        # A jitted function takes the float64 numpy position directly: its C++
        # dispatch transfers it in the same call, so a separate
        # ``jnp.asarray`` dispatch (15-170 us per call measured in
        # STUDIES/python_callpath_v1) is pure overhead. Same executable, same
        # arithmetic, same draws.
        def target(q: np.ndarray) -> tuple[float, np.ndarray]:
            value, grad = vg(q)
            return float(value), np.asarray(grad, dtype=np.float64)

        return target

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
    compiled function before use. PyMC Data and mutable dimensions are frozen
    on a separate model at compile time; later changes require a new target.
    Unsupported shared graph inputs are rejected rather than left unbound.
    Nonfinite log densities or gradients become recoverable
    zero-density evaluations, matching the callable transport's default.
    Raises ``NotImplementedError`` when the PyTensor numba
    backend cannot supply a wrappable jit function.
    """
    import ctypes

    import numba
    import pytensor
    from pytensor.compile import SharedVariable
    try:
        from pytensor.graph.traversal import graph_inputs
    except ImportError:  # Older PyTensor versions exported this from basic.
        from pytensor.graph.basic import graph_inputs

    q0, dim, names, unravel = _pymc_layout(model)
    original_initial = model.initial_point()
    shared_inputs = any(isinstance(var, SharedVariable) for var in graph_inputs([model.logp()]))
    shared_dimensions = any(isinstance(var, SharedVariable) for var in model.dim_lengths.values())
    frozen_model = model
    if shared_inputs or shared_dimensions:
        try:
            # PyMC 5.28+ exports it only from the optimization submodule;
            # older releases also re-export it from pymc.model.transform.
            from pymc.model.transform.optimization import freeze_dims_and_data
        except ImportError:
            try:
                from pymc.model.transform import freeze_dims_and_data
            except ImportError:
                freeze_dims_and_data = None
        if freeze_dims_and_data is None:
            raise NotImplementedError(
                "gil_free=True requires PyMC freeze_dims_and_data for shared data; "
                "upgrade PyMC or use gil_free=False"
            ) from None
        try:
            frozen_model = freeze_dims_and_data(model)
        except Exception as error:
            raise NotImplementedError(
                "could not snapshot PyMC data and dimensions without changing the model; "
                "use supported constant initial values or gil_free=False"
            ) from error

    # The official transform freezes named pm.Data and dimensions. An external
    # pytensor.shared used directly in a Potential can survive that transform.
    remaining_shared = [var for var in graph_inputs([frozen_model.logp()])
                        if isinstance(var, SharedVariable)]
    if remaining_shared:
        shared_names = ", ".join(var.name or "<unnamed>" for var in remaining_shared)
        raise NotImplementedError(
            "gil_free=True cannot snapshot these remaining shared graph inputs: "
            + shared_names + "; register them as pm.Data or use gil_free=False"
        )

    # Rebuilding a graph need not preserve free-RV insertion order. Bind its
    # value variables explicitly in the original public unconstrained layout.
    frozen_values = {var.name: var for var in frozen_model.value_vars}
    frozen_initial = original_initial if frozen_model is model else frozen_model.initial_point()
    if set(frozen_values) != set(names) or any(
        name not in frozen_initial
        or np.shape(frozen_initial[name]) != np.shape(original_initial[name])
        or not np.array_equal(frozen_initial[name], original_initial[name], equal_nan=True)
        for name in names
    ):
        raise NotImplementedError(
            "freezing PyMC data changed the unconstrained layout or initial values; "
            "use gil_free=False"
        )
    # numba fastmath off: with PyTensor's default fastmath the numba code
    # differs between a fresh compile and a load from numba's file cache, so
    # the first process to compile a model draws differently from later ones
    # (WP86, STUDIES/pymc_gil_free_determinism_v1). Wall per gradient is
    # unchanged and PyTensor keys its cache on the flag.
    with pytensor.config.change_flags(numba__fastmath=False):
        fn = frozen_model.logp_dlogp_function(
            grad_vars=[frozen_values[name] for name in names],
            initial_point=frozen_initial, ravel_inputs=True, mode="NUMBA",
        )
    fn.set_extra_values({})
    compiled_inputs = fn._pytensor_function.maker.fgraph.inputs
    if len(compiled_inputs) != 1 or any(isinstance(var, SharedVariable) for var in compiled_inputs):
        raise NotImplementedError(
            "PyTensor NUMBA function has inputs beyond the raveled position after freezing; "
            "use gil_free=False"
        )
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
            value = extract(logp)
            g = numba.carray(grad_ptr, (n,))
            finite = np.isfinite(value)
            for i in range(n):
                g[i] = grad[i]
                if not np.isfinite(grad[i]):
                    finite = False
            if not finite:
                # PyTensor may return a finite density but an overflowing
                # derivative on a coarse proposal. Match callable transport's
                # default recoverable policy without weakening the raw ABI.
                for i in range(n):
                    g[i] = 0.0
                return -np.inf
            return value

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
        keep_alive=(raw, inner, fn, frozen_model),
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
    single-function wrapper is only safe with ``threads=1``. Either way this
    is a Python callable serialised by the GIL, so ``threads=1`` is faster.

    For speed use ``gil_free=True`` with ``threads=4``: the parallel,
    compiled (numba) transport, 8-22x the default's ESS/s on Linux
    (STUDIES/python_callpath_linux_v1, WP78). It needs numba and fails
    closed (``NotImplementedError``) on models it cannot snapshot, such as
    ``pm.Data`` with explicit ``initval``s; fall back to the default at
    ``threads=1``.
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
    "summary", "format_summary", "uniform_starts", "best_of_starts", "START_RULES", "__version__", "CFuncTarget", "from_cfunc", "numba_raw_signature",
    "start_session", "CFuncSession", "ContinuationChunk", "WarmState", "sample_warm", "WarmSession", "WarmChunk",
    "StanTarget", "from_stan",
    "tridiagonal_cholesky", "tridiagonal_precision_mass", "diagonal_block",
    "from_numpy", "from_jax", "from_torch", "from_pymc", "to_inferencedata", "wrap_callable",
    "sample_native_eight_schools", "sample_native_local_level", "eight_schools_logp_grad",
]
