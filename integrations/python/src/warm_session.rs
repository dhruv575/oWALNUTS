//! Resident warm-continuation session (`owalnuts::sampler::WarmSession`)
//! for Python callables and compiled C-ABI targets. The worker thread owns
//! the target (a strong reference to the callable, or the cfunc keepalive);
//! the interpreter is detached around every call so the worker can take
//! the GIL for a callable's callbacks.
use super::*;
use owalnuts::sampler::{WarmChunk, WarmSession, WarmState};

enum Inner {
    Callable(WarmSession<PyTarget>),
    CFunc(WarmSession<continuation::OwnedCFunc>),
}

/// The Python-visible session; `owalnuts.WarmSession` wraps it.
#[pyclass(name = "_WarmSession")]
pub(super) struct PyWarmSession {
    inner: Inner,
}

fn callable_target(target: Py<PyAny>, dimension: usize, nonfinite: &str) -> PyResult<PyTarget> {
    Ok(PyTarget {
        callable: target,
        dimension,
        policy: NonFinitePolicy::parse(nonfinite)?,
        calls: AtomicUsize::new(0),
        recoverable: AtomicUsize::new(0),
        attached_nanos: AtomicU64::new(0),
        last_fatal: Mutex::new(None),
        // No pinned worker thread states: the session's pool threads
        // outlive any one call, and their states would otherwise be
        // released only when the session closes.
        pinned: None,
    })
}

fn cfunc_target(
    owner: Py<PyAny>,
    address: usize,
    dimension: usize,
    user_data: usize,
    parameter_names: Option<Vec<String>>,
) -> PyResult<continuation::OwnedCFunc> {
    if address == 0 {
        return Err(value_error("address must be a nonzero cfunc address"));
    }
    // SAFETY: as in `sample_cfunc`: the caller passes the address of a
    // compiled callback with the documented `RawTargetFn` ABI; `owner` is
    // the strong Python reference that keeps it alive and moves into the
    // worker-side target. The rest is asserted by `RawTarget::new`.
    let function: RawTargetFn = unsafe { std::mem::transmute::<usize, RawTargetFn>(address) };
    // SAFETY: thread-safety, reentrancy, determinism, buffer discipline, and
    // `user_data` validity are the documented `from_cfunc` contract.
    let mut raw = unsafe {
        RawTarget::new(
            nonzero(dimension, "dimension")?,
            function,
            user_data as *mut core::ffi::c_void,
        )
    };
    if let Some(names) = parameter_names {
        raw = raw.with_parameter_names(names).map_err(facade_error)?;
    }
    Ok(continuation::OwnedCFunc { raw, _owner: owner })
}

fn chunk_dict<'py>(py: Python<'py>, chunk: WarmChunk, wall: f64) -> PyResult<Bound<'py, PyDict>> {
    let count = chunk.chains.len();
    let mut flat = Vec::with_capacity(count * chunk.draws * chunk.dimension);
    let diagnostics = PyList::empty(py);
    let metadata = PyList::empty(py);
    let work = PyList::empty(py);
    for chain in &chunk.chains {
        flat.extend_from_slice(&chain.samples);
        diagnostics.append(continuation::diagnostics_dict(py, &chain.diagnostics)?)?;
        let m = PyDict::new(py);
        m.set_item("effective_seed", chain.effective_seed)?;
        m.set_item(
            "mass_diagonal",
            chain.mass_diagonal.clone().into_pyarray(py),
        )?;
        m.set_item("final_step_size", chain.step_size)?;
        metadata.append(m)?;
        work.append(work_totals(py, chain.telemetry.total())?)?;
    }
    let d = PyDict::new(py);
    d.set_item(
        "samples",
        flat.into_pyarray(py)
            .reshape([count, chunk.draws, chunk.dimension])?,
    )?;
    d.set_item("diagnostics", diagnostics)?;
    d.set_item("metadata", metadata)?;
    d.set_item("work", work)?;
    d.set_item("seed", chunk.seed)?;
    d.set_item("call_index", chunk.call_index)?;
    d.set_item("target_calls", chunk.target_calls)?;
    d.set_item("wall_seconds", wall)?;
    Ok(d)
}

