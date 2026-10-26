#!/usr/bin/env python3
"""WP84 driver: target equivalence check, CmdStan / nutpie refit arms, and the frozen cell order.

Usage (on the lane, every command under `taskset -c <lane cores>`):
  python run_cells.py check  <workdir>                 Rust density/gradient vs BridgeStan (sv.stan)
  python run_cells.py stan   <cmdstan|nutpie> <N> <seed> <outdir> <workdir>
  python run_cells.py plan                             print the frozen cell order (protocol.json)
  python run_cells.py all    <workdir>                 run every cell in order, skipping completed ones

Outputs match the Rust arms: <outdir>/ticks.jsonl and <outdir>/tick-XXX.f32
(little-endian f32, [chain][draw][3] = mu, log_sigma, h_last).
Latency for the Stan arms is the wall of the per-tick data update plus the sampling call
(CmdStan: `CmdStanModel.sample`, which writes the data JSON, spawns the four chain
processes, and reads the CSVs back; nutpie: `with_data` + `nutpie.sample`). Compilation
happens once per cell, before tick 1, outside the latency.
"""
import json, os, subprocess, sys, time
from pathlib import Path
import numpy as np

HERE = Path(__file__).resolve().parent
PROTO = json.loads((HERE / "protocol.json").read_text())
DATA = json.loads((HERE / "models" / "data.json").read_text())
STAN = HERE / "models" / "sv.stan"
TICKS = int(os.environ.get("WP84_TICKS", PROTO["stream"]["ticks"]))


def stan_data(n):
    p = DATA["priors"]
    return dict(n=n, y=DATA["y"][:n], rho=DATA["rho"], nu=DATA["nu"], mu_mean=p["mu_mean"], mu_sd=p["mu_sd"],
                log_sigma_mean=p["log_sigma_mean"], log_sigma_sd=p["log_sigma_sd"], beta_sd=p["beta_sd"])


def rust_bin(workdir):
    return Path(workdir) / "target" / "release" / "wp84"


def check(workdir):
    import bridgestan as bs
    workdir = Path(workdir)
    out = {}
    for n in (250, 1001):
        dj = workdir / f"check-data-{n}.json"
        dj.write_text(json.dumps(stan_data(n)))
        model = bs.StanModel(str(STAN), str(dj))
        rng = np.random.default_rng(84 + n)
        pts = [np.r_[DATA["priors"]["mu_mean"] + rng.normal(), np.log(.2) + .3 * rng.normal(), .001 * rng.normal(),
                     rng.normal(size=n)] for _ in range(5)]
        pj, oj = workdir / f"check-pts-{n}.json", workdir / f"check-out-{n}.json"
        pj.write_text(json.dumps([p.tolist() for p in pts]))
        subprocess.run([str(rust_bin(workdir)), "eval", str(HERE / "models" / "data.json"), str(n), str(pj), str(oj)],
                       check=True)
        rust = json.loads(oj.read_text())
        diffs, gerr = [], 0.0
        for p, r in zip(pts, rust):
            lp, g = model.log_density_gradient(p, propto=False, jacobian=True)
            diffs.append(r["lp"] - lp)
            gerr = max(gerr, float(np.max(np.abs(np.asarray(r["grad"]) - g) / (1 + np.abs(g)))))
        out[n] = dict(lp_minus_stan=diffs, lp_offset_spread=float(np.ptp(diffs)), max_rel_grad_err=gerr)
    print(json.dumps(out, indent=1))
    ok = all(v["lp_offset_spread"] < 1e-8 and v["max_rel_grad_err"] < 1e-8 for v in out.values())
    (workdir / "target-check.json").write_text(json.dumps(dict(ok=ok, detail=out), indent=1))
    if not ok:
        sys.exit("target check FAILED")


def write_f32(path, mu, ls, hl):
    arr = np.stack([mu, ls, hl], axis=-1).astype("<f4")  # (chains, draws, 3)
    path.write_bytes(arr.tobytes())


