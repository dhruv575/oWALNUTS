#!/usr/bin/env python3
"""WP93 driver: gated reference, the two preregistered lanes, the pre-freeze smoke.

Usage (on the lane; every command under `taskset -c <lane cores>`, RAYON_NUM_THREADS=4, OMP_NUM_THREADS=1):
  python run_cells.py ref   <cell-id> <outdir> <workdir>     gated reference at that cell's preregistered ticks
  python run_cells.py plan                                   print the frozen cell order per lane
  python run_cells.py lane  <1|2> <workdir>                  run that lane's cells in order; an existing output is skipped, never rerun
  python run_cells.py smoke <workdir> <outroot>              diagnostic-seed smoke (3 reference ticks, one 3-tick warm cell), then analyze.py

Outputs: <outdir>/ticks.jsonl and <outdir>/tick-XXX[-aA].f32 (little-endian f32, [chain][draw][4] = mu, log_sigma, beta, h_last;
`chains` and `draws` in the record give the shape).

Reference gate (protocol.json "reference"): per tick, attempt 0 at seed_base*1000 + tick; chains named by a WarmupStep /
SampledLogDensity warning are dropped; if fewer than 3 remain or the rank R-hat of h_next over the remaining chains exceeds
1.01, attempt 1 runs at seed_base*1000 + tick + 200. A tick failing both is recorded `gate_failed` (unscored; the analysis
counts it as a failure for every configuration).
"""
import json, re, shutil, subprocess, sys, time
from pathlib import Path
import numpy as np

HERE = Path(__file__).resolve().parent
PROTO = json.loads((HERE / "protocol.json").read_text())
DATA = str(HERE / "models" / "data.json")


def rust_bin(workdir):
    return Path(workdir) / "target" / "release" / "wp93"


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


def ref(cell_id, outdir, workdir, ticks=None, seed_base=None):
    import warnings
    warnings.filterwarnings("ignore")
    import arviz as az
    cell = next(c for c in PROTO["cells"] if c["id"] == cell_id) if ticks is None else dict(N=PROTO["stream"]["N"], ticks=ticks)
    outdir = Path(outdir)
    if outdir.exists():
        sys.exit(f"output exists: {outdir}")
    outdir.mkdir(parents=True)
    log = open(outdir / "ticks.jsonl", "w")
    spec = PROTO["reference"]
    base = spec["seed_base"] if seed_base is None else seed_base
    big_n = cell["N"]
    for tick in cell["ticks"]:
        n = big_n + tick
        attempts, chosen = [], None
        for a in range(spec["attempts"]):
            seed = base * 1000 + tick + spec["attempt_seed_step"] * a
            stem = outdir / f"tick-{tick:03}-a{a}"
            t0 = time.perf_counter()
            r = subprocess.run([str(rust_bin(workdir)), "reftick", DATA, str(n), str(seed), str(stem)])
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
        out = dict(tick=tick, n=n, attempts=attempts)
        if chosen is None:
            out.update(status="gate_failed")
        else:
            out.update(status="ok", attempt=chosen["attempt"], seed=chosen["seed"], kept=chosen["kept"], flagged=chosen["flagged"],
                       rhat_h_next=chosen["rhat_h_next"], wall_seconds=chosen["wall_seconds"], chains=4, draws=20000,
                       file=f"tick-{tick:03}-a{chosen['attempt']}.f32")
        log.write(json.dumps(out) + "\n")
        log.flush()
        print(time.strftime("%H:%M:%S"), "ref tick", tick, out["status"], [a["gate"] for a in attempts], flush=True)


def cell_cmd(c, workdir, out):
    if c["arm"] == "ref":
        return [sys.executable, str(HERE / "run_cells.py"), "ref", c["id"], str(out), str(workdir)]
    return [str(rust_bin(workdir)), "warm", DATA, str(c["N"]), str(c["K"]), str(c["seed"]), str(c["ticks"]), str(out)]


def plan():
    for lane in (1, 2):
        print(f"lane {lane}:", " -> ".join(c["id"] for c in PROTO["cells"] if c["lane"] == lane))


def lane(which, workdir):
    cells = [c for c in PROTO["cells"] if c["lane"] == int(which)]
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
    """Diagnostic seeds (99xxxx), never scored: 3 reference ticks (0, 1, 2), one 3-tick warm cell at K = 5 and one at K = 200,
    then analyze.py on a smoke protocol copy (ticks 0..2, H grid unchanged)."""
    outroot = Path(outroot)
    if outroot.exists():
        shutil.rmtree(outroot)
    cells = outroot / "cells"
    cells.mkdir(parents=True)
    smoke_proto = json.loads(json.dumps(PROTO))
    smoke_proto["stream"]["ticks"] = 3
    smoke_proto["reference"]["seed_base"] = 993960
    smoke_proto["cells"] = [dict(id="ref-lo", arm="ref", N=250, ticks=[0, 1, 2], lane=1),
                            dict(id="warm5-s931201", arm="warm", N=250, K=5, seed=993901, ticks=3, lane=1),
                            dict(id="warm200-s931202", arm="warm", N=250, K=200, seed=993902, ticks=3, lane=1)]
    study = outroot / "study"
    study.mkdir()
    for f in ("run_cells.py", "analyze.py"):
        shutil.copy(HERE / f, study / f)
    shutil.copytree(HERE / "models", study / "models")
    (study / "protocol.json").write_text(json.dumps(smoke_proto, indent=1))
    subprocess.run([sys.executable, str(study / "run_cells.py"), "ref", "ref-lo", str(cells / "ref-lo"), str(workdir)], check=True)
    for c in smoke_proto["cells"][1:]:
        subprocess.run(cell_cmd(c, workdir, cells / c["id"]), check=True)
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
