#!/usr/bin/env python3
"""Build BridgeStan model DLLs (and a private tbb.dll) with the mingw runtime
linked statically, so no `libwinpthread-1.dll`, `libgcc_s_seh-1.dll` or
`libstdc++-6.dll` is resolved from PATH at load time (Windows GNU only).

Why: on Windows GNU the stock build binds those three DLLs by the DLL search
order, i.e. by whatever PATH the launching shell has. WP50B
(`STUDIES/bridgestan_windows_root_cause_v2`) reproduced the post-sampling
`STATUS_HEAP_CORRUPTION` only when the WinLibs set was bound, with the faults
inside `libwinpthread-1.dll` at thread/process teardown.

    python build_static_runtime.py --out DIR [--tbb] [model.stan ...]

* `--tbb` builds a private `DIR/tbb/tbb.dll` from a COPY of the BridgeStan
  tree's `stan/lib/stan_math/lib/tbb_2020.3` sources, using Stan Math's own
  TBB make invocation plus `TBB_STATIC_LDFLAGS`. The shared BridgeStan tree is
  never modified. Preload this tbb.dll (by full path) instead of the stock one;
  it has the same name and export table, so the model's `tbb.dll` import binds
  to it.
* each `model.stan` is copied to `DIR/models/` and compiled with
  `bridgestan.compile_model(..., make_args=[f"LDLIBS_OS={MODEL_LDLIBS_OS}"])`.
  `LDLIBS_OS` is Stan Math's `?=` per-OS link-library slot (default on Windows:
  `-static-libgcc -static-libstdc++`); overriding it on the make command line
  changes only the final link. `-static` cannot be used because it also forces
  a static `-ltbb`.
* every product is checked with `objdump -p`; a forbidden runtime import is a
  hard error. `DIR/static-runtime-manifest.json` records flags, hashes,
  imports and exports.

Run with the Python that has the `bridgestan` package and with GNU make
available as `mingw32-make` (MAKE is set if unset).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

FORBIDDEN_IMPORTS = ("libwinpthread-1.dll", "libgcc_s_seh-1.dll", "libstdc++-6.dll")
STATIC_WINPTHREAD = "-Wl,-Bstatic,--whole-archive -lwinpthread -Wl,--no-whole-archive,-Bdynamic"
MODEL_LDLIBS_OS = f"-static-libgcc -static-libstdc++ {STATIC_WINPTHREAD}"
TBB_STATIC_LDFLAGS = f"-static-libgcc -static-libstdc++ {STATIC_WINPTHREAD} -Wl,--exclude-libs,ALL"
TBB_CXXFLAGS = ("-Wno-unknown-warning-option -Wno-deprecated-copy -Wno-missing-attributes "
                "-Wno-class-memaccess -Wno-sized-deallocation -D_UCRT")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def pe_imports(path: Path) -> list[str]:
    out = subprocess.check_output(["objdump", "-p", str(path)], text=True, errors="replace")
    return [line.split("DLL Name:")[1].strip() for line in out.splitlines() if "DLL Name:" in line]


def pe_exports(path: Path) -> list[str]:
    out = subprocess.check_output(["objdump", "-p", str(path)], text=True, errors="replace")
    names, inside = [], False
    for line in out.splitlines():
        if "[Ordinal/Name Pointer] Table" in line:
            inside = True
            continue
        if inside:
            if not line.strip():
                break
            names.append(line.split()[-1])
    return sorted(names)


def describe(path: Path) -> dict:
    imports = pe_imports(path)
    bad = [i for i in imports if i.lower() in FORBIDDEN_IMPORTS]
    if bad:
        raise SystemExit(f"{path}: still imports dynamic mingw runtime {bad}")
    return {"path": str(path), "bytes": path.stat().st_size, "sha256": sha256(path),
            "imports": imports, "exports": pe_exports(path)}


def bridgestan_home() -> Path:
    import bridgestan.compile as compile_module
    return Path(compile_module.get_bridgestan_path())


def build_tbb(out: Path) -> dict:
    src_root = bridgestan_home() / "stan/lib/stan_math/lib/tbb_2020.3"
    src, bin_dir = out / "tbb-src", out / "tbb"
    if src.exists() or bin_dir.exists():
        raise SystemExit(f"refusing to replace {src} / {bin_dir}")
    shutil.copytree(src_root, src)
    bin_dir.mkdir(parents=True)
    env = dict(os.environ, tbb_root="../tbb-src", CXX="g++", CC="gcc",
               LDFLAGS=TBB_STATIC_LDFLAGS, SHELL="sh.exe")
    cmd = ["mingw32-make", "-r", "-f", str(src / "build" / "Makefile.tbb"), "compiler=gcc",
           "cfg=release", "stdver=c++17", f"CXXFLAGS={TBB_CXXFLAGS}"]
    log = out / "tbb-build.log"
    with log.open("w", encoding="utf-8") as handle:
        subprocess.run(cmd, cwd=bin_dir, env=env, stdout=handle, stderr=subprocess.STDOUT,
                       check=True)
    stock = bridgestan_home() / "stan/lib/stan_math/lib/tbb/tbb.dll"
    info = describe(bin_dir / "tbb.dll")
    info["stock_exports_missing"] = sorted(set(pe_exports(stock)) - set(info["exports"]))
    info["extra_exports_vs_stock"] = sorted(set(info["exports"]) - set(pe_exports(stock)))
    if info["stock_exports_missing"]:
        raise SystemExit(f"private tbb.dll lacks stock exports: {info['stock_exports_missing'][:5]}")
    info.update({"ldflags": TBB_STATIC_LDFLAGS, "cxxflags": TBB_CXXFLAGS, "make": cmd,
                 "stock_tbb": {"path": str(stock), "sha256": sha256(stock)}})
    return info


def build_model(out: Path, stan: Path) -> dict:
    import bridgestan.compile as compile_module
    models = out / "models"
    models.mkdir(parents=True, exist_ok=True)
    target = models / stan.name
    if target.exists():
        raise SystemExit(f"refusing to replace {target}")
    shutil.copy2(stan, target)
    data = stan.with_name(stan.stem + ".data.json")
    if data.exists():
        shutil.copy2(data, models / data.name)
    compile_module.compile_model(str(target), make_args=[f"LDLIBS_OS={MODEL_LDLIBS_OS}"])
    info = describe(models / f"{stan.stem}_model.so")
    info.update({"stan": str(stan), "stan_sha256": sha256(stan), "ldlibs_os": MODEL_LDLIBS_OS})
    return info


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--tbb", action="store_true")
    parser.add_argument("models", nargs="*", type=Path)
    args = parser.parse_args()
    if sys.platform != "win32":
        raise SystemExit("static mingw runtime build is Windows GNU only")
    os.environ.setdefault("MAKE", "mingw32-make")
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    manifest = {"schema": "owalnuts-bridgestan-static-runtime-v1",
                "bridgestan_home": str(bridgestan_home()),
                "gcc": subprocess.check_output(["gcc", "--version"], text=True).splitlines()[0],
                "forbidden_imports": list(FORBIDDEN_IMPORTS)}
    if args.tbb:
        manifest["tbb"] = build_tbb(out)
    manifest["models"] = [build_model(out, m.resolve()) for m in args.models]
    (out / "static-runtime-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n",
                                                      encoding="utf-8")
    print(json.dumps({k: v for k, v in manifest.items() if k != "models"} | {
        "models": [{"path": m["path"], "imports": m["imports"]} for m in manifest["models"]]},
        indent=2, default=str)[:4000])


if __name__ == "__main__":
    main()
