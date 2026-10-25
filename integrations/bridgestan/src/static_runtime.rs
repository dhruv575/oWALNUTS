//! Opt-in Windows multi-replica dispatch for static-runtime BridgeStan DLLs.
//!
//! A stock Windows GNU build binds `libwinpthread-1.dll`, `libgcc_s_seh-1.dll`
//! and `libstdc++-6.dll` through the DLL search order (that is, through the
//! launching shell's PATH). With four concurrently evaluated replica modules
//! that configuration corrupted the heap (`STATUS_HEAP_CORRUPTION`) in
//! `STUDIES/bridgestan_windows_root_cause_v2..v4`, which is why Windows
//! defaults to one owned worker. Model and `tbb.dll` builds that link the
//! mingw runtime statically (`tools/build_static_runtime.py`) did not fault in
//! the same configuration, and removing the serialisation was worth 3-4x
//! sampling wall time with bit-identical draws.
//!
//! [`check_static_runtime`] reads the PE import tables of the model DLL and
//! every preload (no external tool) and passes only if
//!
//! * no file imports a mingw/GCC runtime DLL ([`is_mingw_runtime`]), and
//! * every non-system DLL the model or a preload imports is itself one of the
//!   preloads (matched by file name), so nothing else can be bound from PATH.
//!
//! [`WindowsDispatch::ConcurrentIfStaticRuntime`] uses multi-replica dispatch
//! only when that check passes; otherwise the owned worker is kept.

use crate::LoadError;
use std::path::{Path, PathBuf};

/// How a [`crate::ReplicatedStanTarget`] executes on Windows. Ignored
/// elsewhere (other platforms always dispatch to independent replicas).
#[derive(Clone, Copy, Debug, Default, PartialEq, Eq)]
pub enum WindowsDispatch {
    /// One owned worker per target, all owners serialised by the
    /// process-global native-call lock (the default).
    #[default]
    OwnedWorker,
    /// Independent replica modules called directly from the sampler threads,
    /// without the owned worker and the process-global lock, but only if
    /// [`check_static_runtime`] passes for the model and its preloads; the
    /// owned worker is used otherwise.
    ConcurrentIfStaticRuntime,
}

/// Options for [`crate::ReplicatedStanTarget::load_with_options`].
#[derive(Clone, Debug, Default, PartialEq, Eq)]
pub struct ReplicatedOptions {
    /// Windows execution policy; [`WindowsDispatch::OwnedWorker`] by default.
    pub windows_dispatch: WindowsDispatch,
}

impl ReplicatedOptions {
    /// Opt in to [`WindowsDispatch::ConcurrentIfStaticRuntime`].
    pub fn concurrent_if_static_runtime() -> Self {
        Self {
            windows_dispatch: WindowsDispatch::ConcurrentIfStaticRuntime,
        }
    }
}

/// One file's imports as read from its PE import tables.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct ImportedDlls {
    pub path: PathBuf,
    /// DLL names from the import and delay-import directories, as written.
    pub imports: Vec<String>,
}

/// Result of [`check_static_runtime`].
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct StaticRuntimeReport {
    /// The model followed by each preload, in order.
    pub files: Vec<ImportedDlls>,
    /// Human-readable reasons the check failed; empty when it passed.
    pub problems: Vec<String>,
}

impl StaticRuntimeReport {
    /// True when no mingw runtime import and no unresolved non-system import
    /// was found.
    pub fn passed(&self) -> bool {
        self.problems.is_empty()
    }
}

/// True for mingw-w64/GCC runtime DLL names that a static-runtime build must
/// not import (case-insensitive).
pub fn is_mingw_runtime(dll: &str) -> bool {
    let lower = dll.to_ascii_lowercase();
    [
        "libwinpthread",
        "libgcc_s",
        "libstdc++",
        "libgomp",
        "libatomic",
        "libquadmath",
        "libssp",
        "libgfortran",
        "libmcfgthread",
    ]
    .iter()
    .any(|prefix| lower.starts_with(prefix))
}

