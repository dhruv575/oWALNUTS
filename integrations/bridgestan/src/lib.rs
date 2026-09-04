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
//!   the previous fatal mapping. Only a failed dimension check remains fatal.
//! * Thread safety: with `STAN_THREADS=true` Stan's autodiff stack is
//!   thread-local and one model instance may be evaluated from many threads
//!   concurrently, which is what the parallel facade entry points do. The
//!   constructor reads `bs_model_info` and, if the library was not built with
//!   `STAN_THREADS=true`, serialises every evaluation through a mutex shared
//!   by all `StanTarget`s loaded from that file (same path, same module, same
//!   global autodiff stack) and reports [`StanTarget::threading`] as
//!   [`Threading::Serialised`].
//! * **Do not build with `STAN_THREADS=true` on Windows/mingw-w64.** GCC on
//!   mingw-w64 implements `__thread` with emulated TLS (`__emutls_get_address`
//!   on every access), and Stan Math touches its thread-local autodiff stack
//!   for every node it records. Measured on the posteriordb models
//!   (`STUDIES/posteriordb_bench_v1/artifacts/wall-gap/`): a threaded build
//!   costs 9–16x more per gradient than the default build (arK 120 vs 12.8 µs,
//!   hmm_example 445 vs 28 µs, eight schools 6.2 vs 0.59 µs); the default
//!   build matches CmdStan's per-gradient cost. Build without `STAN_THREADS`
//!   and use [`ReplicatedStanTarget`], which loads one copy of the library per
//!   concurrent thread (distinct file paths are distinct modules with their
//!   own global autodiff stack) and dispatches each call to a free replica.
//! * On Windows, model and preload DLLs are process-lifetime residents. This
//!   prevents native TLS destructor callbacks from reaching unloaded code
//!   after model drop. Model objects are still destructed normally. Replica
//!   copies use a process-private content-addressed cache with an exclusive
//!   process lease; repeated same-model loads reuse modules and later
//!   processes clean stale unlocked directories. Non-Windows libraries still
//!   unload, and their replica copies are deleted, on target drop.
#![deny(unsafe_op_in_unsafe_fn)]