def stan_arm(arm, big_n, seed, outdir, workdir):
    outdir, workdir = Path(outdir), Path(workdir)
    if outdir.exists():
        sys.exit(f"output exists: {outdir}")
    outdir.mkdir(parents=True)
    log = open(outdir / "ticks.jsonl", "w")
    if arm == "cmdstan":
        import cmdstanpy
        cmdstanpy.set_cmdstan_path(PROTO["software"]["cmdstan_path"])
        exe_dir = workdir / "cmdstan-exe"
        exe_dir.mkdir(exist_ok=True)
        src = exe_dir / "sv.stan"
        if not src.exists():
            src.write_text(STAN.read_text())
        model = cmdstanpy.CmdStanModel(stan_file=str(src))
    else:
        import nutpie
        compiled = nutpie.compile_stan_model(code=STAN.read_text())
    for tick in range(1, TICKS + 1):
        n, s = big_n + tick, seed * 1000 + tick
        rec = dict(tick=tick, n=n, seed=s)
        t0 = time.perf_counter()
        try:
            if arm == "cmdstan":
                tmp = outdir / "csv" / f"tick-{tick:03}"
                tmp.mkdir(parents=True)
                fit = model.sample(data=stan_data(n), chains=4, parallel_chains=4, seed=s, show_progress=False,
                                   output_dir=str(tmp))
                wall = time.perf_counter() - t0
                d = fit.draws(concat_chains=False)  # (draws, chains, cols)
                cols = list(fit.column_names)
                get = lambda name: d[:, :, cols.index(name)].T
                mu, ls, hl = get("mu"), get("log_sigma"), get("h_last")
                div = [int(x) for x in fit.divergences]
                for f in tmp.iterdir():
                    f.unlink()
                tmp.rmdir()
            else:
                m = compiled.with_data(**stan_data(n))
                tr = nutpie.sample(m, chains=4, cores=4, seed=s, progress_bar=False)
                wall = time.perf_counter() - t0
                post = tr.posterior
                mu, ls, hl = (np.asarray(post[v]) for v in ("mu", "log_sigma", "h_last"))
                div = [int(x) for x in np.asarray(tr.sample_stats["diverging"]).sum(axis=1)]
            write_f32(outdir / f"tick-{tick:03}.f32", mu, ls, hl)
            rec.update(status="ok", wall_seconds=wall, divergences=div, draws=int(mu.shape[1]))
        except Exception as e:  # failures are results
            rec.update(status="error", wall_seconds=time.perf_counter() - t0, error=repr(e))
        log.write(json.dumps(rec) + "\n")
        log.flush()


def cells():
    out = []
    for c in PROTO["cells"]:
        out.append(c)
    return out


def run_all(workdir):
    workdir = Path(workdir)
    art = HERE / "artifacts" / "cells"
    art.mkdir(parents=True, exist_ok=True)
    data = str(HERE / "models" / "data.json")
    for c in cells():
        out = art / c["id"]
        if (out / "DONE").exists():
            continue
        if out.exists():
            # a started cell that did not finish is a result, never rerun
            (out / "INCOMPLETE").write_text("found started without DONE at resume; not rerun\n")
            continue
        t0 = time.time()
        if c["arm"] in ("ref", "refit"):
            cmd = [str(rust_bin(workdir)), c["arm"], data, str(c["N"]), str(c["seed"]), str(out)]
        elif c["arm"] == "warm":
            cmd = [str(rust_bin(workdir)), "warm", data, str(c["N"]), str(c["K"]), str(c["seed"]), str(out)]
        else:
            cmd = [sys.executable, str(HERE / "run_cells.py"), "stan", c["arm"], str(c["N"]), str(c["seed"]), str(out),
                   str(workdir)]
        print(time.strftime("%H:%M:%S"), "start", c["id"], flush=True)
        r = subprocess.run(cmd)
        (out / "DONE").write_text(json.dumps(dict(returncode=r.returncode, elapsed=time.time() - t0)) + "\n")
        print(time.strftime("%H:%M:%S"), "done", c["id"], r.returncode, flush=True)


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "check":
        check(sys.argv[2])
    elif cmd == "stan":
        stan_arm(sys.argv[2], int(sys.argv[3]), int(sys.argv[4]), sys.argv[5], sys.argv[6])
    elif cmd == "plan":
        for c in cells():
            print(c["id"])
    elif cmd == "all":
        run_all(sys.argv[2])