/// True for DLLs that Windows itself provides (loaded from System32 / the
/// known-DLL list, not from PATH).
pub fn is_system_dll(dll: &str) -> bool {
    let lower = dll.to_ascii_lowercase();
    if lower.starts_with("api-ms-win-") || lower.starts_with("ext-ms-") {
        return true;
    }
    matches!(
        lower.as_str(),
        "kernel32.dll"
            | "kernelbase.dll"
            | "ntdll.dll"
            | "msvcrt.dll"
            | "ucrtbase.dll"
            | "user32.dll"
            | "gdi32.dll"
            | "advapi32.dll"
            | "shell32.dll"
            | "shlwapi.dll"
            | "ole32.dll"
            | "oleaut32.dll"
            | "ws2_32.dll"
            | "bcrypt.dll"
            | "bcryptprimitives.dll"
            | "crypt32.dll"
            | "secur32.dll"
            | "userenv.dll"
            | "psapi.dll"
            | "dbghelp.dll"
            | "iphlpapi.dll"
            | "winmm.dll"
            | "version.dll"
            | "rpcrt4.dll"
            | "comdlg32.dll"
            | "synchronization.dll"
    )
}

/// Check that `model_so` and every `preload` are static-runtime builds whose
/// only non-system imports are satisfied by `preload` (see the module docs).
/// I/O and PE-format errors are returned as [`LoadError::Invalid`].
pub fn check_static_runtime(
    model_so: &Path,
    preload: &[PathBuf],
) -> Result<StaticRuntimeReport, LoadError> {
    let mut files = Vec::with_capacity(preload.len() + 1);
    for path in std::iter::once(model_so).chain(preload.iter().map(PathBuf::as_path)) {
        let bytes = std::fs::read(path)
            .map_err(|error| LoadError::Invalid(format!("{}: {error}", path.display())))?;
        let imports = pe_imported_dlls(&bytes)
            .map_err(|error| LoadError::Invalid(format!("{}: {error}", path.display())))?;
        files.push(ImportedDlls {
            path: path.to_path_buf(),
            imports,
        });
    }
    Ok(evaluate_imports(files))
}

/// The pure decision of [`check_static_runtime`] over already-read imports.
pub fn evaluate_imports(files: Vec<ImportedDlls>) -> StaticRuntimeReport {
    let provided: Vec<String> = files
        .iter()
        .skip(1)
        .filter_map(|file| file.path.file_name())
        .map(|name| name.to_string_lossy().to_ascii_lowercase())
        .collect();
    let mut problems = Vec::new();
    for file in &files {
        for dll in &file.imports {
            if is_mingw_runtime(dll) {
                problems.push(format!(
                    "{} imports mingw runtime {dll}",
                    file.path.display()
                ));
            } else if !is_system_dll(dll) && !provided.contains(&dll.to_ascii_lowercase()) {
                problems.push(format!(
                    "{} imports {dll}, which is neither a system DLL nor a preload",
                    file.path.display()
                ));
            }
        }
    }
    StaticRuntimeReport { files, problems }
}

fn u16_at(bytes: &[u8], offset: usize) -> Result<u16, String> {
    bytes
        .get(offset..offset + 2)
        .map(|b| u16::from_le_bytes([b[0], b[1]]))
        .ok_or_else(|| format!("truncated PE file at offset {offset:#x}"))
}

fn u32_at(bytes: &[u8], offset: usize) -> Result<u32, String> {
    bytes
        .get(offset..offset + 4)
        .map(|b| u32::from_le_bytes([b[0], b[1], b[2], b[3]]))
        .ok_or_else(|| format!("truncated PE file at offset {offset:#x}"))
}

struct Section {
    virtual_address: u32,
    virtual_size: u32,
    raw_size: u32,
    raw_offset: u32,
}

fn rva_to_offset(sections: &[Section], rva: u32) -> Result<usize, String> {
    for s in sections {
        let span = s.virtual_size.max(s.raw_size);
        if rva >= s.virtual_address && rva < s.virtual_address.saturating_add(span) {
            return Ok((rva - s.virtual_address + s.raw_offset) as usize);
        }
    }
    Err(format!("RVA {rva:#x} is outside every section"))
}

fn c_string_at(bytes: &[u8], offset: usize) -> Result<String, String> {
    let tail = bytes
        .get(offset..)
        .ok_or_else(|| format!("string offset {offset:#x} out of range"))?;
    let end = tail
        .iter()
        .position(|&b| b == 0)
        .ok_or("unterminated DLL name")?;
    String::from_utf8(tail[..end].to_vec()).map_err(|_| "non-UTF-8 DLL name".into())
}