use libloading::{Library, Symbol};
use owalnuts::walnutpie::{Target, TargetError};
use std::{
    cell::Cell,
    ffi::{CStr, CString, c_char, c_int, c_uint},
    fmt,
    ops::Deref,
    path::{Path, PathBuf},
    sync::atomic::{AtomicUsize, Ordering},
    sync::{Arc, Mutex, OnceLock, TryLockError, Weak},
};
#[cfg(windows)]
use std::{
    collections::HashMap,
    fs::{File, OpenOptions},
    io::Read,
    time::{Duration, SystemTime, UNIX_EPOCH},
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
    static LIBRARIES: OnceLock<Mutex<HashMap<PathBuf, Arc<Library>>>> = OnceLock::new();

    let key = std::fs::canonicalize(path).unwrap_or_else(|_| path.to_path_buf());
    let mut libraries = LIBRARIES
        .get_or_init(Default::default)
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

/// How concurrent evaluations are executed.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Threading {
    /// Library built with `STAN_THREADS=true`; evaluations run concurrently.
    Concurrent,
    /// Library built without `STAN_THREADS`; evaluations are serialised.
    Serialised,
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
    loaded: ModelAndLibraries<ModelHandle, LoadedLibraries>,
    dimension: usize,
    info: String,
    unc_names: Option<Vec<String>>,
    threading: Threading,
    /// Shared by every `StanTarget` loaded from the same file: without
    /// `STAN_THREADS` the autodiff stack is a global of the *module*, and
    /// Windows/POSIX return the same module for the same path.
    serial: Arc<Mutex<()>>,
    calls: AtomicUsize,
    recoverable: AtomicUsize,
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
// serialised by `StanTarget::serial` otherwise.
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

impl StanTarget {
    /// Load `model_so` (a BridgeStan `*_model.so`), preloading each library in
    /// `preload` first (on Windows, `tbb.dll` from
    /// `stan/lib/stan_math/lib/tbb` must be resident before the model loads),
    /// and construct the model with CmdStan-JSON `data` and `seed`.
    pub fn load(
        model_so: &Path,
        preload: &[PathBuf],
        data: Option<&str>,
        seed: u32,
    ) -> Result<Self, LoadError> {
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
        let info = unsafe { CStr::from_ptr(info_fn(ptr)) }
            .to_string_lossy()
            .into_owned();
        // SAFETY: model pointer is valid.
        let dimension = unsafe { unc_num(ptr) };
        if dimension <= 0 {
            return Err(LoadError::Invalid(format!(
                "bs_param_unc_num returned {dimension}"
            )));
        }
        let threading = if info.contains("STAN_THREADS=true") {
            Threading::Concurrent
        } else {
            Threading::Serialised
        };
        let unc_names = unc_names_fn.and_then(|f| {
            // SAFETY: model pointer is valid; the string is owned by the model.
            let raw = unsafe { f(ptr) };
            if raw.is_null() {
                return None;
            }
            // SAFETY: BridgeStan returns a NUL-terminated string.
            let joined = unsafe { CStr::from_ptr(raw) }.to_string_lossy();
            let names: Vec<String> = joined
                .split(',')
                .filter(|n| !n.is_empty())
                .map(str::to_owned)
                .collect();
            (names.len() == dimension as usize).then_some(names)
        });
        Ok(Self {
            loaded: ModelAndLibraries {
                model,
                _libraries: LoadedLibraries {
                    _library: library,
                    _preloaded: preloaded,
                },
            },
            dimension: dimension as usize,
            info,
            unc_names,
            threading,
            serial: module_lock(model_so),
            calls: AtomicUsize::new(0),
            recoverable: AtomicUsize::new(0),
        })
    }

    /// The `bs_model_info` string (compiler, Stan version, `STAN_THREADS`).
    pub fn info(&self) -> &str {
        &self.info
    }

    pub fn threading(&self) -> Threading {
        self.threading
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
        let mut value = f64::NAN;
        let mut err: *mut c_char = std::ptr::null_mut();
        // SAFETY: `position` and `gradient` have `dimension` elements (checked
        // by the caller), the model pointer is valid, and `err` is a writable
        // slot that we free if set.
        let rc = unsafe {
            (self.loaded.model.log_density_gradient)(
                self.loaded.model.ptr,
                false,
                true,
                position.as_ptr(),
                &mut value,
                gradient.as_mut_ptr(),
                &mut err,
            )
        };
        let outcome = if rc != 0 {
            let message = take_error(err, self.loaded.model.free_error);
            Err(TargetError::recoverable(format!(
                "stan exception: {message}"
            )))
        } else {
            map_evaluation(value, gradient)
        };
        if outcome.is_err() {
            self.recoverable.fetch_add(1, Ordering::Relaxed);
        }
        outcome
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
        match self.threading {
            Threading::Concurrent => self.evaluate(position, gradient),
            Threading::Serialised => {
                let _guard = self.serial.lock().unwrap_or_else(|p| p.into_inner());
                self.evaluate(position, gradient)
            }
        }
    }
}

/// A pool of independently loaded copies of one model library, for
/// libraries built *without* `STAN_THREADS` (the fast build on Windows, see
/// the module docs).
///
/// Each replica is the same `*_model.so` copied to a distinct file name in a
/// private cache and loaded separately, so each has its own global Stan
/// autodiff stack and may be evaluated by one thread at a time. On Windows,
/// the process-private cache is content-addressed and reused by later loads of
/// the same model in this process. Its files remain while their modules are
/// resident and are removed by a later process after its lease check proves
/// the creating process has exited. Other platforms retain unload-and-delete
/// behavior on target drop.
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
        if replicas > 1 {
            std::fs::create_dir_all(&dir).map_err(|e| LoadError::Invalid(e.to_string()))?;
            let stem = model_so
                .file_name()
                .map(|name| name.to_string_lossy().into_owned())
                .unwrap_or_else(|| "model.so".into());
            for replica in 1..replicas {
                let copy = dir.join(format!("replica{replica}-{stem}"));
                std::fs::copy(model_so, &copy).map_err(|e| LoadError::Invalid(e.to_string()))?;
                copies.files.push(copy);
            }
        }
        Ok(copies)
    }
}

#[cfg(windows)]
struct ReplicaCopies {
    files: Vec<PathBuf>,
}

#[cfg(windows)]
impl ReplicaCopies {
    fn prepare(model_so: &Path, replicas: usize) -> Result<Self, LoadError> {
        let files = if replicas > 1 {
            process_replica_cache()?.copies(model_so, replicas)?
        } else {
            Vec::new()
        };
        Ok(Self { files })
    }
}

#[cfg(windows)]
struct DigestRecord {
    length: u64,
    modified: Option<SystemTime>,
    digest: String,
}

