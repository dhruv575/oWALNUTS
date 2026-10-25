//! CFunc continuation transport. The worker target owns the Python keepalive;
//! callback code remains live even if the Python session is dropped mid-call.
use super::*;
use owalnuts::sampler::{SessionChunk, SessionHandle};

struct OwnedCFunc {
    raw: RawTarget,
    _owner: Py<PyAny>,
}
impl Target for OwnedCFunc {
    fn dimension(&self) -> usize {
        self.raw.dimension()
    }
    fn log_density_gradient(&self, q: &[f64], g: &mut [f64]) -> Result<f64, TargetError> {
        self.raw.log_density_gradient(q, g)
    }
    fn parameter_names(&self) -> Option<Vec<String>> {
        self.raw.parameter_names()
    }
}

#[pyclass]
pub(super) struct CFuncSession {
    handle: SessionHandle,
}

fn chunk_dict<'py>(
    py: Python<'py>,
    chunk: SessionChunk,
    wall: f64,
) -> PyResult<Bound<'py, PyDict>> {
    let count = chunk.chains.len();
    let draws = chunk.retained_end - chunk.retained_start;
    let mut flat = Vec::new();
    let diagnostics = PyList::empty(py);
    let cumulative_work = PyList::empty(py);
    let metadata = PyList::empty(py);
    for chain in &chunk.chains {
        flat.extend_from_slice(&chain.samples);
        let d = PyDict::new(py);
        d.set_item(
            "depth",
            chain
                .diagnostics
                .iter()
                .map(|v| v.depth() as u32)
                .collect::<Vec<_>>()
                .into_pyarray(py),
        )?;
        d.set_item(
            "stop",
            chain
                .diagnostics
                .iter()
                .map(|v| stop_code(v.stop()))
                .collect::<Vec<_>>()
                .into_pyarray(py),
        )?;
        d.set_item(
            "target_evaluations",
            chain
                .diagnostics
                .iter()
                .map(|v| v.target_evaluations())
                .collect::<Vec<_>>()
                .into_pyarray(py),
        )?;
        d.set_item(
            "divergent",
            chain
                .diagnostics
                .iter()
                .map(|v| v.divergent())
                .collect::<Vec<_>>()
                .into_pyarray(py),
        )?;
        d.set_item(
            "max_abs_energy_error",
            chain
                .diagnostics
                .iter()
                .map(|v| v.maximum_absolute_energy_error())
                .collect::<Vec<_>>()
                .into_pyarray(py),
        )?;
        d.set_item(
            "leaves_built",
            chain
                .diagnostics
                .iter()
                .map(|v| v.leaves_built() as u32)
                .collect::<Vec<_>>()
                .into_pyarray(py),
        )?;
        d.set_item(
            "selected_refinement_level",
            chain
                .diagnostics
                .iter()
                .map(|v| {
                    v.selected_refinement_level()
                        .map(|level| level as i32)
                        .unwrap_or(-1)
                })
                .collect::<Vec<_>>()
                .into_pyarray(py),
        )?;
        d.set_item(
            "zero_density_evaluations",
            chain
                .diagnostics
                .iter()
                .map(|v| v.zero_density_evaluations() as u32)
                .collect::<Vec<_>>()
                .into_pyarray(py),
        )?;
        d.set_item(
            "trajectory_macro_length",
            chain
                .diagnostics
                .iter()
                .map(|v| v.trajectory_macro_length())
                .collect::<Vec<_>>()
                .into_pyarray(py),
        )?;
        diagnostics.append(d)?;
        let work = PyDict::new(py);
        work.set_item("retained", work_totals(py, chain.telemetry.retained())?)?;
        work.set_item("discarded", work_totals(py, chain.telemetry.discarded())?)?;
        work.set_item("total", work_totals(py, chain.telemetry.total())?)?;
        work.set_item(
            "including_adaptation",
            chain.telemetry.target_calls_including_adaptation(),
        )?;
        cumulative_work.append(work)?;
        let m = PyDict::new(py);
        m.set_item("effective_seed", chain.effective_seed)?;
        m.set_item(
            "mass_diagonal",
            chain.mass_diagonal.clone().into_pyarray(py),
        )?;
        m.set_item("final_step_size", chain.tuning.step_size())?;
        m.set_item("final_max_error", chain.tuning.max_error())?;
        metadata.append(m)?;
    }
    let d = PyDict::new(py);
    d.set_item(
        "samples",
        flat.into_pyarray(py)
            .reshape([count, draws, chunk.dimension])?,
    )?;
    d.set_item("diagnostics", diagnostics)?;
    d.set_item("cumulative_work", cumulative_work)?;
    d.set_item("metadata", metadata)?;
    d.set_item("retained_start", chunk.retained_start)?;
    d.set_item("retained_end", chunk.retained_end)?;
    d.set_item("is_warmup", chunk.is_warmup)?;
    d.set_item("target_calls", chunk.target_calls)?;
    d.set_item("cumulative_target_calls", chunk.cumulative_target_calls)?;
    d.set_item(
        "initialization_target_calls",
        chunk.initialization_target_calls,
    )?;
    d.set_item("wall_seconds", wall)?;
    Ok(d)
}