/// DLL names in the import (directory 1) and delay-import (directory 13)
/// tables of a PE32/PE32+ image.
pub fn pe_imported_dlls(bytes: &[u8]) -> Result<Vec<String>, String> {
    if bytes.get(0..2) != Some(b"MZ") {
        return Err("not a PE file (no MZ header)".into());
    }
    let pe = u32_at(bytes, 0x3c)? as usize;
    if bytes.get(pe..pe + 4) != Some(b"PE\0\0") {
        return Err("not a PE file (no PE signature)".into());
    }
    let coff = pe + 4;
    let section_count = u16_at(bytes, coff + 2)? as usize;
    let optional_size = u16_at(bytes, coff + 16)? as usize;
    let optional = coff + 20;
    let directories = match u16_at(bytes, optional)? {
        0x10b => optional + 96,
        0x20b => optional + 112,
        magic => return Err(format!("unknown optional-header magic {magic:#x}")),
    };
    let directory_count = u32_at(bytes, directories - 4)? as usize;
    let mut sections = Vec::with_capacity(section_count);
    let table = optional + optional_size;
    for i in 0..section_count {
        let base = table + 40 * i;
        sections.push(Section {
            virtual_size: u32_at(bytes, base + 8)?,
            virtual_address: u32_at(bytes, base + 12)?,
            raw_size: u32_at(bytes, base + 16)?,
            raw_offset: u32_at(bytes, base + 20)?,
        });
    }
    let directory = |index: usize| -> Result<Option<u32>, String> {
        if index >= directory_count {
            return Ok(None);
        }
        let rva = u32_at(bytes, directories + 8 * index)?;
        Ok((rva != 0).then_some(rva))
    };
    let mut names = Vec::new();
    if let Some(rva) = directory(1)? {
        let mut entry = rva_to_offset(&sections, rva)?;
        loop {
            let name_rva = u32_at(bytes, entry + 12)?;
            let first_thunk = u32_at(bytes, entry + 16)?;
            if name_rva == 0 && first_thunk == 0 {
                break;
            }
            names.push(c_string_at(bytes, rva_to_offset(&sections, name_rva)?)?);
            entry += 20;
        }
    }
    if let Some(rva) = directory(13)? {
        let mut entry = rva_to_offset(&sections, rva)?;
        loop {
            let attributes = u32_at(bytes, entry)?;
            let name = u32_at(bytes, entry + 4)?;
            if attributes == 0 && name == 0 {
                break;
            }
            names.push(c_string_at(bytes, rva_to_offset(&sections, name)?)?);
            entry += 32;
        }
    }
    Ok(names)
}

#[cfg(test)]
mod tests {
    use super::*;

    /// A minimal PE32+ image: one section at RVA 0x1000 / file offset 0x200
    /// holding an import directory for `dlls`.
    fn synthetic_pe(dlls: &[&str]) -> Vec<u8> {
        let mut b = vec![0u8; 0x200];
        b[0..2].copy_from_slice(b"MZ");
        b[0x3c..0x40].copy_from_slice(&0x40u32.to_le_bytes());
        b[0x40..0x44].copy_from_slice(b"PE\0\0");
        let coff = 0x44;
        b[coff + 2..coff + 4].copy_from_slice(&1u16.to_le_bytes()); // sections
        let optional_size: u16 = 112 + 16 * 8;
        b[coff + 16..coff + 18].copy_from_slice(&optional_size.to_le_bytes());
        let optional = coff + 20;
        b[optional..optional + 2].copy_from_slice(&0x20bu16.to_le_bytes());
        let dirs = optional + 112;
        b[dirs - 4..dirs].copy_from_slice(&16u32.to_le_bytes());
        b[dirs + 8..dirs + 12].copy_from_slice(&0x1000u32.to_le_bytes()); // import dir
        let table = optional + optional_size as usize;
        // section: virtual size, RVA, raw size, raw offset
        b[table + 8..table + 12].copy_from_slice(&0x200u32.to_le_bytes());
        b[table + 12..table + 16].copy_from_slice(&0x1000u32.to_le_bytes());
        b[table + 16..table + 20].copy_from_slice(&0x200u32.to_le_bytes());
        b[table + 20..table + 24].copy_from_slice(&0x200u32.to_le_bytes());
        let mut section = vec![0u8; 0x200];
        let names_at = 20 * (dlls.len() + 1);
        let mut cursor = names_at;
        for (i, dll) in dlls.iter().enumerate() {
            let entry = 20 * i;
            let name_rva = 0x1000 + cursor as u32;
            section[entry + 12..entry + 16].copy_from_slice(&name_rva.to_le_bytes());
            section[entry + 16..entry + 20].copy_from_slice(&0x1100u32.to_le_bytes());
            section[cursor..cursor + dll.len()].copy_from_slice(dll.as_bytes());
            cursor += dll.len() + 1;
        }
        b.extend_from_slice(&section);
        b
    }

