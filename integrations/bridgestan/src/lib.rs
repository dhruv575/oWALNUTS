//! An [`owalnuts::walnutpie::Target`] backed by a BridgeStan-compiled Stan
//! model.
//!
//! BridgeStan (BSD-3-Clause, <https://github.com/roualdes/bridgestan>) exposes
//! any Stan program as a shared library with a small C API. Stan Math provides
//! reverse-mode autodiff, so a user writes the model once in Stan and never
//! writes a gradient. This crate binds the six entry points oWALNUTS needs with
//! `libloading`; no `bindgen`/libclang is required at build time. The official
//! `bridgestan` Rust crate (crates.io, same license) is the alternative where
//! libclang is available.
//!
//! # Semantics
//!
//! * Positions are Stan's *unconstrained* parameters (`bs_param_unc_num`).
//! * `log_density_gradient` is called with `propto = false` and
//!   `jacobian = true`, so the density includes the change-of-variables
//!   adjustment and all normalizing constants; posterior draws are therefore
//!   comparable to CmdStan's unconstrained draws.
//! * A Stan exception (rc != 0) is mapped to
//!   [`TargetError::recoverable`], i.e. zero density at the proposed point.
//!   This is exactly the convention of the reference walnutpie
//!   (`NoExceptLogpGrad`) and of kernel v10: the leaf refines and, at the
//!   finest level, is rejected. A returned `-inf`, `NaN` or `+inf` log
//!   density, and a finite log density with a nonfinite gradient element,
//!   are treated the same way (see [`map_evaluation`]): CmdStan and nutpie
//!   reject such a proposal rather than abort the run, and the posteriordb
//!   benchmark (`STUDIES/posteriordb_bench_v1`) lost every `arma11` cell to
//!   the previous fatal mapping. Dimension mismatches and owner-worker
//!   disconnects remain fatal.
//! * Thread safety: on Windows every BridgeStan native operation runs on one
//!   owned OS thread per target. Caller and Rayon threads use a bounded
//!   channel; drop sends shutdown and joins the owner after model destruction
//!   and native TLS teardown. [`ReplicatedStanTarget`] deliberately has one
//!   effective Windows worker regardless of its requested count. Off Windows,
//!   `STAN_THREADS=true` permits direct concurrent evaluation; otherwise a
//!   module-identity mutex serialises setup and evaluation. `threading()`
//!   reports effective call concurrency, `compiled_threading()` reports the
//!   DLL capability, and [`Execution`] reports the detailed backend.
//! * **Do not build with `STAN_THREADS=true` on Windows/mingw-w64.** GCC on
//!   mingw-w64 implements `__thread` with emulated TLS (`__emutls_get_address`
//!   on every access), and Stan Math touches its thread-local autodiff stack
//!   for every node it records. Measured on the posteriordb models
//!   (`STUDIES/posteriordb_bench_v1/artifacts/wall-gap/`): a threaded build
//!   costs 9–16x more per gradient than the default build (arK 120 vs 12.8 µs,
//!   hmm_example 445 vs 28 µs, eight schools 6.2 vs 0.59 µs); the default
//!   build matches CmdStan's per-gradient cost. Build without `STAN_THREADS`.
//!   The Windows owned worker safely serialises calls from parallel samplers.
//!   Off Windows, [`ReplicatedStanTarget`] loads one copy of the library per
//!   concurrent thread and dispatches each call to a free replica.
//! * On Windows, model and preload DLLs are process-lifetime residents. This
//!   prevents native TLS destructor callbacks from reaching unloaded code
//!   after owner shutdown. Model objects are destructed on their owner. Models
//!   load from a real-SHA-256 process-private cache, so their source files are
//!   not kept mapped or locked. Repeated same-content loads reuse modules and later
//!   processes clean stale unlocked directories. Non-Windows libraries still
//!   unload, and their replica copies are deleted, on target drop.
#![deny(unsafe_op_in_unsafe_fn)]

use libloading::{Library, Symbol};
use owalnuts::walnutpie::{Target, TargetError, TargetErrorKind};
#[cfg(not(windows))]
use std::{cell::Cell, sync::TryLockError};
#[cfg(windows)]
use std::{
    collections::HashMap,
    fs::{File, OpenOptions},
    io::Read,
    sync::mpsc::{Receiver, SyncSender, sync_channel},
    thread::{self, JoinHandle},
    time::{Duration, SystemTime, UNIX_EPOCH},
};
use std::{
    ffi::{CStr, CString, c_char, c_int, c_uint},
    fmt,
    ops::Deref,
    path::{Path, PathBuf},
    sync::atomic::{AtomicUsize, Ordering},
    sync::{Arc, Mutex, OnceLock, Weak},
};

#[cfg(windows)]
use fs2::FileExt;
#[cfg(windows)]
use sha2::{Digest, Sha256};

#[repr(C)]
struct BsModel {
    _private: [u8; 0],
}

type ConstructFn = unsafe extern "C" fn(*const c_char, c_uint, *mut *mut c_char) -> *mut BsModel;
type DestructFn = unsafe extern "C" fn(*mut BsModel);
type FreeErrorFn = unsafe extern "C" fn(*mut c_char);
type InfoFn = unsafe extern "C" fn(*const BsModel) -> *const c_char;
type UncNumFn = unsafe extern "C" fn(*const BsModel) -> c_int;
type UncNamesFn = unsafe extern "C" fn(*const BsModel) -> *const c_char;
type LogDensityGradientFn = unsafe extern "C" fn(
    *const BsModel,
    bool,
    bool,
    *const f64,
    *mut f64,
    *mut f64,
    *mut *mut c_char,
) -> c_int;

/// A normal unload-on-drop library off Windows, and a process-resident
/// registry reference on Windows.
#[cfg(not(windows))]
struct PlatformLibrary(Library);

#[cfg(windows)]
#[derive(Clone)]
struct PlatformLibrary(Arc<Library>);

impl Deref for PlatformLibrary {
    type Target = Library;

    fn deref(&self) -> &Self::Target {
        #[cfg(not(windows))]
        {
            &self.0
        }
        #[cfg(windows)]
        {
            &self.0
        }
    }
}

#[cfg(not(windows))]
fn load_library(path: &Path) -> Result<PlatformLibrary, libloading::Error> {
    // SAFETY: loading a foreign shared library runs its initialisers. The
    // caller supplies BridgeStan and its native runtime dependencies.
    unsafe { Library::new(path) }.map(PlatformLibrary)
}

#[cfg(windows)]
fn load_library(path: &Path) -> Result<PlatformLibrary, libloading::Error> {
    let key = std::fs::canonicalize(path).unwrap_or_else(|_| path.to_path_buf());
    let mut libraries = resident_libraries()
        .lock()
        .unwrap_or_else(|poisoned| poisoned.into_inner());
    if let Some(library) = libraries.get(&key) {
        return Ok(PlatformLibrary(Arc::clone(library)));
    }
    // SAFETY: loading a foreign shared library runs its initialisers. The
    // caller supplies BridgeStan and its native runtime dependencies.
    let library = Arc::new(unsafe { Library::new(path) }?);
    libraries.insert(key, Arc::clone(&library));
    Ok(PlatformLibrary(library))
}

#[cfg(windows)]
fn resident_libraries() -> &'static Mutex<HashMap<PathBuf, Arc<Library>>> {
    static LIBRARIES: OnceLock<Mutex<HashMap<PathBuf, Arc<Library>>>> = OnceLock::new();
    LIBRARIES.get_or_init(Default::default)
}

/// Effective concurrency exposed by a target.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Threading {
    /// Calls may execute concurrently.
    Concurrent,
    /// Calls are serialized.
    Serialised,
}