#[cfg(windows)]
struct ProcessReplicaCache {
    dir: PathBuf,
    _lease: File,
    copy_lock: Mutex<()>,
    digests: Mutex<HashMap<PathBuf, DigestRecord>>,
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
            digests: Mutex::new(HashMap::new()),
        })
    }

    fn digest(&self, source: &Path) -> Result<String, LoadError> {
        let key = std::fs::canonicalize(source).unwrap_or_else(|_| source.to_path_buf());
        let metadata =
            std::fs::metadata(source).map_err(|error| LoadError::Invalid(error.to_string()))?;
        let modified = metadata.modified().ok();
        {
            let digests = self
                .digests
                .lock()
                .unwrap_or_else(|poisoned| poisoned.into_inner());
            if let Some(record) = digests.get(&key)
                && record.length == metadata.len()
                && record.modified == modified
            {
                return Ok(record.digest.clone());
            }
        }
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
        let digest = format!("{:x}", hasher.finalize());
        self.digests
            .lock()
            .unwrap_or_else(|poisoned| poisoned.into_inner())
            .insert(
                key,
                DigestRecord {
                    length: metadata.len(),
                    modified,
                    digest: digest.clone(),
                },
            );
        Ok(digest)
    }

    fn copies(&self, source: &Path, replicas: usize) -> Result<Vec<PathBuf>, LoadError> {
        let digest = self.digest(source)?;
        let extension = source
            .extension()
            .map(|extension| extension.to_string_lossy().into_owned())
            .unwrap_or_else(|| "dll".into());
        let _copy_guard = self
            .copy_lock
            .lock()
            .unwrap_or_else(|poisoned| poisoned.into_inner());
        let mut copies = Vec::with_capacity(replicas.saturating_sub(1));
        for replica in 1..replicas {
            let copy = self
                .dir
                .join(format!("{digest}-replica-{replica}.{extension}"));
            if !copy.exists() {
                let temporary = self.dir.join(format!(
                    ".copy-{}-{}",
                    std::process::id(),
                    NEXT_POOL_ID.fetch_add(1, Ordering::Relaxed)
                ));
                if let Err(error) = std::fs::copy(source, &temporary) {
                    let _ = std::fs::remove_file(&temporary);
                    return Err(LoadError::Invalid(error.to_string()));
                }
                if let Err(error) = std::fs::rename(&temporary, &copy) {
                    let _ = std::fs::remove_file(&temporary);
                    return Err(LoadError::Invalid(error.to_string()));
                }
            }
            copies.push(copy);
        }
        Ok(copies)
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

thread_local! {
    static PREFERRED_REPLICA: Cell<usize> = const { Cell::new(0) };
}

impl ReplicatedStanTarget {
    /// Load `replicas` independent copies of `model_so` (see
    /// [`StanTarget::load`] for the other arguments). `replicas` should be at
    /// least the number of threads that will call the target concurrently.
    /// Replica 0 is the original file; replicas 1.. are copies made under a
    /// process-private cache. On Windows, same-content replica paths and
    /// resident modules are reused for the life of the process; elsewhere the
    /// copies are deleted on drop.
    pub fn load(
        model_so: &Path,
        preload: &[PathBuf],
        data: Option<&str>,
        seed: u32,
        replicas: usize,
    ) -> Result<Self, LoadError> {
        let replicas = replicas.max(1);
        let copies = ReplicaCopies::prepare(model_so, replicas)?;
        let mut loaded = Vec::with_capacity(replicas);
        loaded.push(StanTarget::load(model_so, preload, data, seed)?);
        for copy in &copies.files {
            loaded.push(StanTarget::load(copy, preload, data, seed)?);
        }
        let dimension = loaded[0].dimension();
        Ok(Self {
            replicas: loaded,
            _copies: copies,
            dimension,
        })
    }

    pub fn replicas(&self) -> usize {
        self.replicas.len()
    }

    /// The `bs_model_info` string of the library.
    pub fn info(&self) -> &str {
        self.replicas[0].info()
    }

    pub fn threading(&self) -> Threading {
        self.replicas[0].threading()
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
        let n = self.replicas.len();
        let start = PREFERRED_REPLICA.with(Cell::get) % n;
        for k in 0..n {
            let i = (start + k) % n;
            let r = &self.replicas[i];
            let guard = match r.serial.try_lock() {
                Ok(g) => g,
                Err(TryLockError::Poisoned(p)) => p.into_inner(),
                Err(TryLockError::WouldBlock) => continue,
            };
            PREFERRED_REPLICA.with(|p| p.set(i));
            r.calls.fetch_add(1, Ordering::Relaxed);
            let out = r.evaluate(position, gradient);
            drop(guard);
            return out;
        }
        // Every replica is busy (more callers than replicas): wait for ours.
        let r = &self.replicas[start];
        let _guard = r.serial.lock().unwrap_or_else(|p| p.into_inner());
        r.calls.fetch_add(1, Ordering::Relaxed);
        r.evaluate(position, gradient)
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
    fn windows_library_registry_keeps_and_reuses_resident_handle() {
        let first = load_library(Path::new("kernel32.dll")).expect("load kernel32");
        let identity = Arc::as_ptr(&first.0);
        drop(first);
        let second = load_library(Path::new("kernel32.dll")).expect("reload kernel32");
        assert_eq!(identity, Arc::as_ptr(&second.0));
        assert!(
            Arc::strong_count(&second.0) >= 2,
            "the process registry retains its own strong reference"
        );
    }

    #[cfg(windows)]
    #[test]
    fn windows_replica_cache_reuses_copies_and_cleans_only_unleased_dirs() {
        let outer = test_directory("cache");
        let root = outer.join("cache");
        std::fs::create_dir_all(&outer).unwrap();
        let source = outer.join("source.dll");
        std::fs::write(&source, b"not a real DLL; cache behavior only").unwrap();

        let cache = ProcessReplicaCache::create(&root).unwrap();
        let cache_dir = cache.dir.clone();
        let first = cache.copies(&source, 4).unwrap();
        let second = cache.copies(&source, 4).unwrap();
        assert_eq!(first, second);
        assert_eq!(first.len(), 3);
        assert!(first.iter().all(|copy| copy.exists()));

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
        assert_eq!(copies.files.len(), 3);
        drop(copies);
        assert!(!copy_dir.exists());
        let _ = std::fs::remove_dir_all(outer);
    }
}
