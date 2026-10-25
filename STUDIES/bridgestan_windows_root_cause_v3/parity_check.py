#!/usr/bin/env python3
"""WP50C Phase A parity and load check (one process per model build).

    python parity_check.py child <tbb.dll> <model.so> <data.json>   # internal
    python parity_check.py run                                      # all pairs

Each child process preloads exactly one tbb.dll by full path, loads the model
with the bridgestan Python package, evaluates log density + gradient
(propto=False, jacobian=True) at 64 deterministic positions, and reports the
IEEE-754 bit patterns plus the full path of every mingw runtime module mapped
in that process (GetModuleHandleW/GetModuleFileNameW). The parent compares the
static build against the dynamic (stock) build of the same model.
"""
from __future__ import annotations

import ctypes
import hashlib
import json
import struct
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
RUNTIME = ("libwinpthread-1.dll", "libgcc_s_seh-1.dll", "libstdc++-6.dll", "tbb.dll")


def mapped_modules() -> dict:
    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    k32.GetModuleHandleW.restype = ctypes.c_void_p
    k32.GetModuleFileNameW.argtypes = [ctypes.c_void_p, ctypes.c_wchar_p, ctypes.c_uint32]
    out = {}
    for name in RUNTIME:
        handle = k32.GetModuleHandleW(name)
        if not handle:
            out[name] = None
            continue
        buf = ctypes.create_unicode_buffer(32768)
        k32.GetModuleFileNameW(handle, buf, 32768)
        out[name] = buf.value
    return out


def child(tbb: str, model: str, data: str) -> None:
    import numpy as np
    # Full-path preload; the model's tbb.dll import binds to it. winmode=0 uses
    # the legacy search order (incl. PATH) for the stock tbb.dll's own
    # libgcc_s_seh/libstdc++ dependencies; with the default safe search the
    # stock tbb.dll cannot load at all (attempt 1, preserved in artifacts).
    ctypes.CDLL(tbb, winmode=0)
    import bridgestan as bs
    sm = bs.StanModel(model, data=Path(data).read_text(encoding="utf-8"), seed=50700000,
                      capture_stan_prints=False)
    dim = sm.param_unc_num()
    rng = np.random.default_rng(50700000)
    bits = []
    for _ in range(64):
        x = rng.normal(0.0, 1.0, dim)
        value, grad = sm.log_density_gradient(x, propto=False, jacobian=True)
        bits.append(struct.pack("<d", value).hex() + ":" + "".join(struct.pack("<d", g).hex() for g in grad))
    print(json.dumps({"dim": dim, "bits_sha256": hashlib.sha256("\n".join(bits).encode()).hexdigest(),
                      "first": bits[0], "modules": mapped_modules()}))


def run() -> None:
    manifest = json.loads((HERE / "build" / "static" / "static-runtime-manifest.json").read_text())
    stock_tbb = manifest["tbb"]["stock_tbb"]["path"]
    static_tbb = manifest["tbb"]["path"]
    pairs = json.loads((HERE / "protocol.json").read_text())["phase_a"]["parity_pairs"]
    results = {}
    for name, pair in pairs.items():
        row = {}
        for variant, tbb, model in (("dynamic", stock_tbb, pair["dynamic_model"]),
                                    ("static", static_tbb, pair["static_model"])):
            proc = subprocess.run([sys.executable, "-I", __file__, "child", tbb, model, pair["data"]],
                                  capture_output=True, text=True)
            row[variant] = {"returncode": proc.returncode, "stderr": proc.stderr[-2000:],
                            "report": json.loads(proc.stdout.strip().splitlines()[-1]) if proc.returncode == 0 else None}
        d, s = row["dynamic"]["report"], row["static"]["report"]
        row["bit_identical"] = bool(d and s and d["bits_sha256"] == s["bits_sha256"])
        row["static_maps_forbidden_runtime"] = bool(s) and any(
            s["modules"][m] for m in ("libwinpthread-1.dll", "libgcc_s_seh-1.dll", "libstdc++-6.dll"))
        row["static_tbb_is_private"] = bool(s) and (s["modules"]["tbb.dll"] or "").lower() == static_tbb.lower()
        results[name] = row
        print(name, "bit_identical", row["bit_identical"], "static_maps_forbidden",
              row["static_maps_forbidden_runtime"], "private_tbb", row["static_tbb_is_private"])
        for variant in ("dynamic", "static"):
            print("   ", variant, (row[variant]["report"] or {}).get("modules"), row[variant]["stderr"][-200:])
    (HERE / "artifacts" / "phase-a-parity.json").write_text(json.dumps(results, indent=2) + "\n")


if __name__ == "__main__":
    if sys.argv[1:2] == ["child"]:
        child(*sys.argv[2:5])
    else:
        run()