fn stan_threading(compiled: Threading) -> Threading {
    #[cfg(windows)]
    {
        let _ = compiled;
        Threading::Serialised
    }
    #[cfg(not(windows))]
    {
        compiled
    }
}

fn replicated_threading(compiled: Threading, effective_replicas: usize) -> Threading {
    if effective_replicas > 1 {
        Threading::Concurrent
    } else {
        stan_threading(compiled)
    }
}

/// Effective execution backend used by this target.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Execution {
    /// Direct calls to one `STAN_THREADS=true` model.
    DirectConcurrent,
    /// Direct serialized calls to one non-`STAN_THREADS` model.
    DirectSerialised,
    /// Concurrent dispatch across independent non-Windows model modules.
    ReplicatedConcurrent,
    /// Bounded-channel dispatch to one serialized Windows owner thread.
    OwnedSerialised,
}

fn stan_execution(threading: Threading) -> Execution {
    #[cfg(windows)]
    {
        let _ = threading;
        Execution::OwnedSerialised
    }
    #[cfg(not(windows))]
    {
        match threading {
            Threading::Concurrent => Execution::DirectConcurrent,
            Threading::Serialised => Execution::DirectSerialised,
        }
    }
}

fn replicated_execution(threading: Threading, effective_replicas: usize) -> Execution {
    #[cfg(windows)]
    {
        let _ = (threading, effective_replicas);
        Execution::OwnedSerialised
    }
    #[cfg(not(windows))]
    {
        if effective_replicas > 1 {
            Execution::ReplicatedConcurrent
        } else {
            stan_execution(threading)
        }
    }
}

/// Errors from loading or constructing a model.
#[derive(Debug)]
pub enum LoadError {
    Library(libloading::Error),
    Construct(String),
    Invalid(String),
}

impl fmt::Display for LoadError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            LoadError::Library(e) => write!(f, "library load failed: {e}"),
            LoadError::Construct(m) => write!(f, "bs_model_construct failed: {m}"),
            LoadError::Invalid(m) => write!(f, "invalid model: {m}"),
        }
    }
}

impl std::error::Error for LoadError {}

impl From<libloading::Error> for LoadError {
    fn from(e: libloading::Error) -> Self {
        LoadError::Library(e)
    }
}

/// A loaded, constructed Stan model exposed as an oWALNUTS target.
pub struct StanTarget {
    #[cfg(not(windows))]
    native: NativeTarget,
    #[cfg(windows)]
    worker: OwnedClient,
    dimension: usize,
    info: String,
    unc_names: Option<Vec<String>>,
    compiled_threading: Threading,
    calls: AtomicUsize,
    recoverable: AtomicUsize,
}

struct NativeTarget {
    loaded: Option<ModelAndLibraries<ModelHandle, LoadedLibraries>>,
    dimension: usize,
    info: String,
    unc_names: Option<Vec<String>>,
    compiled_threading: Threading,
    /// Shared by every target loaded from the same module. It serializes model
    /// setup/teardown and non-STAN_THREADS evaluations.
    serial: Arc<Mutex<()>>,
}

/// Field order is the lifetime invariant: Rust drops `model` before
/// `libraries`. This remains necessary on non-Windows, where libraries unload.
struct ModelAndLibraries<M, L> {
    model: M,
    _libraries: L,
}

struct LoadedLibraries {
    // The model DLL unloads before its preload dependencies off Windows.
    _library: PlatformLibrary,
    _preloaded: Vec<PlatformLibrary>,
}

struct ModelHandle {
    ptr: *mut BsModel,
    destruct: DestructFn,
    free_error: FreeErrorFn,
    log_density_gradient: LogDensityGradientFn,
}

// SAFETY: BridgeStan models are immutable after construction; concurrent
// `bs_log_density_gradient` calls are safe under STAN_THREADS=true and are
// serialised by `NativeTarget::serial` otherwise.
unsafe impl Send for ModelHandle {}
unsafe impl Sync for ModelHandle {}

impl Drop for ModelHandle {
    fn drop(&mut self) {
        if !self.ptr.is_null() {
            // SAFETY: `ptr` came from `bs_model_construct` and is destructed once.
            unsafe { (self.destruct)(self.ptr) };
            self.ptr = std::ptr::null_mut();
        }
    }
}

impl NativeTarget {
    fn load(
        model_so: &Path,
        preload: &[PathBuf],
        data: Option<&str>,
        seed: u32,
    ) -> Result<Self, LoadError> {
        let serial = module_lock(model_so);
        let setup_guard = serial
            .lock()
            .unwrap_or_else(|poisoned| poisoned.into_inner());
        let mut preloaded = Vec::with_capacity(preload.len());
        for dep in preload {
            preloaded.push(load_library(dep)?);
        }
        let library = load_library(model_so)?;
        // SAFETY: symbol types match bridgestan.h 2.x declarations.
        let (construct, destruct, free_error, info_fn, unc_num, ldg) = unsafe {
            let construct: Symbol<ConstructFn> = library.get(b"bs_model_construct\0")?;
            let destruct: Symbol<DestructFn> = library.get(b"bs_model_destruct\0")?;
            let free_error: Symbol<FreeErrorFn> = library.get(b"bs_free_error_msg\0")?;
            let info_fn: Symbol<InfoFn> = library.get(b"bs_model_info\0")?;
            let unc_num: Symbol<UncNumFn> = library.get(b"bs_param_unc_num\0")?;
            let ldg: Symbol<LogDensityGradientFn> = library.get(b"bs_log_density_gradient\0")?;
            (*construct, *destruct, *free_error, *info_fn, *unc_num, *ldg)
        };
        // Optional: older BridgeStan libraries may lack it; names are then `None`.
        // SAFETY: symbol type matches bridgestan.h 2.x.
        let unc_names_fn: Option<UncNamesFn> =
            unsafe { library.get::<UncNamesFn>(b"bs_param_unc_names\0") }
                .ok()
                .map(|s| *s);
        let data_c = match data {
            Some(d) => Some(CString::new(d).map_err(|e| LoadError::Invalid(e.to_string()))?),
            None => None,
        };
        let data_ptr = data_c.as_ref().map_or(std::ptr::null(), |c| c.as_ptr());
        let mut err: *mut c_char = std::ptr::null_mut();
        // SAFETY: valid C string (or null) and a writable error slot.
        let ptr = unsafe { construct(data_ptr, seed, &mut err) };
        if ptr.is_null() {
            let message = take_error(err, free_error);
            return Err(LoadError::Construct(message));
        }
        let model = ModelHandle {
            ptr,
            destruct,
            free_error,
            log_density_gradient: ldg,
        };
        // SAFETY: model pointer is valid; info string is owned by the model.
        let info_raw = unsafe { info_fn(ptr) };
        if info_raw.is_null() {
            return Err(LoadError::Invalid(
                "bs_model_info returned a null pointer".into(),
            ));
        }
        // SAFETY: the checked pointer names a NUL-terminated model-owned string.
        let info = unsafe { CStr::from_ptr(info_raw) }
            .to_string_lossy()
            .into_owned();
        // SAFETY: model pointer is valid.
        let dimension = unsafe { unc_num(ptr) };
        if dimension <= 0 {
            return Err(LoadError::Invalid(format!(
                "bs_param_unc_num returned {dimension}"
            )));
        }
        let compiled_threading = if info.contains("STAN_THREADS=true") {
            Threading::Concurrent
        } else {
            Threading::Serialised
        };
        let unc_names = match unc_names_fn {
            None => None,
            Some(names_fn) => {
                // SAFETY: model pointer is valid; the string is owned by the model.
                let raw = unsafe { names_fn(ptr) };
                if raw.is_null() {
                    optional_names_failure("bs_param_unc_names returned a null pointer")?
                } else {
                    // SAFETY: the checked pointer names a NUL-terminated string.
                    match unsafe { CStr::from_ptr(raw) }.to_str() {
                        Ok(joined) => parse_optional_names(joined, dimension as usize)?,
                        Err(_) => {
                            optional_names_failure("bs_param_unc_names returned malformed UTF-8")?
                        }
                    }
                }
            }
        };
        drop(setup_guard);
        Ok(Self {
            loaded: Some(ModelAndLibraries {
                model,
                _libraries: LoadedLibraries {
                    _library: library,
                    _preloaded: preloaded,
                },
            }),
            dimension: dimension as usize,
            info,
            unc_names,
            compiled_threading,
            serial,
        })
    }

