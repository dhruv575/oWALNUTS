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
//!   finest level, is rejected. A returned `-inf` log density is treated the
//!   same way. `NaN`/`+inf` values or nonfinite gradients are fatal.
//! * Thread safety: with `STAN_THREADS=true` Stan's autodiff stack is
//!   thread-local and one model instance may be evaluated from many threads
//!   concurrently, which is what the parallel facade entry points do. The
//!   constructor reads `bs_model_info` and, if the library was not built with
//!   `STAN_THREADS=true`, serialises every evaluation through a mutex and
//!   reports [`StanTarget::threading`] as [`Threading::Serialised`].
#![deny(unsafe_op_in_unsafe_fn)]

use libloading::{Library, Symbol};
use owalnuts::walnutpie::{Target, TargetError};
use std::{
    ffi::{CStr, CString, c_char, c_int, c_uint},
    fmt,
    path::{Path, PathBuf},
    sync::Mutex,
    sync::atomic::{AtomicUsize, Ordering},
};

#[repr(C)]
struct BsModel {
    _private: [u8; 0],
}

type ConstructFn = unsafe extern "C" fn(*const c_char, c_uint, *mut *mut c_char) -> *mut BsModel;
type DestructFn = unsafe extern "C" fn(*mut BsModel);
type FreeErrorFn = unsafe extern "C" fn(*mut c_char);
type InfoFn = unsafe extern "C" fn(*const BsModel) -> *const c_char;
type UncNumFn = unsafe extern "C" fn(*const BsModel) -> c_int;
type LogDensityGradientFn = unsafe extern "C" fn(
    *const BsModel,
    bool,
    bool,
    *const f64,
    *mut f64,
    *mut f64,
    *mut *mut c_char,
) -> c_int;

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
    // Field order matters: the model must be destructed before the library
    // (and any preloaded dependency) is unloaded. Rust drops fields in
    // declaration order.
    model: ModelHandle,
    _library: Library,
    _preloaded: Vec<Library>,
    dimension: usize,
    info: String,
    threading: Threading,
    serial: Mutex<()>,
    calls: AtomicUsize,
    recoverable: AtomicUsize,
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
            // SAFETY: loading a foreign shared library runs its initialisers;
            // these are the TBB/pthread runtimes the model was linked against.
            preloaded.push(unsafe { Library::new(dep) }?);
        }
        // SAFETY: same as above for the model library itself.
        let library = unsafe { Library::new(model_so) }?;
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
        Ok(Self {
            model,
            _library: library,
            _preloaded: preloaded,
            dimension: dimension as usize,
            info,
            threading,
            serial: Mutex::new(()),
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

    /// Fused evaluations started so far.
    pub fn calls(&self) -> usize {
        self.calls.load(Ordering::Relaxed)
    }

    /// Evaluations that raised a Stan exception or returned `-inf`.
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
            (self.model.log_density_gradient)(
                self.model.ptr,
                false,
                true,
                position.as_ptr(),
                &mut value,
                gradient.as_mut_ptr(),
                &mut err,
            )
        };
        if rc != 0 {
            let message = take_error(err, self.model.free_error);
            self.recoverable.fetch_add(1, Ordering::Relaxed);
            return Err(TargetError::recoverable(message));
        }
        if value == f64::NEG_INFINITY {
            self.recoverable.fetch_add(1, Ordering::Relaxed);
            return Err(TargetError::recoverable("stan log density is -inf"));
        }
        if !value.is_finite() {
            return Err(TargetError::new(format!("stan log density is {value}")));
        }
        if let Some(bad) = gradient.iter().find(|g| !g.is_finite()) {
            return Err(TargetError::new(format!("stan gradient contains {bad}")));
        }
        Ok(value)
    }
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
