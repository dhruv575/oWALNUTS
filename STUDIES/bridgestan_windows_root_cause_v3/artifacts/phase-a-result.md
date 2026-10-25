# Phase A result: all four acceptance criteria hold

- **A1 imports: PASS.** `objdump -p` on all three products shows only
  `KERNEL32.dll` and the UCRT `api-ms-win-crt-*` API sets; the two model DLLs
  also import `tbb.dll`. No product imports `libwinpthread-1.dll`,
  `libgcc_s_seh-1.dll` or `libstdc++-6.dll`
  (`phase-a-static-runtime-manifest.json`).
- **A2 exports: PASS.**
  - Each model exports 44 names, identical to its WP50 dynamic build
    (`phase-a-exports.json`).
  - The private `tbb.dll` has 0 missing and 0 extra exports compared with the
    stock `tbb.dll`.
- **A3 parity: PASS.** Log density and gradient at 64 deterministic positions
  are bit-identical between the static and dynamic builds for both sblrc and
  arK (`phase-a-parity.json`).
- **A4 load: PASS.**
  - The static process maps no libwinpthread, libgcc_s_seh or libstdc++, and
    its `tbb.dll` is the private copy.
  - The dynamic process maps all three runtime DLLs from PATH (here Git's
    `mingw64\bin`, because the check was launched from Git Bash).

Harness correction, recorded and not a result. Attempt 1
(`phase-a-parity-attempt1-dynamic-leg-load-failure.json`, preserved) could
not load the stock `tbb.dll` in the dynamic leg. Python's full-path
`ctypes.CDLL` uses the safe DLL search, which excludes PATH, so the stock
`tbb.dll` could not find its `libgcc_s_seh-1.dll`/`libstdc++-6.dll`
dependencies. This is itself a direct demonstration of the PATH dependence
the fix removes; the static leg loaded and passed in that attempt. Both legs
were then re-evaluated with `winmode=0` (legacy search).

The model link uses `-Wl,--whole-archive` for libwinpthread, and the export
table is unchanged.