    #[test]
    fn parses_synthetic_import_table() {
        let pe = synthetic_pe(&["KERNEL32.dll", "libwinpthread-1.dll", "tbb.dll"]);
        assert_eq!(
            pe_imported_dlls(&pe).unwrap(),
            ["KERNEL32.dll", "libwinpthread-1.dll", "tbb.dll"]
        );
        assert!(pe_imported_dlls(b"not a pe").is_err());
    }

    fn file(path: &str, imports: &[&str]) -> ImportedDlls {
        ImportedDlls {
            path: PathBuf::from(path),
            imports: imports.iter().map(|s| s.to_string()).collect(),
        }
    }

    #[test]
    fn static_runtime_decision() {
        let ok = evaluate_imports(vec![
            file(
                "m_model.so",
                &["KERNEL32.dll", "api-ms-win-crt-heap-l1-1-0.dll", "tbb.dll"],
            ),
            file("x/tbb.dll", &["KERNEL32.dll", "msvcrt.dll"]),
        ]);
        assert!(ok.passed(), "{:?}", ok.problems);

        let dynamic_model = evaluate_imports(vec![
            file(
                "m_model.so",
                &["KERNEL32.dll", "libwinpthread-1.dll", "tbb.dll"],
            ),
            file("x/tbb.dll", &["KERNEL32.dll"]),
        ]);
        assert!(!dynamic_model.passed());

        let stock_tbb = evaluate_imports(vec![
            file("m_model.so", &["KERNEL32.dll", "tbb.dll"]),
            file("x/tbb.dll", &["libgcc_s_seh-1.dll", "libstdc++-6.dll"]),
        ]);
        assert_eq!(stock_tbb.problems.len(), 2);

        let tbb_not_preloaded = evaluate_imports(vec![file("m_model.so", &["tbb.dll"])]);
        assert!(!tbb_not_preloaded.passed());
    }

    #[test]
    fn runtime_and_system_names() {
        for dll in [
            "libwinpthread-1.dll",
            "LIBGCC_S_SEH-1.DLL",
            "libstdc++-6.dll",
            "libgomp-1.dll",
        ] {
            assert!(is_mingw_runtime(dll), "{dll}");
        }
        assert!(!is_mingw_runtime("tbb.dll"));
        assert!(is_system_dll("api-ms-win-crt-runtime-l1-1-0.dll"));
        assert!(is_system_dll("KERNEL32.dll"));
        assert!(!is_system_dll("tbb.dll"));
    }

    #[test]
    fn default_dispatch_is_owned_worker() {
        assert_eq!(
            ReplicatedOptions::default().windows_dispatch,
            WindowsDispatch::OwnedWorker
        );
        assert_eq!(
            ReplicatedOptions::concurrent_if_static_runtime().windows_dispatch,
            WindowsDispatch::ConcurrentIfStaticRuntime
        );
    }

    #[cfg(windows)]
    #[test]
    fn reads_this_test_executable() {
        let exe = std::env::current_exe().unwrap();
        let imports = pe_imported_dlls(&std::fs::read(exe).unwrap()).unwrap();
        assert!(
            imports
                .iter()
                .any(|d| d.eq_ignore_ascii_case("kernel32.dll"))
        );
    }

    #[cfg(windows)]
    #[test]
    fn missing_file_is_an_error_not_a_pass() {
        let missing = std::env::temp_dir().join("owalnuts-no-such-model.so");
        assert!(check_static_runtime(&missing, &[]).is_err());
    }
}
