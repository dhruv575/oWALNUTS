#!/usr/bin/env python3
"""WP97 driver: gated reference, the two preregistered lanes, the pre-freeze smoke (the WP93 driver with dataset-aware cells).

Usage (on the lane; every command under `taskset -c <lane cores>`, RAYON_NUM_THREADS=4, OMP_NUM_THREADS=1):
  python run_cells.py ref   <cell-id> <outdir> <workdir>     gated reference at that cell's preregistered ticks
  python run_cells.py plan                                   print the frozen cell order per lane
  python run_cells.py lane  <3|4> <workdir>                  run that lane's cells in order; an existing output is skipped, never rerun
  python run_cells.py smoke <workdir> <outroot>              diagnostic-seed smoke (3 reference ticks, two 3-tick warm cells), then analyze.py

Outputs: <outdir>/ticks.jsonl and <outdir>/tick-XXX[-aA].f32 (little-endian f32, [chain][draw][4] = mu, log_sigma, beta, h_last;
`chains` and `draws` in the record give the shape).

Reference gate (protocol.json "reference"): per tick, attempt 0 at seed_base[dataset]*1000 + tick; chains named by a WarmupStep /
SampledLogDensity warning are dropped; if fewer than 3 remain or the rank R-hat of h_next over the remaining chains exceeds
1.01, attempt 1 runs at seed_base*1000 + tick + 200. A tick failing both is recorded `gate_failed` (unscored; the analysis
counts it as a failure for every configuration).
"""
import json, re, shutil, subprocess, sys, time
from pathlib import Path
import numpy as np

HERE = Path(__file__).resolve().parent
PROTO = json.loads((HERE / "protocol.json").read_text())


def data_path(dataset):
    return str(HERE / PROTO["datasets"][dataset]["file"])


def rust_bin(workdir):
    return Path(workdir) / "target" / "release" / "wp97"


def load_draws(path, chains, draws):
    raw = np.frombuffer(Path(path).read_bytes(), dtype="<f4").astype(float)
    return raw.reshape(chains, draws, 4)


def h_next(a, tick, chain_idx):
    mu, ls, hl = a[..., 0], a[..., 1], a[..., 3]
    eps = np.random.default_rng(PROTO["quantities"]["eps_seed_base"] + tick).normal(size=(4, 20000))
    eps = eps[np.asarray(chain_idx), : a.shape[1]]
    return mu + PROTO["model"]["rho"] * (hl - mu) + np.exp(ls) * eps


def flagged_chains(rec):
    return sorted({int(m) for w in rec.get("chain_warnings", []) for m in re.findall(r"chain: (\d+)", w)
                   if w.startswith(("WarmupStep", "SampledLogDensity"))})


def ref(cell_id, outdir, workdir, cell=None, seed_base=None):
    import warnings
    warnings.filterwarnings("ignore")
    import arviz as az
    if cell is None:
        cell = next(c for c in PROTO["cells"] if c["id"] == cell_id)
    outdir = Path(outdir)
    if outdir.exists():
        sys.exit(f"output exists: {outdir}")
    outdir.mkdir(parents=True)
    log = open(outdir / "ticks.jsonl", "w")
    spec = PROTO["reference"]
    base = spec["seed_base"][cell["dataset"]] if seed_base is None else seed_base
    big_n = cell["N"]
    data = data_path(cell["dataset"])
    for tick in cell["ticks"]:
        n = big_n + tick
        attempts, chosen = [], None
        for a in range(spec["attempts"]):
            seed = base * 1000 + tick + spec["attempt_seed_step"] * a
            stem = outdir / f"tick-{tick:03}-a{a}"
            t0 = time.perf_counter()
            r = subprocess.run([str(rust_bin(workdir)), "reftick", data, str(n), str(seed), str(stem)])
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
        out = dict(tick=tick, n=n, dataset=cell["dataset"], attempts=attempts)
        if chosen is None:
            out.update(status="gate_failed")
        else:
            out.update(status="ok", attempt=chosen["attempt"], seed=chosen["seed"], kept=chosen["kept"], flagged=chosen["flagged"],
                       rhat_h_next=chosen["rhat_h_next"], wall_seconds=chosen["wall_seconds"], chains=4, draws=20000,
                       file=f"tick-{tick:03}-a{chosen['attempt']}.f32")
        log.write(json.dumps(out) + "\n")
        log.flush()
        print(time.strftime("%H:%M:%S"), "ref", cell["dataset"], "tick", tick, out["status"], [a["gate"] for a in attempts], flush=True)


