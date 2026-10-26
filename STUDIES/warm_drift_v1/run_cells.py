#!/usr/bin/env python3
"""WP96 driver: the gated reference and the two preregistered lane queues.

Usage (on the lane; every command under `taskset -c <lane cores>`, RAYON_NUM_THREADS=4, OMP_NUM_THREADS=1):
  python run_cells.py ref    <stream> <outdir> <workdir>   gated reference at the preregistered ticks
  python run_cells.py plan                                  print the frozen cell order per lane
  python run_cells.py queue  <3|4> <workdir>                run that lane's cells in order, never rerunning

Outputs match the Rust arm: <outdir>/ticks.jsonl and <outdir>/tick-XXXX-aA.f32 (little-endian f32,
[chain][draw][3] = mu, log_sigma, h_last; `chains` and `draws` in the record give the shape).

Reference gate (protocol.json "reference", the WP88 gate): per tick, attempt 0 at seed
base*10000 + tick; chains named by a WarmupStep / SampledLogDensity warning are dropped; if fewer
than 3 remain or the rank R-hat of h_next over the remaining chains exceeds 1.01, attempt 1 runs at
seed base*10000 + tick + 5000. A tick failing both is recorded `gate_failed` (unscored; the analysis
counts it as a failure for every arm).
"""
import json, re, subprocess, sys, time
from pathlib import Path
import numpy as np

HERE = Path(__file__).resolve().parent
PROTO = json.loads((HERE / "protocol.json").read_text())


def data_path(stream):
    return str(HERE / "models" / f"data-{stream}.json")


def rust_bin(workdir):
    return Path(workdir) / "target" / "release" / "wp96"


def load_draws(path, chains, draws):
    raw = np.frombuffer(Path(path).read_bytes(), dtype="<f4").astype(float)
    return raw.reshape(chains, draws, 3)


def h_next(a, tick, chain_idx):
    """h_next per draw, chains x draws, with the shared eps stream rows of the given chain indices."""
    mu, ls, hl = a[..., 0], a[..., 1], a[..., 2]
    eps = np.random.default_rng(PROTO["quantities"]["eps_seed_base"] + tick).normal(size=(4, 20000))
    eps = eps[np.asarray(chain_idx), : a.shape[1]]
    rho = PROTO["model"]["rho"]
    return mu + rho * (hl - mu) + np.exp(ls) * eps


def flagged_chains(rec):
    return sorted({int(m) for w in rec.get("chain_warnings", []) for m in re.findall(r"chain: (\d+)", w)
                   if w.startswith(("WarmupStep", "SampledLogDensity"))})


def ref(stream, outdir, workdir):
    import warnings
    warnings.filterwarnings("ignore")
    import arviz as az
    outdir = Path(outdir)
    if outdir.exists():
        sys.exit(f"output exists: {outdir}")
    outdir.mkdir(parents=True)
    log = open(outdir / "ticks.jsonl", "w")
    spec = PROTO["reference"]
    base = spec["seed_base"][stream]
    n = PROTO["stream"]["N"]
    for tick in spec["ticks"]:
        attempts, chosen = [], None
        for a in range(spec["attempts"]):
            seed = base * 10000 + tick + spec["attempt_seed_step"] * a
            stem = outdir / f"tick-{tick:04}-a{a}"
            t0 = time.perf_counter()
            r = subprocess.run([str(rust_bin(workdir)), "reftick", data_path(stream), str(tick), str(n), str(seed), str(stem)])
            att = dict(attempt=a, seed=seed, returncode=r.returncode, driver_wall=time.perf_counter() - t0)
            rec = json.loads(stem.with_suffix(".json").read_text()) if stem.with_suffix(".json").exists() else {}
            att.update({k: rec.get(k) for k in ("status", "wall_seconds", "error", "chain_warnings", "divergences", "steps", "calls")})
            if rec.get("status") == "ok":
                dropped = flagged_chains(rec)
                kept = [c for c in range(rec["chains"]) if c not in dropped]
                att.update(flagged=dropped, kept=kept)
                if len(kept) >= spec["min_chains"]:
                    arr = load_draws(stem.with_suffix(".f32"), rec["chains"], rec["draws"])[kept]
                    rhat = float(az.rhat(h_next(arr, tick, kept)))
                    att["rhat_h_next"] = rhat
                    att["gate"] = "pass" if rhat <= spec["max_rhat"] else "fail_rhat"
                else:
                    att["gate"] = "fail_chains"
            else:
                att["gate"] = "fail_error"
            attempts.append(att)
            if att["gate"] == "pass":
                chosen = att
                break
        out = dict(tick=tick, n=n, start=tick, attempts=attempts)
        if chosen is None:
            out.update(status="gate_failed")
        else:
            out.update(status="ok", attempt=chosen["attempt"], seed=chosen["seed"], kept=chosen["kept"],
                       flagged=chosen["flagged"], rhat_h_next=chosen["rhat_h_next"], wall_seconds=chosen["wall_seconds"],
                       chains=4, draws=20000, file=f"tick-{tick:04}-a{chosen['attempt']}.f32")
        log.write(json.dumps(out) + "\n")
        log.flush()
        print(time.strftime("%H:%M:%S"), "ref", stream, "tick", tick, out["status"], [a["gate"] for a in attempts], flush=True)


def cell_cmd(c, workdir):
    out = str(HERE / "artifacts" / "cells" / c["id"])
    if c["arm"] == "ref":
        return [sys.executable, str(HERE / "run_cells.py"), "ref", c["stream"], out, str(workdir)]
    if c["arm"] == "warm":
        return [str(rust_bin(workdir)), "warm", data_path(c["stream"]), str(PROTO["stream"]["N"]), str(c["K"]),
                str(c["seed"]), str(c["ticks"]), c["policy"], str(PROTO["reference"]["every"]), out]
    raise ValueError(c)


def run_queue(lane, workdir):
    art = HERE / "artifacts" / "cells"
    art.mkdir(parents=True, exist_ok=True)
    for c in PROTO["cells"]:
        if c["lane"] != lane:
            continue
        out = art / c["id"]
        if (out / "DONE").exists():
            continue
        if out.exists():
            # a started cell that did not finish is a result, never rerun
            (out / "INCOMPLETE").write_text("found started without DONE at resume; not rerun\n")
            continue
        t0 = time.time()
        print(time.strftime("%H:%M:%S"), "start", c["id"], flush=True)
        r = subprocess.run(cell_cmd(c, workdir))
        out.mkdir(exist_ok=True)
        (out / "DONE").write_text(json.dumps(dict(returncode=r.returncode, elapsed=time.time() - t0)) + "\n")
        print(time.strftime("%H:%M:%S"), "done", c["id"], r.returncode, f"{time.time() - t0:.0f}s", flush=True)


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "ref":
        ref(sys.argv[2], sys.argv[3], sys.argv[4])
    elif cmd == "plan":
        for lane in (3, 4):
            print("lane", lane, [c["id"] for c in PROTO["cells"] if c["lane"] == lane])
    elif cmd == "queue":
        run_queue(int(sys.argv[2]), sys.argv[3])
    else:
        sys.exit(__doc__)