    fn evaluate_unlocked(
        &self,
        position: &[f64],
        gradient: &mut [f64],
    ) -> Result<f64, TargetError> {
        let model = &self
            .loaded
            .as_ref()
            .expect("native model exists until drop")
            .model;
        let mut value = f64::NAN;
        let mut err: *mut c_char = std::ptr::null_mut();
        // SAFETY: `position` and `gradient` have `dimension` elements (checked
        // by the caller), the model pointer is valid, and `err` is a writable
        // slot that we free if set.
        let rc = unsafe {
            (model.log_density_gradient)(
                model.ptr,
                false,
                true,
                position.as_ptr(),
                &mut value,
                gradient.as_mut_ptr(),
                &mut err,
            )
        };
        if rc != 0 {
            let message = take_error(err, model.free_error);
            Err(TargetError::recoverable(format!(
                "stan exception: {message}"
            )))
        } else {
            map_evaluation(value, gradient)
        }
    }

    fn evaluate(&self, position: &[f64], gradient: &mut [f64]) -> Result<f64, TargetError> {
        match self.compiled_threading {
            Threading::Concurrent => self.evaluate_unlocked(position, gradient),
            Threading::Serialised => {
                let _guard = self
                    .serial
                    .lock()
                    .unwrap_or_else(|poisoned| poisoned.into_inner());
                self.evaluate_unlocked(position, gradient)
            }
        }
    }
}

impl Drop for NativeTarget {
    fn drop(&mut self) {
        let _teardown_guard = self
            .serial
            .lock()
            .unwrap_or_else(|poisoned| poisoned.into_inner());
        drop(self.loaded.take());
    }
}

fn parse_optional_names(joined: &str, dimension: usize) -> Result<Option<Vec<String>>, LoadError> {
    let names: Vec<String> = joined.split(',').map(str::to_owned).collect();
    if names.len() != dimension || names.iter().any(String::is_empty) {
        return optional_names_failure(format!(
            "bs_param_unc_names returned {} names for dimension {dimension}",
            names.len()
        ));
    }
    Ok(Some(names))
}

fn optional_names_failure(_message: impl Into<String>) -> Result<Option<Vec<String>>, LoadError> {
    Ok(None)
}

#[cfg(windows)]
#[derive(Clone, Debug)]
struct WorkerMetadata {
    dimension: usize,
    info: String,
    unc_names: Option<Vec<String>>,
    compiled_threading: Threading,
}

#[cfg(windows)]
enum WorkerOutcome {
    Success(f64),
    Recoverable(String),
}

#[cfg(windows)]
struct WorkerReply {
    gradient: Vec<f64>,
    outcome: WorkerOutcome,
}

#[cfg(windows)]
enum WorkerRequest {
    Evaluate {
        position: Vec<f64>,
        response: SyncSender<WorkerReply>,
    },
    Shutdown,
}

#[cfg(windows)]
trait OwnedBackend: Send + 'static {
    fn metadata(&self) -> WorkerMetadata;
    fn evaluate(&mut self, position: &[f64]) -> WorkerReply;
}

#[cfg(windows)]
impl OwnedBackend for NativeTarget {
    fn metadata(&self) -> WorkerMetadata {
        WorkerMetadata {
            dimension: self.dimension,
            info: self.info.clone(),
            unc_names: self.unc_names.clone(),
            compiled_threading: self.compiled_threading,
        }
    }

    fn evaluate(&mut self, position: &[f64]) -> WorkerReply {
        let mut gradient = vec![0.0; self.dimension];
        let outcome = match NativeTarget::evaluate(self, position, &mut gradient) {
            Ok(value) => WorkerOutcome::Success(value),
            Err(error) => WorkerOutcome::Recoverable(error.message().to_owned()),
        };
        WorkerReply { gradient, outcome }
    }
}

#[cfg(windows)]
struct OwnedClient {
    requests: SyncSender<WorkerRequest>,
    join: Option<JoinHandle<()>>,
}

#[cfg(windows)]
impl OwnedClient {
    fn evaluate(&self, position: &[f64], gradient: &mut [f64]) -> Result<f64, TargetError> {
        let (response_tx, response_rx) = sync_channel(0);
        self.requests
            .send(WorkerRequest::Evaluate {
                position: position.to_vec(),
                response: response_tx,
            })
            .map_err(|_| TargetError::new("BridgeStan owner worker disconnected"))?;
        let reply = response_rx
            .recv()
            .map_err(|_| TargetError::new("BridgeStan owner worker panicked or disconnected"))?;
        if reply.gradient.len() != gradient.len() {
            return Err(TargetError::new(
                "BridgeStan owner worker returned a mismatched gradient",
            ));
        }
        gradient.copy_from_slice(&reply.gradient);
        match reply.outcome {
            WorkerOutcome::Success(value) => Ok(value),
            WorkerOutcome::Recoverable(message) => Err(TargetError::recoverable(message)),
        }
    }

    fn shutdown(&mut self) {
        let _ = self.requests.send(WorkerRequest::Shutdown);
        if let Some(join) = self.join.take() {
            let _ = join.join();
        }
    }
}

#[cfg(windows)]
impl Drop for OwnedClient {
    fn drop(&mut self) {
        self.shutdown();
    }
}

#[cfg(windows)]
fn start_owned_worker<B, F>(loader: F) -> Result<(OwnedClient, WorkerMetadata), LoadError>
where
    B: OwnedBackend,
    F: FnOnce() -> Result<B, LoadError> + Send + 'static,
{
    static NEXT_WORKER_ID: AtomicUsize = AtomicUsize::new(0);

    let (request_tx, request_rx): (SyncSender<WorkerRequest>, Receiver<WorkerRequest>) =
        sync_channel(1);
    let (init_tx, init_rx) = sync_channel(0);
    let worker_id = NEXT_WORKER_ID.fetch_add(1, Ordering::Relaxed);
    let join = thread::Builder::new()
        .name(format!("owalnuts-bridgestan-{worker_id}"))
        .spawn(move || match loader() {
            Ok(mut backend) => {
                let metadata = backend.metadata();
                if init_tx.send(Ok(metadata)).is_err() {
                    return;
                }
                while let Ok(request) = request_rx.recv() {
                    match request {
                        WorkerRequest::Evaluate { position, response } => {
                            let _ = response.send(backend.evaluate(&position));
                        }
                        WorkerRequest::Shutdown => break,
                    }
                }
            }
            Err(error) => {
                let _ = init_tx.send(Err(error));
            }
        })
        .map_err(|error| LoadError::Invalid(format!("could not spawn owner worker: {error}")))?;
    match init_rx.recv() {
        Ok(Ok(metadata)) => Ok((
            OwnedClient {
                requests: request_tx,
                join: Some(join),
            },
            metadata,
        )),
        Ok(Err(error)) => {
            let _ = join.join();
            Err(error)
        }
        Err(_) => {
            let _ = join.join();
            Err(LoadError::Invalid(
                "BridgeStan owner worker panicked during load".into(),
            ))
        }
    }
}