fn state_tuple<'py>(py: Python<'py>, state: &WarmState) -> PyResult<Bound<'py, PyTuple>> {
    let chains = state.chain_count();
    let dimension = state.dimension();
    let mut positions = Vec::with_capacity(chains * dimension);
    let mut masses = Vec::with_capacity(chains * dimension);
    let mut steps = Vec::with_capacity(chains);
    for chain in state.chains() {
        positions.extend_from_slice(&chain.position);
        masses.extend_from_slice(&chain.mass_diagonal);
        steps.push(chain.step_size);
    }
    PyTuple::new(
        py,
        [
            positions
                .into_pyarray(py)
                .reshape([chains, dimension])?
                .into_any(),
            steps.into_pyarray(py).into_any(),
            masses
                .into_pyarray(py)
                .reshape([chains, dimension])?
                .into_any(),
        ],
    )
}

#[pymethods]
impl PyWarmSession {
    fn refresh<'py>(&mut self, py: Python<'py>, draws: usize) -> PyResult<Bound<'py, PyDict>> {
        let start = Instant::now();
        let chunk = match &mut self.inner {
            Inner::Callable(session) => py.detach(|| session.refresh(draws)),
            Inner::CFunc(session) => py.detach(|| session.refresh(draws)),
        }
        .map_err(facade_error)?;
        chunk_dict(py, chunk, start.elapsed().as_secs_f64())
    }

    /// `(positions, step_sizes, mass_diagonals)` of the current state.
    fn state<'py>(&self, py: Python<'py>) -> PyResult<Bound<'py, PyTuple>> {
        match &self.inner {
            Inner::Callable(session) => state_tuple(py, session.state()),
            Inner::CFunc(session) => state_tuple(py, session.state()),
        }
    }

    #[pyo3(signature = (target, positions, step_sizes, mass_diagonals, nonfinite="zero_density"))]
    fn retarget_callable(
        &mut self,
        py: Python<'_>,
        target: Py<PyAny>,
        positions: PyReadonlyArray2<'_, f64>,
        step_sizes: PyReadonlyArray1<'_, f64>,
        mass_diagonals: PyReadonlyArray2<'_, f64>,
        nonfinite: &str,
    ) -> PyResult<()> {
        let state = parse_warm_state(positions, step_sizes, mass_diagonals)?;
        let Inner::Callable(session) = &mut self.inner else {
            return Err(value_error(
                "this session was started on a CFuncTarget; retarget with a CFuncTarget",
            ));
        };
        let target = callable_target(target, state.dimension(), nonfinite)?;
        py.detach(|| session.retarget(target, state))
            .map_err(facade_error)
    }

    #[pyo3(signature = (owner, address, dimension, positions, step_sizes, mass_diagonals, user_data=0, parameter_names=None))]
    #[allow(clippy::too_many_arguments)]
    fn retarget_cfunc(
        &mut self,
        py: Python<'_>,
        owner: Py<PyAny>,
        address: usize,
        dimension: usize,
        positions: PyReadonlyArray2<'_, f64>,
        step_sizes: PyReadonlyArray1<'_, f64>,
        mass_diagonals: PyReadonlyArray2<'_, f64>,
        user_data: usize,
        parameter_names: Option<Vec<String>>,
    ) -> PyResult<()> {
        let state = parse_warm_state(positions, step_sizes, mass_diagonals)?;
        if state.dimension() != dimension {
            return Err(value_error(format!(
                "warm state dimension {} must match the cfunc dimension {dimension}",
                state.dimension()
            )));
        }
        let Inner::CFunc(session) = &mut self.inner else {
            return Err(value_error(
                "this session was started on a callable; retarget with a callable",
            ));
        };
        let target = cfunc_target(owner, address, dimension, user_data, parameter_names)?;
        py.detach(|| session.retarget(target, state))
            .map_err(facade_error)
    }

    fn calls(&self) -> usize {
        match &self.inner {
            Inner::Callable(session) => session.calls(),
            Inner::CFunc(session) => session.calls(),
        }
    }

    fn next_seed(&self) -> u64 {
        match &self.inner {
            Inner::Callable(session) => session.next_seed(),
            Inner::CFunc(session) => session.next_seed(),
        }
    }

    fn seed_for_call(&self, call: usize) -> u64 {
        match &self.inner {
            Inner::Callable(session) => session.seed_for_call(call),
            Inner::CFunc(session) => session.seed_for_call(call),
        }
    }

    fn is_terminal(&self) -> bool {
        match &self.inner {
            Inner::Callable(session) => session.is_terminal(),
            Inner::CFunc(session) => session.is_terminal(),
        }
    }

    fn threads(&self) -> usize {
        match &self.inner {
            Inner::Callable(session) => session.threads(),
            Inner::CFunc(session) => session.threads(),
        }
    }

    fn cancel(&self) {
        match &self.inner {
            Inner::Callable(session) => session.cancel(),
            Inner::CFunc(session) => session.cancel(),
        }
    }

    fn close(&self, py: Python<'_>) -> PyResult<()> {
        match &self.inner {
            Inner::Callable(session) => py.detach(|| session.close()),
            Inner::CFunc(session) => py.detach(|| session.close()),
        }
        .map_err(facade_error)
    }
}