#[pymethods]
impl CFuncSession {
    fn adapt<'py>(&self, py: Python<'py>) -> PyResult<Bound<'py, PyDict>> {
        let start = Instant::now();
        let chunk = py.detach(|| self.handle.adapt()).map_err(facade_error)?;
        chunk_dict(py, chunk, start.elapsed().as_secs_f64())
    }
    fn draw<'py>(&self, py: Python<'py>, draws: usize) -> PyResult<Bound<'py, PyDict>> {
        let start = Instant::now();
        let chunk = py
            .detach(|| self.handle.draw(draws))
            .map_err(facade_error)?;
        chunk_dict(py, chunk, start.elapsed().as_secs_f64())
    }
    fn cancel(&self) {
        self.handle.cancel();
    }
    fn close(&self, py: Python<'_>) -> PyResult<()> {
        py.detach(|| self.handle.close()).map_err(facade_error)
    }
    fn progress<'py>(&self, py: Python<'py>) -> PyResult<Bound<'py, PyDict>> {
        let state = self.handle.progress();
        let d = PyDict::new(py);
        d.set_item("adapted", state.adapted)?;
        d.set_item("closed", state.closed)?;
        d.set_item("failed", state.failed)?;
        d.set_item("error", state.error)?;
        d.set_item("completed_transitions", state.completed_transitions)?;
        d.set_item("target_calls", state.target_calls)?;
        Ok(d)
    }
}

#[pyfunction]
#[pyo3(signature = (owner, address, dimension, starts, config, user_data=0, parameter_names=None))]
#[allow(clippy::too_many_arguments)]
pub(super) fn start_cfunc_session(
    py: Python<'_>,
    owner: Py<PyAny>,
    address: usize,
    dimension: usize,
    starts: PyReadonlyArray2<'_, f64>,
    config: &Bound<'_, PyDict>,
    user_data: usize,
    parameter_names: Option<Vec<String>>,
) -> PyResult<CFuncSession> {
    if address == 0 {
        return Err(value_error("address must be a nonzero cfunc address"));
    }
    let starts = parse_starts(starts)?;
    if starts.first().map(Vec::len) != Some(dimension) {
        return Err(value_error("start dimensions must match target"));
    }
    let run = parse_run(config, None)?;
    // SAFETY: identical explicit ABI contract to sample_cfunc; owner is a
    // strong Python reference moved into the target's worker-side lifetime.
    let function: RawTargetFn = unsafe { std::mem::transmute(address) };
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
    let target = OwnedCFunc { raw, _owner: owner };
    let handle = py
        .detach(move || run.sampler.start_session(target, &starts))
        .map_err(facade_error)?;
    Ok(CFuncSession { handle })
}