impl StanTarget {
    /// Load `model_so` (a BridgeStan `*_model.so`), preloading each library in
    /// `preload` first (on Windows, `tbb.dll` from
    /// `stan/lib/stan_math/lib/tbb` must be resident before the model loads),
    /// and construct the model with CmdStan-JSON `data` and `seed`.
    ///
    /// On Windows all native operations execute on one owned OS thread and
    /// callers communicate with it through a bounded channel.
    pub fn load(
        model_so: &Path,
        preload: &[PathBuf],
        data: Option<&str>,
        seed: u32,
    ) -> Result<Self, LoadError> {
        #[cfg(not(windows))]
        let (backend, metadata) = {
            let native = NativeTarget::load(model_so, preload, data, seed)?;
            let metadata = (
                native.dimension,
                native.info.clone(),
                native.unc_names.clone(),
                native.compiled_threading,
            );
            (native, metadata)
        };
        #[cfg(windows)]
        let (backend, metadata) = {
            let cached_model = process_replica_cache()?.model_copy(model_so)?;
            let preload = preload.to_vec();
            let data = data.map(str::to_owned);
            let (worker, metadata) = start_owned_worker(move || {
                NativeTarget::load(&cached_model, &preload, data.as_deref(), seed)
            })?;
            (
                worker,
                (
                    metadata.dimension,
                    metadata.info,
                    metadata.unc_names,
                    metadata.compiled_threading,
                ),
            )
        };
        Ok(Self {
            #[cfg(not(windows))]
            native: backend,
            #[cfg(windows)]
            worker: backend,
            dimension: metadata.0,
            info: metadata.1,
            unc_names: metadata.2,
            compiled_threading: metadata.3,
            calls: AtomicUsize::new(0),
            recoverable: AtomicUsize::new(0),
        })
    }

    /// The `bs_model_info` string (compiler, Stan version, `STAN_THREADS`).
    pub fn info(&self) -> &str {
        &self.info
    }

    /// Effective call concurrency. Windows owned-one targets are always
    /// serialized, even when the DLL was compiled with `STAN_THREADS=true`.
    pub fn threading(&self) -> Threading {
        stan_threading(self.compiled_threading)
    }

    /// Threading capability compiled into the model DLL.
    pub fn compiled_threading(&self) -> Threading {
        self.compiled_threading
    }

    /// Effective execution backend. Windows always reports
    /// [`Execution::OwnedSerialised`], including for `STAN_THREADS=true`
    /// libraries.
    pub fn execution(&self) -> Execution {
        stan_execution(self.compiled_threading)
    }

    /// Stan's unconstrained parameter names (`bs_param_unc_names`, one per
    /// coordinate), or `None` when the library does not export them.
    pub fn param_unc_names(&self) -> Option<&[String]> {
        self.unc_names.as_deref()
    }

    /// Fused evaluations started so far.
    pub fn calls(&self) -> usize {
        self.calls.load(Ordering::Relaxed)
    }

    /// Evaluations that raised a Stan exception or returned a nonfinite log
    /// density or gradient (all mapped to zero density; see [`map_evaluation`]).
    pub fn recoverable_failures(&self) -> usize {
        self.recoverable.load(Ordering::Relaxed)
    }

    fn evaluate(&self, position: &[f64], gradient: &mut [f64]) -> Result<f64, TargetError> {
        #[cfg(not(windows))]
        {
            self.native.evaluate(position, gradient)
        }
        #[cfg(windows)]
        {
            self.worker.evaluate(position, gradient)
        }
    }

    #[cfg(not(windows))]
    fn evaluate_replica_unlocked(
        &self,
        position: &[f64],
        gradient: &mut [f64],
    ) -> Result<f64, TargetError> {
        self.calls.fetch_add(1, Ordering::Relaxed);
        let outcome = self.native.evaluate_unlocked(position, gradient);
        record_recoverable(&outcome, &self.recoverable);
        outcome
    }
}

fn record_recoverable(outcome: &Result<f64, TargetError>, recoverable: &AtomicUsize) {
    if outcome
        .as_ref()
        .is_err_and(|error| error.kind() == TargetErrorKind::Recoverable)
    {
        recoverable.fetch_add(1, Ordering::Relaxed);
    }
}

/// One evaluation lock per loaded library file (keyed by canonical path).
fn module_lock(model_so: &Path) -> Arc<Mutex<()>> {
    static LOCKS: OnceLock<Mutex<std::collections::HashMap<PathBuf, Weak<Mutex<()>>>>> =
        OnceLock::new();
    let key = std::fs::canonicalize(model_so).unwrap_or_else(|_| model_so.to_path_buf());
    let mut map = LOCKS
        .get_or_init(Default::default)
        .lock()
        .unwrap_or_else(|p| p.into_inner());
    if let Some(existing) = map.get(&key).and_then(Weak::upgrade) {
        return existing;
    }
    let fresh = Arc::new(Mutex::new(()));
    map.retain(|_, w| w.strong_count() > 0);
    map.insert(key, Arc::downgrade(&fresh));
    fresh
}

/// Map a BridgeStan evaluation that returned without an exception to the
/// [`Target`] contract.
///
/// A finite log density with a finite gradient is returned as is. A `-inf`,
/// `NaN` or `+inf` log density, or a finite log density whose gradient
/// contains a nonfinite element, is a [`TargetError::recoverable`]
/// zero-density result: the kernel refines the leaf and rejects it at the
/// finest level, exactly as it treats a Stan exception. This is the CmdStan
/// and nutpie convention (a rejected proposal, never an aborted run) and
/// avoids the run-killing `NaN` evaluations of models such as posteriordb's
/// `arma11` far from the typical set. The message names the cause.
pub fn map_evaluation(value: f64, gradient: &[f64]) -> Result<f64, TargetError> {
    if value == f64::NEG_INFINITY {
        return Err(TargetError::recoverable("stan log density is -inf"));
    }
    if !value.is_finite() {
        return Err(TargetError::recoverable(format!(
            "stan log density is {value}; treated as zero density"
        )));
    }
    if let Some(bad) = gradient.iter().find(|g| !g.is_finite()) {
        return Err(TargetError::recoverable(format!(
            "stan gradient contains {bad}; treated as zero density"
        )));
    }
    Ok(value)
}

fn take_error(err: *mut c_char, free: FreeErrorFn) -> String {
    if err.is_null() {
        return String::from("(no message)");
    }
    // SAFETY: BridgeStan allocated a NUL-terminated string; we copy then free it.
    let message = unsafe { CStr::from_ptr(err) }
        .to_string_lossy()
        .into_owned();
    // SAFETY: freed exactly once with the library's own deallocator.
    unsafe { free(err) };
    message
}

impl Target for StanTarget {
    fn dimension(&self) -> usize {
        self.dimension
    }

    fn parameter_names(&self) -> Option<Vec<String>> {
        self.unc_names.clone()
    }

    fn log_density_gradient(
        &self,
        position: &[f64],
        gradient: &mut [f64],
    ) -> Result<f64, TargetError> {
        if position.len() != self.dimension || gradient.len() != self.dimension {
            return Err(TargetError::new("position/gradient dimension mismatch"));
        }
        self.calls.fetch_add(1, Ordering::Relaxed);
        let outcome = self.evaluate(position, gradient);
        record_recoverable(&outcome, &self.recoverable);
        outcome
    }
}