/// Start a session on a Python callable; `config` is the ordinary run
/// configuration (`seed`, `threads`, tuning and limits are used; `draws`
/// is per call and warmup, mass and adaptation are ignored).
#[pyfunction]
#[pyo3(signature = (target, positions, step_sizes, mass_diagonals, config, nonfinite="zero_density"))]
pub(super) fn start_warm_session_callable(
    py: Python<'_>,
    target: Py<PyAny>,
    positions: PyReadonlyArray2<'_, f64>,
    step_sizes: PyReadonlyArray1<'_, f64>,
    mass_diagonals: PyReadonlyArray2<'_, f64>,
    config: &Bound<'_, PyDict>,
    nonfinite: &str,
) -> PyResult<PyWarmSession> {
    let state = parse_warm_state(positions, step_sizes, mass_diagonals)?;
    let run = parse_run(config, None)?;
    let target = callable_target(target, state.dimension(), nonfinite)?;
    let session = py
        .detach(move || run.sampler.start_warm_session(target, state))
        .map_err(facade_error)?;
    Ok(PyWarmSession {
        inner: Inner::Callable(session),
    })
}

/// Start a session on a compiled C-ABI target (`from_cfunc`); see
/// `start_warm_session_callable`.
#[pyfunction]
#[pyo3(signature = (owner, address, dimension, positions, step_sizes, mass_diagonals, config, user_data=0, parameter_names=None))]
#[allow(clippy::too_many_arguments)]
pub(super) fn start_warm_session_cfunc(
    py: Python<'_>,
    owner: Py<PyAny>,
    address: usize,
    dimension: usize,
    positions: PyReadonlyArray2<'_, f64>,
    step_sizes: PyReadonlyArray1<'_, f64>,
    mass_diagonals: PyReadonlyArray2<'_, f64>,
    config: &Bound<'_, PyDict>,
    user_data: usize,
    parameter_names: Option<Vec<String>>,
) -> PyResult<PyWarmSession> {
    let state = parse_warm_state(positions, step_sizes, mass_diagonals)?;
    if state.dimension() != dimension {
        return Err(value_error(format!(
            "warm state dimension {} must match the cfunc dimension {dimension}",
            state.dimension()
        )));
    }
    let run = parse_run(config, None)?;
    let target = cfunc_target(owner, address, dimension, user_data, parameter_names)?;
    let session = py
        .detach(move || run.sampler.start_warm_session(target, state))
        .map_err(facade_error)?;
    Ok(PyWarmSession {
        inner: Inner::CFunc(session),
    })
}
