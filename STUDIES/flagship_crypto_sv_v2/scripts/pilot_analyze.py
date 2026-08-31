"""Pilot analysis: gate functionals for the BTC arm cells (non-evidence).

Usage: python scripts/pilot_analyze.py [seed]
Reads artifacts/draws/BTC-arm{O,A,B,C}-<seed>.f64 (chains-major flat f64,
4 chains x draws x dim) and prints R-hat / bulk / tail ESS for the gate
functionals plus work/wall from the run JSONs.
"""

import json
import pathlib
import sys

import arviz as az
import numpy as np

ROOT = pathlib.Path(__file__).resolve().parents[1]
CHAINS = 4


def functionals(raw):
    a = raw[:, :, 1]
    return {
        "mu": raw[:, :, 0],
        "a": a,
        "s": raw[:, :, 2],
        "h_T": raw[:, :, -1],
        "mean_h": raw[:, :, 3:].mean(axis=2),
    }


def main():
    seed = int(sys.argv[1]) if len(sys.argv) > 1 else 98000
    t = len(json.loads((ROOT / "data" / "BTC.json").read_text())["closes"]) - 1
    dim = t + 3
    rows = []
    for arm in ("O", "A", "B", "C"):
        stem = f"BTC-arm{arm}-{seed}"
        path = ROOT / "artifacts" / "draws" / f"{stem}.f64"
        if not path.exists():
            print(f"{stem}: missing")
            continue
        raw = np.fromfile(path)
        draws = raw.size // (CHAINS * dim)
        raw = raw.reshape(CHAINS, draws, dim)
        meta = json.loads((ROOT / "artifacts" / "runs" / f"{stem}.json").read_text())
        out = {"arm": arm, "wall": round(meta["wall_seconds"], 1),
               "calls": meta["target_calls_total"],
               "div": meta["divergences"], "inv": meta["invalid"],
               "exh": meta["exhaustions"], "caprate": meta["max_depth_rate"],
               "steps": [round(x, 4) for x in meta["final_step_sizes"]]}
        for name, arr in functionals(raw).items():
            da = az.convert_to_dataset(arr)
            ess_b = float(np.asarray(az.ess(da, method="bulk").x).ravel()[0])
            ess_t = float(np.asarray(az.ess(da, method="tail").x).ravel()[0])
            rhat = float(np.asarray(az.rhat(da).x).ravel()[0])
            out[name] = (round(rhat, 3), int(ess_b), int(ess_t))
        rows.append(out)
        refresh = ROOT / "artifacts" / "runs" / f"{stem}-refresh.json"
        if refresh.exists():
            events = json.loads(refresh.read_text())
            installed = [e for e in events if e["outcome"] == "Installed"]
            out["installs"] = f"{len(installed)} boundaries x chains"
    for out in rows:
        print(json.dumps(out))
    (ROOT / "artifacts" / f"pilot-summary-{seed}.json").write_text(
        json.dumps(rows, indent=1)
    )


if __name__ == "__main__":
    main()