/// A pool of independently loaded copies of one model library off Windows.
///
/// Each replica is the same `*_model.so` copied to a distinct file name in a
/// private cache and loaded separately, so each has its own global Stan
/// autodiff stack and may be evaluated by one thread at a time.
///
/// On Windows this type intentionally uses one effective [`StanTarget`] owned
/// worker regardless of the requested count. Calls from any number of sampler
/// threads are serialized through that worker. Multi-worker Windows execution
/// is out of scope until separately qualified; use [`Self::requested_replicas`]
/// to distinguish the requested and effective counts.
/// A call takes the first free replica (trying the one this thread used last
/// first, so steady-state dispatch is one uncontended `try_lock`); with at
/// least as many replicas as calling threads, evaluations never wait. The
/// per-call dispatch cost is ~50 ns against a >=0.5 µs Stan gradient.
///
/// With a `STAN_THREADS=true` library the replicas are still correct but
/// pointless; use [`StanTarget`] directly.
pub struct ReplicatedStanTarget {
    replicas: Vec<StanTarget>,
    // Dropped after the replicas (field order). Off Windows this removes
    // copies after their libraries unload; Windows cache copies are resident.
    _copies: ReplicaCopies,
    dimension: usize,
    requested_replicas: usize,
}

#[derive(Clone, Debug, PartialEq, Eq)]
struct ReplicaMetadata {
    dimension: usize,
    unc_names: Option<Vec<String>>,
    compiled_threading: Threading,
}

impl From<&StanTarget> for ReplicaMetadata {
    fn from(target: &StanTarget) -> Self {
        Self {
            dimension: target.dimension,
            unc_names: target.unc_names.clone(),
            compiled_threading: target.compiled_threading,
        }
    }
}

fn validate_replica_metadata(metadata: &[ReplicaMetadata]) -> Result<(), LoadError> {
    let Some(expected) = metadata.first() else {
        return Err(LoadError::Invalid("no model replicas were loaded".into()));
    };
    for (index, observed) in metadata.iter().enumerate().skip(1) {
        if observed != expected {
            return Err(LoadError::Invalid(format!(
                "replica {index} metadata/capability differs from replica 0: \
                 expected {expected:?}, observed {observed:?}"
            )));
        }
    }
    Ok(())
}

#[cfg(not(windows))]
struct ReplicaCopies {
    dir: PathBuf,
    files: Vec<PathBuf>,
}

#[cfg(not(windows))]
impl Drop for ReplicaCopies {
    fn drop(&mut self) {
        for f in &self.files {
            let _ = std::fs::remove_file(f);
        }
        let _ = std::fs::remove_dir(&self.dir);
    }
}

#[cfg(not(windows))]
impl ReplicaCopies {
    fn prepare(model_so: &Path, replicas: usize) -> Result<Self, LoadError> {
        let dir = std::env::temp_dir().join(format!(
            "owalnuts-bridgestan-{}-{}",
            std::process::id(),
            NEXT_POOL_ID.fetch_add(1, Ordering::Relaxed)
        ));
        let mut copies = Self {
            dir: dir.clone(),
            files: Vec::new(),
        };
        if replicas > 0 {
            std::fs::create_dir_all(&dir).map_err(|e| LoadError::Invalid(e.to_string()))?;
            let stem = model_so
                .file_name()
                .map(|name| name.to_string_lossy().into_owned())
                .unwrap_or_else(|| "model.so".into());
            let bytes =
                std::fs::read(model_so).map_err(|error| LoadError::Invalid(error.to_string()))?;
            for replica in 0..replicas {
                let copy = dir.join(format!("replica{replica}-{stem}"));
                std::fs::write(&copy, &bytes)
                    .map_err(|error| LoadError::Invalid(error.to_string()))?;
                copies.files.push(copy);
            }
        }
        Ok(copies)
    }
}

#[cfg(windows)]
struct ReplicaCopies;

#[cfg(windows)]
impl ReplicaCopies {
    fn prepare(_model_so: &Path, _replicas: usize) -> Result<Self, LoadError> {
        Ok(Self)
    }
}

#[cfg(windows)]
struct ProcessReplicaCache {
    dir: PathBuf,
    _lease: File,
    copy_lock: Mutex<()>,
}

#[cfg(windows)]
impl ProcessReplicaCache {
    fn create(root: &Path) -> std::io::Result<Self> {
        const CLEANUP_GRACE: Duration = Duration::from_secs(60 * 60);

        std::fs::create_dir_all(root)?;
        cleanup_stale_cache_dirs(root, CLEANUP_GRACE);
        let nonce = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap_or_default()
            .as_nanos();
        let dir = (0..1000)
            .find_map(|attempt| {
                let candidate =
                    root.join(format!("process-{}-{nonce}-{attempt}", std::process::id()));
                match std::fs::create_dir(&candidate) {
                    Ok(()) => Some(Ok(candidate)),
                    Err(error) if error.kind() == std::io::ErrorKind::AlreadyExists => None,
                    Err(error) => Some(Err(error)),
                }
            })
            .transpose()?
            .ok_or_else(|| std::io::Error::other("could not allocate replica cache directory"))?;
        let lease_path = dir.join(".lease");
        let lease = match OpenOptions::new()
            .read(true)
            .write(true)
            .create_new(true)
            .open(&lease_path)
        {
            Ok(lease) => lease,
            Err(error) => {
                let _ = std::fs::remove_dir_all(&dir);
                return Err(error);
            }
        };
        if let Err(error) = lease.lock_exclusive() {
            drop(lease);
            let _ = std::fs::remove_dir_all(&dir);
            return Err(error);
        }
        Ok(Self {
            dir,
            _lease: lease,
            copy_lock: Mutex::new(()),
        })
    }

    fn digest(source: &Path) -> Result<String, LoadError> {
        let mut input =
            File::open(source).map_err(|error| LoadError::Invalid(error.to_string()))?;
        let mut hasher = Sha256::new();
        let mut buffer = [0_u8; 64 * 1024];
        loop {
            let count = input
                .read(&mut buffer)
                .map_err(|error| LoadError::Invalid(error.to_string()))?;
            if count == 0 {
                break;
            }
            hasher.update(&buffer[..count]);
        }
        Ok(format!("{:x}", hasher.finalize()))
    }

    fn model_copy(&self, source: &Path) -> Result<PathBuf, LoadError> {
        let digest = Self::digest(source)?;
        let extension = source
            .extension()
            .map(|extension| extension.to_string_lossy().into_owned())
            .unwrap_or_else(|| "dll".into());
        let _copy_guard = self
            .copy_lock
            .lock()
            .unwrap_or_else(|poisoned| poisoned.into_inner());
        let copy = self.dir.join(format!("{digest}-model.{extension}"));
        if copy.exists() {
            if Self::digest(&copy)? != digest {
                return Err(LoadError::Invalid(format!(
                    "cached model content does not match its identity: {}",
                    copy.display()
                )));
            }
            return Ok(copy);
        }
        let temporary = self.dir.join(format!(
            ".copy-{}-{}",
            std::process::id(),
            NEXT_POOL_ID.fetch_add(1, Ordering::Relaxed)
        ));
        if let Err(error) = std::fs::copy(source, &temporary) {
            let _ = std::fs::remove_file(&temporary);
            return Err(LoadError::Invalid(error.to_string()));
        }
        if Self::digest(&temporary)? != digest {
            let _ = std::fs::remove_file(&temporary);
            return Err(LoadError::Invalid(
                "model source changed while it was copied".into(),
            ));
        }
        if let Err(error) = std::fs::rename(&temporary, &copy) {
            let _ = std::fs::remove_file(&temporary);
            return Err(LoadError::Invalid(error.to_string()));
        }
        Ok(copy)
    }
}

#[cfg(windows)]
fn cache_dir_old_enough(path: &Path, minimum_age: Duration) -> bool {
    std::fs::metadata(path)
        .and_then(|metadata| metadata.modified())
        .ok()
        .and_then(|modified| modified.elapsed().ok())
        .is_some_and(|age| age >= minimum_age)
}