def cell_cmd(c, workdir, out):
    if c["arm"] == "ref":
        return [sys.executable, str(HERE / "run_cells.py"), "ref", c["id"], str(out), str(workdir)]
    return [str(rust_bin(workdir)), "warm", data_path(c["dataset"]), str(c["N"]), str(c["K"]), str(c["seed"]), str(c["ticks"]), str(out)]


def plan():
    for lane in sorted({c["lane"] for c in PROTO["cells"]}):
        print(f"lane {lane} (cores {PROTO['lanes'][str(lane)]}):", " -> ".join(c["id"] for c in PROTO["cells"] if c["lane"] == lane))


def lane(which, workdir):
    cells = [c for c in PROTO["cells"] if c["lane"] == int(which)]
    (HERE / "artifacts" / "cells").mkdir(parents=True, exist_ok=True)
    log = open(HERE / "artifacts" / f"lane-{which}.log", "a")
    for c in cells:
        out = HERE / "artifacts" / "cells" / c["id"]
        if out.exists():
            msg = f"{time.strftime('%H:%M:%S')} skip {c['id']} (output exists; never rerun)"
        else:
            t0 = time.perf_counter()
            r = subprocess.run(cell_cmd(c, workdir, out))
            msg = f"{time.strftime('%H:%M:%S')} done {c['id']} rc={r.returncode} wall={time.perf_counter() - t0:.1f}s"
        print(msg, flush=True)
        log.write(msg + "\n")
        log.flush()
    print("LANE-FINISHED", which, flush=True)
    log.write(f"LANE-FINISHED {which}\n")


def smoke(workdir, outroot):
    """Diagnostic seeds (99xxxx), never scored: reference ticks 0, 1 on real and 0, 1 on sim through the gate code path, a 3-tick
    K = 20 real warm cell and a 3-tick K = 200 sim warm cell, then analyze.py on a smoke protocol copy (ticks 0..2)."""
    outroot = Path(outroot)
    if outroot.exists():
        shutil.rmtree(outroot)
    cells = outroot / "cells"
    cells.mkdir(parents=True)
    smoke_proto = json.loads(json.dumps(PROTO))
    smoke_proto["stream"]["ticks"] = 3
    smoke_proto["reference"]["seed_base"] = {"sim": 993970, "real": 993975}
    smoke_proto["arms"]["seeds"] = {"sim": [993972], "real": [993971]}
    smoke_proto["cells"] = [dict(id="ref-sim-lo", arm="ref", dataset="sim", N=250, ticks=[0, 1, 2], lane=3),
                            dict(id="ref-real-lo", arm="ref", dataset="real", N=250, ticks=[0, 1, 2], lane=3),
                            dict(id="warm200-sim-s993972", arm="warm", dataset="sim", N=250, K=200, seed=993972, ticks=3, lane=3),
                            dict(id="warm20-real-s993971", arm="warm", dataset="real", N=250, K=20, seed=993971, ticks=3, lane=3)]
    study = outroot / "study"
    study.mkdir()
    for f in ("run_cells.py", "analyze.py"):
        shutil.copy(HERE / f, study / f)
    shutil.copytree(HERE / "models", study / "models")
    (study / "protocol.json").write_text(json.dumps(smoke_proto, indent=1))
    for c in smoke_proto["cells"]:
        t0 = time.perf_counter()
        subprocess.run(cell_cmd(c, workdir, cells / c["id"]) if c["arm"] == "warm" else
                       [sys.executable, str(study / "run_cells.py"), "ref", c["id"], str(cells / c["id"]), str(workdir)], check=True)
        print(time.strftime("%H:%M:%S"), "smoke cell", c["id"], f"{time.perf_counter() - t0:.1f}s", flush=True)
    subprocess.run([sys.executable, str(study / "analyze.py"), str(cells), "--out", str(outroot / "out")], check=True)
    print("smoke-done")


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "ref":
        ref(sys.argv[2], sys.argv[3], sys.argv[4])
    elif cmd == "plan":
        plan()
    elif cmd == "lane":
        lane(sys.argv[2], sys.argv[3])
    elif cmd == "smoke":
        smoke(sys.argv[2], sys.argv[3])
    else:
        sys.exit(__doc__)