#[cfg(windows)]
fn cleanup_stale_cache_dirs(root: &Path, minimum_age: Duration) {
    let Ok(entries) = std::fs::read_dir(root) else {
        return;
    };
    for entry in entries.flatten() {
        let path = entry.path();
        if !path.is_dir() || !cache_dir_old_enough(&path, minimum_age) {
            continue;
        }
        let lease_path = path.join(".lease");
        match OpenOptions::new().read(true).write(true).open(lease_path) {
            Ok(lease) => {
                if lease.try_lock_exclusive().is_err() {
                    continue;
                }
                let _ = FileExt::unlock(&lease);
                drop(lease);
            }
            Err(error) if error.kind() == std::io::ErrorKind::NotFound => {}
            Err(_) => continue,
        }
        let _ = std::fs::remove_dir_all(path);
    }
}

#[cfg(windows)]
fn process_replica_cache() -> Result<&'static ProcessReplicaCache, LoadError> {
    static CACHE: OnceLock<Result<ProcessReplicaCache, String>> = OnceLock::new();

    CACHE
        .get_or_init(|| {
            let root = std::env::temp_dir().join("owalnuts-bridgestan-cache-v1");
            ProcessReplicaCache::create(&root).map_err(|error| error.to_string())
        })
        .as_ref()
        .map_err(|error| LoadError::Invalid(error.clone()))
}

#[cfg(not(windows))]
thread_local! {
    static PREFERRED_REPLICA: Cell<usize> = const { Cell::new(0) };
}

impl ReplicatedStanTarget {
    /// Load `replicas` independent copies of `model_so` (see
    /// [`StanTarget::load`] for the other arguments). `replicas` should be at
    /// least the number of threads that will call the target concurrently.
    /// Off Windows every replica, including replica 0, is copied from one
    /// in-memory source snapshot and deleted on drop. On Windows one
    /// content-addressed cached copy and resident module is reused for the
    /// life of the process.
    pub fn load(
        model_so: &Path,
        preload: &[PathBuf],
        data: Option<&str>,
        seed: u32,
        replicas: usize,
    ) -> Result<Self, LoadError> {
        let requested_replicas = replicas;
        #[cfg(not(windows))]
        let effective_replicas = requested_replicas.max(1);
        #[cfg(windows)]
        let effective_replicas = 1;
        let copies = ReplicaCopies::prepare(model_so, effective_replicas)?;
        let mut loaded = Vec::with_capacity(effective_replicas);
        #[cfg(windows)]
        loaded.push(StanTarget::load(model_so, preload, data, seed)?);
        #[cfg(not(windows))]
        for copy in &copies.files {
            loaded.push(StanTarget::load(copy, preload, data, seed)?);
        }
        validate_replica_metadata(&loaded.iter().map(ReplicaMetadata::from).collect::<Vec<_>>())?;
        let dimension = loaded[0].dimension();
        Ok(Self {
            replicas: loaded,
            _copies: copies,
            dimension,
            requested_replicas,
        })
    }

    /// Effective replicas. This is always one on Windows.
    pub fn replicas(&self) -> usize {
        self.effective_replicas()
    }

    /// Effective replica count after platform safety policy.
    pub fn effective_replicas(&self) -> usize {
        self.replicas.len()
    }

    /// Replica count requested by the caller before the Windows safety cap.
    pub fn requested_replicas(&self) -> usize {
        self.requested_replicas
    }

    /// The `bs_model_info` string of the library.
    pub fn info(&self) -> &str {
        self.replicas[0].info()
    }

    /// Effective call concurrency after replica and platform policy.
    pub fn threading(&self) -> Threading {
        replicated_threading(self.compiled_threading(), self.effective_replicas())
    }

    /// Threading capability compiled into the model library.
    pub fn compiled_threading(&self) -> Threading {
        self.replicas[0].compiled_threading()
    }

    /// Effective execution backend.
    pub fn execution(&self) -> Execution {
        replicated_execution(self.compiled_threading(), self.effective_replicas())
    }

    /// Stan's unconstrained parameter names (see [`StanTarget::param_unc_names`]).
    pub fn param_unc_names(&self) -> Option<&[String]> {
        self.replicas[0].param_unc_names()
    }

    /// Fused evaluations started so far, summed over replicas.
    pub fn calls(&self) -> usize {
        self.replicas.iter().map(StanTarget::calls).sum()
    }

    /// Evaluations that raised a Stan exception or returned `-inf`, summed.
    pub fn recoverable_failures(&self) -> usize {
        self.replicas
            .iter()
            .map(StanTarget::recoverable_failures)
            .sum()
    }
}

static NEXT_POOL_ID: AtomicUsize = AtomicUsize::new(0);

impl Target for ReplicatedStanTarget {
    fn dimension(&self) -> usize {
        self.dimension
    }

    fn parameter_names(&self) -> Option<Vec<String>> {
        self.replicas[0].parameter_names()
    }

    fn log_density_gradient(
        &self,
        position: &[f64],
        gradient: &mut [f64],
    ) -> Result<f64, TargetError> {
        if position.len() != self.dimension || gradient.len() != self.dimension {
            return Err(TargetError::new("position/gradient dimension mismatch"));
        }
        #[cfg(windows)]
        {
            self.replicas[0].log_density_gradient(position, gradient)
        }
        #[cfg(not(windows))]
        {
            let n = self.replicas.len();
            let start = PREFERRED_REPLICA.with(Cell::get) % n;
            for k in 0..n {
                let i = (start + k) % n;
                let r = &self.replicas[i];
                let guard = match r.native.serial.try_lock() {
                    Ok(g) => g,
                    Err(TryLockError::Poisoned(p)) => p.into_inner(),
                    Err(TryLockError::WouldBlock) => continue,
                };
                PREFERRED_REPLICA.with(|p| p.set(i));
                let out = r.evaluate_replica_unlocked(position, gradient);
                drop(guard);
                return out;
            }
            // Every replica is busy (more callers than replicas): wait for ours.
            let r = &self.replicas[start];
            let _guard = r.native.serial.lock().unwrap_or_else(|p| p.into_inner());
            r.evaluate_replica_unlocked(position, gradient)
        }
    }
}

/// Locate the BridgeStan source tree the Python package downloads
/// (`$BRIDGESTAN` or `~/.bridgestan/bridgestan-<version>`), used to find
/// `tbb.dll` on Windows.
pub fn bridgestan_home() -> Option<PathBuf> {
    if let Ok(p) = std::env::var("BRIDGESTAN") {
        return Some(PathBuf::from(p));
    }
    let home = std::env::var("USERPROFILE")
        .or_else(|_| std::env::var("HOME"))
        .ok()?;
    let root = Path::new(&home).join(".bridgestan");
    let mut versions: Vec<PathBuf> = std::fs::read_dir(&root)
        .ok()?
        .filter_map(|e| e.ok().map(|e| e.path()))
        .filter(|p| p.is_dir())
        .collect();
    versions.sort();
    versions.pop()
}

/// Libraries that must be resident before a Windows BridgeStan model loads.
pub fn default_preload() -> Vec<PathBuf> {
    let mut out = Vec::new();
    if cfg!(windows) {
        if let Some(home) = bridgestan_home() {
            let tbb = home.join("stan/lib/stan_math/lib/tbb/tbb.dll");
            if tbb.exists() {
                out.push(tbb);
            }
        }
    }
    out
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::sync::Arc;
    #[cfg(windows)]
    use std::{cell::RefCell, thread::ThreadId};

    struct DropProbe {
        name: &'static str,
        log: Arc<Mutex<Vec<&'static str>>>,
    }

    impl Drop for DropProbe {
        fn drop(&mut self) {
            self.log
                .lock()
                .unwrap_or_else(|poisoned| poisoned.into_inner())
                .push(self.name);
        }
    }

    #[cfg(windows)]
    type OperationLog = Arc<Mutex<Vec<(&'static str, ThreadId)>>>;

    #[cfg(windows)]
    fn log_operation(log: &OperationLog, operation: &'static str) {
        log.lock()
            .unwrap_or_else(|poisoned| poisoned.into_inner())
            .push((operation, thread::current().id()));
    }

    #[cfg(windows)]
    struct OwnerTlsProbe(OperationLog);

    #[cfg(windows)]
    impl Drop for OwnerTlsProbe {
        fn drop(&mut self) {
            log_operation(&self.0, "tls_destruct");
        }
    }

    #[cfg(windows)]
    thread_local! {
        #[allow(clippy::missing_const_for_thread_local)]
        static OWNER_TLS_PROBE: RefCell<Option<OwnerTlsProbe>> = RefCell::new(None);
    }

    #[cfg(windows)]
    struct FakeBackend {
        log: OperationLog,
        active: Arc<AtomicUsize>,
    }

    #[cfg(windows)]
    impl OwnedBackend for FakeBackend {
        fn metadata(&self) -> WorkerMetadata {
            log_operation(&self.log, "metadata");
            log_operation(&self.log, "names");
            WorkerMetadata {
                dimension: 2,
                info: "fake STAN_THREADS=false".into(),
                unc_names: Some(vec!["a".into(), "b".into()]),
                compiled_threading: Threading::Serialised,
            }
        }

        fn evaluate(&mut self, position: &[f64]) -> WorkerReply {
            log_operation(&self.log, "gradient");
            if position.first() == Some(&99.0) {
                panic!("fake native panic");
            }
            let mut gradient = position.iter().map(|value| -*value).collect();
            if position.first().is_some_and(|value| *value < 0.0) {
                log_operation(&self.log, "error_free");
                return WorkerReply {
                    gradient,
                    outcome: WorkerOutcome::Recoverable("fake domain error".into()),
                };
            }
            gradient.resize(2, 0.0);
            WorkerReply {
                gradient,
                outcome: WorkerOutcome::Success(-0.5 * position.iter().sum::<f64>()),
            }
        }
    }

    #[cfg(windows)]
    impl Drop for FakeBackend {
        fn drop(&mut self) {
            log_operation(&self.log, "model_destruct");
            self.active.fetch_sub(1, Ordering::SeqCst);
        }
    }

    #[cfg(windows)]
    fn start_fake_worker(
        log: OperationLog,
        active: Arc<AtomicUsize>,
    ) -> (OwnedClient, WorkerMetadata) {
        start_owned_worker(move || {
            OWNER_TLS_PROBE.with(|probe| {
                probe.replace(Some(OwnerTlsProbe(Arc::clone(&log))));
            });
            for operation in ["preload", "library_load", "symbol_load", "construct"] {
                log_operation(&log, operation);
            }
            active.fetch_add(1, Ordering::SeqCst);
            Ok(FakeBackend { log, active })
        })
        .unwrap()
    }

    #[test]
    fn model_is_dropped_before_its_libraries() {
        let log = Arc::new(Mutex::new(Vec::new()));
        let loaded = ModelAndLibraries {
            model: DropProbe {
                name: "model",
                log: Arc::clone(&log),
            },
            _libraries: DropProbe {
                name: "libraries",
                log: Arc::clone(&log),
            },
        };
        drop(loaded);
        assert_eq!(*log.lock().unwrap(), ["model", "libraries"]);
    }

    #[test]
    fn optional_parameter_names_are_none_when_null_or_malformed() {
        assert_eq!(
            parse_optional_names("alpha,beta", 2).unwrap(),
            Some(vec!["alpha".into(), "beta".into()])
        );
        let malformed = parse_optional_names("alpha", 2);
        assert_eq!(malformed.unwrap(), None);

        let null = optional_names_failure("null optional names");
        assert_eq!(null.unwrap(), None);
    }

    #[test]
    fn replica_metadata_validation_covers_dimension_names_and_capability() {
        let expected = ReplicaMetadata {
            dimension: 2,
            unc_names: Some(vec!["a".into(), "b".into()]),
            compiled_threading: Threading::Serialised,
        };
        assert!(validate_replica_metadata(&[expected.clone(), expected.clone()]).is_ok());
        for mismatched in [
            ReplicaMetadata {
                dimension: 3,
                ..expected.clone()
            },
            ReplicaMetadata {
                unc_names: None,
                ..expected.clone()
            },
            ReplicaMetadata {
                compiled_threading: Threading::Concurrent,
                ..expected.clone()
            },
        ] {
            assert!(validate_replica_metadata(&[expected.clone(), mismatched]).is_err());
        }
    }

    #[test]
    fn execution_distinguishes_capability_from_effective_backend() {
        #[cfg(windows)]
        {
            assert_eq!(stan_threading(Threading::Concurrent), Threading::Serialised);
            assert_eq!(
                replicated_threading(Threading::Concurrent, 1),
                Threading::Serialised
            );
            assert_eq!(
                stan_execution(Threading::Concurrent),
                Execution::OwnedSerialised
            );
            assert_eq!(
                replicated_execution(Threading::Concurrent, 4),
                Execution::OwnedSerialised
            );
        }
        #[cfg(not(windows))]
        {
            assert_eq!(stan_threading(Threading::Concurrent), Threading::Concurrent);
            assert_eq!(
                replicated_threading(Threading::Serialised, 4),
                Threading::Concurrent
            );
            assert_eq!(
                stan_execution(Threading::Concurrent),
                Execution::DirectConcurrent
            );
            assert_eq!(
                stan_execution(Threading::Serialised),
                Execution::DirectSerialised
            );
            assert_eq!(
                replicated_execution(Threading::Serialised, 4),
                Execution::ReplicatedConcurrent
            );
        }
    }

    #[cfg(windows)]
    fn test_directory(label: &str) -> PathBuf {
        std::env::temp_dir().join(format!(
            "owalnuts-bridgestan-test-{label}-{}-{}",
            std::process::id(),
            NEXT_POOL_ID.fetch_add(1, Ordering::Relaxed)
        ))
    }

    #[cfg(windows)]
    #[test]
    fn windows_library_registry_reuses_handle_across_concurrent_loads() {
        let before = resident_libraries()
            .lock()
            .unwrap_or_else(|poisoned| poisoned.into_inner())
            .len();
        let first = load_library(Path::new("kernel32.dll")).expect("load kernel32");
        let identity = Arc::as_ptr(&first.0);
        drop(first);
        thread::scope(|scope| {
            let handles: Vec<_> = (0..16)
                .map(|_| {
                    scope.spawn(|| {
                        (0..4)
                            .map(|_| {
                                let loaded = load_library(Path::new("kernel32.dll"))
                                    .expect("reload kernel32");
                                assert!(
                                    Arc::strong_count(&loaded.0) >= 2,
                                    "the process registry retains its own strong reference"
                                );
                                Arc::as_ptr(&loaded.0) as usize
                            })
                            .collect::<Vec<_>>()
                    })
                })
                .collect();
            for handle in handles {
                assert!(
                    handle
                        .join()
                        .unwrap()
                        .into_iter()
                        .all(|observed| observed == identity as usize)
                );
            }
        });
        let after = resident_libraries()
            .lock()
            .unwrap_or_else(|poisoned| poisoned.into_inner())
            .len();
        assert!(after == before || after == before + 1);
    }

    #[cfg(windows)]
    #[test]
    fn windows_replica_cache_handles_concurrent_reuse_replacement_and_cleanup() {
        let outer = test_directory("cache");
        let root = outer.join("cache");
        std::fs::create_dir_all(&outer).unwrap();
        let source = outer.join("source.dll");
        let original_bytes = b"not a real DLL; cache behavior only";
        let replacement_bytes = b"different real content of same-ish size";
        std::fs::write(&source, original_bytes).unwrap();

        let cache = ProcessReplicaCache::create(&root).unwrap();
        let cache_dir = cache.dir.clone();
        let first = cache.model_copy(&source).unwrap();
        let second = cache.model_copy(&source).unwrap();
        assert_eq!(first, second);
        assert!(first.exists());
        let plateau_files = std::fs::read_dir(&cache.dir).unwrap().count();
        thread::scope(|scope| {
            let handles: Vec<_> = (0..16)
                .map(|_| {
                    scope.spawn(|| {
                        (0..4)
                            .map(|_| cache.model_copy(&source).unwrap())
                            .collect::<Vec<_>>()
                    })
                })
                .collect();
            for handle in handles {
                assert!(
                    handle
                        .join()
                        .unwrap()
                        .into_iter()
                        .all(|observed| observed == first)
                );
            }
        });
        assert_eq!(
            std::fs::read_dir(&cache.dir).unwrap().count(),
            plateau_files
        );

        std::fs::write(&first, b"tampered cached model").unwrap();
        assert!(cache.model_copy(&source).is_err());
        std::fs::remove_file(&first).unwrap();
        let restored = cache.model_copy(&source).unwrap();
        assert_eq!(restored, first);

        assert_eq!(std::fs::read(&restored).unwrap(), original_bytes);
        std::fs::write(&source, replacement_bytes).unwrap();
        let changed = cache.model_copy(&source).unwrap();
        assert_ne!(changed, first);
        assert_eq!(std::fs::read(&first).unwrap(), original_bytes);
        assert_eq!(std::fs::read(&changed).unwrap(), replacement_bytes);

        cleanup_stale_cache_dirs(&root, Duration::ZERO);
        assert!(
            cache_dir.exists(),
            "an exclusively leased process cache must not be removed"
        );

        drop(cache);
        cleanup_stale_cache_dirs(&root, Duration::ZERO);
        assert!(
            !cache_dir.exists(),
            "a later process may remove an unlocked stale cache"
        );
        let _ = std::fs::remove_dir_all(outer);
    }

    #[cfg(windows)]
    #[test]
    fn owned_worker_runs_native_operations_on_one_thread_and_joins_tls() {
        let log = Arc::new(Mutex::new(Vec::new()));
        let active = Arc::new(AtomicUsize::new(0));
        let caller = thread::current().id();
        let (mut client, metadata) = start_fake_worker(Arc::clone(&log), Arc::clone(&active));
        assert_eq!(metadata.dimension, 2);
        assert_eq!(
            metadata.unc_names.as_deref(),
            Some(&["a".into(), "b".into()][..])
        );

        let mut gradient = [0.0; 2];
        let calls = AtomicUsize::new(0);
        let recoverable = AtomicUsize::new(0);
        calls.fetch_add(1, Ordering::Relaxed);
        let success = client.evaluate(&[2.0, 4.0], &mut gradient);
        record_recoverable(&success, &recoverable);
        assert_eq!(success.unwrap(), -3.0);
        assert_eq!(gradient, [-2.0, -4.0]);
        calls.fetch_add(1, Ordering::Relaxed);
        let error = client.evaluate(&[-1.0, 0.0], &mut gradient);
        record_recoverable(&error, &recoverable);
        assert_eq!(error.unwrap_err().kind(), TargetErrorKind::Recoverable);
        assert_eq!(calls.load(Ordering::Relaxed), 2);
        assert_eq!(recoverable.load(Ordering::Relaxed), 1);

        thread::scope(|scope| {
            let handles: Vec<_> = (0..16)
                .map(|value| {
                    let client = &client;
                    scope.spawn(move || {
                        let mut gradient = [0.0; 2];
                        client
                            .evaluate(&[value as f64, 1.0], &mut gradient)
                            .unwrap()
                    })
                })
                .collect();
            for handle in handles {
                assert!(handle.join().unwrap().is_finite());
            }
        });
        client.shutdown();
        assert_eq!(active.load(Ordering::SeqCst), 0);

        let operations = log.lock().unwrap();
        let owner = operations[0].1;
        assert_ne!(owner, caller);
        assert!(operations.iter().all(|(_, thread)| *thread == owner));
        let labels: Vec<_> = operations.iter().map(|(operation, _)| *operation).collect();
        assert!(labels.contains(&"preload"));
        assert!(labels.contains(&"library_load"));
        assert!(labels.contains(&"symbol_load"));
        assert!(labels.contains(&"construct"));
        assert!(labels.contains(&"metadata"));
        assert!(labels.contains(&"names"));
        assert!(labels.contains(&"gradient"));
        assert!(labels.contains(&"error_free"));
        let model_drop = labels
            .iter()
            .position(|label| *label == "model_destruct")
            .unwrap();
        let tls_drop = labels
            .iter()
            .position(|label| *label == "tls_destruct")
            .unwrap();
        assert!(model_drop < tls_drop);
        assert_eq!(labels.last(), Some(&"tls_destruct"));
    }

    #[cfg(windows)]
    #[test]
    fn owner_panic_becomes_fatal_and_drop_does_not_panic() {
        let log = Arc::new(Mutex::new(Vec::new()));
        let active = Arc::new(AtomicUsize::new(0));
        let (client, _) = start_fake_worker(log, Arc::clone(&active));
        let mut gradient = [0.0; 2];
        let error = client.evaluate(&[99.0, 0.0], &mut gradient).unwrap_err();
        assert_eq!(error.kind(), TargetErrorKind::Fatal);
        drop(client);
        assert_eq!(active.load(Ordering::SeqCst), 0);
    }

    #[cfg(windows)]
    #[test]
    fn load_failure_is_joined_before_return() {
        struct ExitProbe(Arc<AtomicUsize>);
        impl Drop for ExitProbe {
            fn drop(&mut self) {
                self.0.fetch_sub(1, Ordering::SeqCst);
            }
        }

        let active = Arc::new(AtomicUsize::new(0));
        let worker_active = Arc::clone(&active);
        let result = start_owned_worker::<FakeBackend, _>(move || {
            worker_active.fetch_add(1, Ordering::SeqCst);
            let _exit = ExitProbe(Arc::clone(&worker_active));
            Err(LoadError::Invalid("fake load failure".into()))
        });
        assert!(result.is_err());
        assert_eq!(active.load(Ordering::SeqCst), 0);
    }

    #[cfg(windows)]
    #[test]
    fn repeated_owned_load_drop_leaves_no_workers() {
        let active = Arc::new(AtomicUsize::new(0));
        for _ in 0..64 {
            let log = Arc::new(Mutex::new(Vec::new()));
            let (client, _) = start_fake_worker(log, Arc::clone(&active));
            assert_eq!(active.load(Ordering::SeqCst), 1);
            drop(client);
            assert_eq!(active.load(Ordering::SeqCst), 0);
        }
    }

    #[cfg(not(windows))]
    #[test]
    fn non_windows_replica_copies_are_deleted_on_drop() {
        let outer = std::env::temp_dir().join(format!(
            "owalnuts-bridgestan-test-copy-{}-{}",
            std::process::id(),
            NEXT_POOL_ID.fetch_add(1, Ordering::Relaxed)
        ));
        std::fs::create_dir_all(&outer).unwrap();
        let source = outer.join("source.so");
        std::fs::write(&source, b"copy behavior only").unwrap();
        let copies = ReplicaCopies::prepare(&source, 4).unwrap();
        let copy_dir = copies.dir.clone();
        assert_eq!(copies.files.len(), 4);
        std::fs::write(&source, b"replacement after snapshot").unwrap();
        assert!(
            copies
                .files
                .iter()
                .all(|copy| std::fs::read(copy).unwrap() == b"copy behavior only")
        );
        drop(copies);
        assert!(!copy_dir.exists());
        let _ = std::fs::remove_dir_all(outer);
    }
}
