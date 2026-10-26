#!/usr/bin/env python3
"""WP88 driver: target check, gated reference, CmdStan / nutpie refit arms, the Python warm extra,
and the three preregistered parallel queues.

Usage (on the lane; every command under `taskset -c <queue cores>`, RAYON_NUM_THREADS=4, OMP_NUM_THREADS=1):
  python run_cells.py check   <workdir>                      Rust density/gradient vs BridgeStan (both datasets)
  python run_cells.py prep    <workdir>                      compile the CmdStan model and the C target once
  python run_cells.py ref     <ds> <N> <outdir> <workdir>    gated reference at the preregistered ticks
  python run_cells.py stan    <cmdstan|nutpie> <ds> <N> <seed> <ticks> <outdir> <workdir>
  python run_cells.py pyextra <ds> <N> <K> <seed> <ticks> <outdir> <workdir>   (lane venv python with owalnuts)
  python run_cells.py plan                                   print the frozen cell order per queue
  python run_cells.py queue   <A|B|C> <workdir>              run that queue's cells in order, never rerunning

Outputs match the Rust arms: <outdir>/ticks.jsonl and <outdir>/tick-XXX.f32 (little-endian f32,
[chain][draw][3] = mu, log_sigma, h_last; `chains` and `draws` in the record give the shape).

Reference gate (protocol.json "reference"): per tick, attempt 0 at seed base*1000 + tick; chains named by
a WarmupStep / SampledLogDensity warning are dropped; if fewer than 3 remain or the rank R-hat of h_next
over the remaining chains exceeds 1.01, attempt 1 runs at seed base*1000 + tick + 200. A tick failing
both is recorded `gate_failed` (unscored; the analysis counts it as a failure for every arm).
"""
import ctypes, json, os, re, subprocess, sys, time
from pathlib import Path
import numpy as np

HERE = Path(__file__).resolve().parent
PROTO = json.loads((HERE / "protocol.json").read_text())
STAN = HERE / "models" / "sv.stan"
_DATA = {}


def data(ds):
    if ds not in _DATA:
        _DATA[ds] = json.loads((HERE / "models" / f"data-{ds}.json").read_text())
    return _DATA[ds]


def data_path(ds):
    return str(HERE / "models" / f"data-{ds}.json")


def stan_data(ds, n):
    d = data(ds)
    p = d["priors"]
    return dict(n=n, y=d["y"][:n], rho=d["rho"], nu=d["nu"], mu_mean=p["mu_mean"], mu_sd=p["mu_sd"],
                log_sigma_mean=p["log_sigma_mean"], log_sigma_sd=p["log_sigma_sd"], beta_sd=p["beta_sd"])


def rust_bin(workdir):
    return Path(workdir) / "target" / "release" / "wp88"


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


# ── target check ────────────────────────────────────────────────────────────────────────────

def check(workdir):
    import bridgestan as bs
    workdir = Path(workdir)
    out = {}
    for ds, ns in (("sim", (250, 1001)), ("real", (250, 350))):
        for n in ns:
            dj = workdir / f"check-data-{ds}-{n}.json"
            dj.write_text(json.dumps(stan_data(ds, n)))
            model = bs.StanModel(str(STAN), str(dj))
            rng = np.random.default_rng(88 + n)
            pri = data(ds)["priors"]
            pts = [np.r_[pri["mu_mean"] + rng.normal(), np.log(.2) + .3 * rng.normal(), .001 * rng.normal(),
                         rng.normal(size=n)] for _ in range(5)]
            pj, oj = workdir / f"check-pts-{ds}-{n}.json", workdir / f"check-out-{ds}-{n}.json"
            pj.write_text(json.dumps([p.tolist() for p in pts]))
            subprocess.run([str(rust_bin(workdir)), "eval", data_path(ds), str(n), str(pj), str(oj)], check=True)
            rust = json.loads(oj.read_text())
            diffs, gerr = [], 0.0
            for p, r in zip(pts, rust):
                lp, g = model.log_density_gradient(p, propto=False, jacobian=True)
                diffs.append(r["lp"] - lp)
                gerr = max(gerr, float(np.max(np.abs(np.asarray(r["grad"]) - g) / (1 + np.abs(g)))))
            out[f"{ds}-{n}"] = dict(lp_minus_stan=diffs, lp_offset_spread=float(np.ptp(diffs)), max_rel_grad_err=gerr)
    print(json.dumps(out, indent=1))
    ok = all(v["lp_offset_spread"] < 1e-8 and v["max_rel_grad_err"] < 1e-8 for v in out.values())
    (workdir / "target-check.json").write_text(json.dumps(dict(ok=ok, detail=out), indent=1))
    if not ok:
        sys.exit("target check FAILED")


def prep(workdir):
    workdir = Path(workdir)
    import cmdstanpy
    cmdstanpy.set_cmdstan_path(PROTO["software"]["cmdstan_path"])
    exe_dir = workdir / "cmdstan-exe"
    exe_dir.mkdir(exist_ok=True)
    src = exe_dir / "sv.stan"
    if not src.exists():
        src.write_text(STAN.read_text())
    cmdstanpy.CmdStanModel(stan_file=str(src))
    so = workdir / "libsv.so"
    subprocess.run(["gcc", "-O2", "-shared", "-fPIC", "-o", str(so), str(HERE / "models" / "sv.c"), "-lm"], check=True)
    print("prep done", exe_dir, so)


# ── gated reference ─────────────────────────────────────────────────────────────────────────

def ref(ds, big_n, outdir, workdir):
    import warnings
    warnings.filterwarnings("ignore")
    import arviz as az
    outdir = Path(outdir)
    if outdir.exists():
        sys.exit(f"output exists: {outdir}")
    outdir.mkdir(parents=True)
    log = open(outdir / "ticks.jsonl", "w")
    spec = PROTO["reference"]
    base = spec["seed_base"][f"{ds}-N{big_n}"]
    ticks = PROTO["reference"]["ticks"][f"{ds}-N{big_n}"]
    for tick in ticks:
        n = big_n + tick
        attempts = []
        chosen = None
        for a in range(spec["attempts"]):
            seed = base * 1000 + tick + spec["attempt_seed_step"] * a
            stem = outdir / f"tick-{tick:03}-a{a}"
            t0 = time.perf_counter()
            r = subprocess.run([str(rust_bin(workdir)), "reftick", data_path(ds), str(n), str(seed), str(stem)])
            att = dict(attempt=a, seed=seed, returncode=r.returncode, driver_wall=time.perf_counter() - t0)
            rec = json.loads(stem.with_suffix(".json").read_text()) if stem.with_suffix(".json").exists() else {}
            att.update({k: rec.get(k) for k in ("status", "wall_seconds", "error", "chain_warnings", "divergences", "steps", "calls")})
            if rec.get("status") == "ok":
                dropped = flagged_chains(rec)
                kept = [c for c in range(rec["chains"]) if c not in dropped]
                att.update(flagged=dropped, kept=kept)
                if len(kept) >= spec["min_chains"]:
                    arr = load_draws(stem.with_suffix(".f32"), rec["chains"], rec["draws"])[kept]
                    hn = h_next(arr, tick, kept)
                    rhat = float(az.rhat(hn))
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
            out.update(status="ok", attempt=chosen["attempt"], seed=chosen["seed"], kept=chosen["kept"],
                       flagged=chosen["flagged"], rhat_h_next=chosen["rhat_h_next"], wall_seconds=chosen["wall_seconds"],
                       chains=4, draws=20000, file=f"tick-{tick:03}-a{chosen['attempt']}.f32")
        log.write(json.dumps(out) + "\n")
        log.flush()
        print(time.strftime("%H:%M:%S"), "ref", ds, big_n, "tick", tick, out["status"],
              [a["gate"] for a in attempts], flush=True)


# ── CmdStan / nutpie refit arms ─────────────────────────────────────────────────────────────

def write_f32(path, mu, ls, hl):
    arr = np.stack([mu, ls, hl], axis=-1).astype("<f4")  # (chains, draws, 3)
    path.write_bytes(arr.tobytes())


def stan_arm(arm, ds, big_n, seed, ticks, outdir, workdir):
    outdir, workdir = Path(outdir), Path(workdir)
    if outdir.exists():
        sys.exit(f"output exists: {outdir}")
    outdir.mkdir(parents=True)
    log = open(outdir / "ticks.jsonl", "w")
    if arm == "cmdstan":
        import cmdstanpy
        cmdstanpy.set_cmdstan_path(PROTO["software"]["cmdstan_path"])
        src = workdir / "cmdstan-exe" / "sv.stan"
        model = cmdstanpy.CmdStanModel(stan_file=str(src))  # compiled by `prep`; no compile here
    else:
        import nutpie
        compiled = nutpie.compile_stan_model(code=STAN.read_text())
    for tick in range(1, ticks + 1):
        n, s = big_n + tick, seed * 1000 + tick
        rec = dict(tick=tick, n=n, seed=s)
        t0 = time.perf_counter()
        try:
            if arm == "cmdstan":
                tmp = outdir / "csv" / f"tick-{tick:03}"
                tmp.mkdir(parents=True)
                fit = model.sample(data=stan_data(ds, n), chains=4, parallel_chains=4, seed=s, show_progress=False,
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
                m = compiled.with_data(**stan_data(ds, n))
                tr = nutpie.sample(m, chains=4, cores=4, seed=s, progress_bar=False)
                wall = time.perf_counter() - t0
                post = tr.posterior
                mu, ls, hl = (np.asarray(post[v]) for v in ("mu", "log_sigma", "h_last"))
                div = [int(x) for x in np.asarray(tr.sample_stats["diverging"]).sum(axis=1)]
            write_f32(outdir / f"tick-{tick:03}.f32", mu, ls, hl)
            rec.update(status="ok", wall_seconds=wall, divergences=div, chains=int(mu.shape[0]), draws=int(mu.shape[1]))
        except Exception as e:  # failures are results
            rec.update(status="error", wall_seconds=time.perf_counter() - t0, error=repr(e))
        log.write(json.dumps(rec) + "\n")
        log.flush()


# ── Python warm extra (owalnuts.sample_warm on a C-ABI target) ──────────────────────────────

class SvData(ctypes.Structure):
    _fields_ = [("n", ctypes.c_int64), ("rho", ctypes.c_double), ("nu", ctypes.c_double),
                ("mu_mean", ctypes.c_double), ("mu_sd", ctypes.c_double), ("ls_mean", ctypes.c_double),
                ("ls_sd", ctypes.c_double), ("beta_sd", ctypes.c_double), ("y", ctypes.POINTER(ctypes.c_double)),
                ("h", ctypes.POINTER(ctypes.c_double)), ("dh", ctypes.POINTER(ctypes.c_double))]


def c_target(lib, ds, n, owalnuts):
    d = data(ds)
    y = np.ascontiguousarray(d["y"][:n], dtype=np.float64)
    p = d["priors"]
    s = SvData(n, d["rho"], d["nu"], p["mu_mean"], p["mu_sd"], p["log_sigma_mean"], p["log_sigma_sd"], p["beta_sd"],
               y.ctypes.data_as(ctypes.POINTER(ctypes.c_double)), None, None)
    addr = ctypes.cast(lib.sv_logp_grad, ctypes.c_void_p).value
    cft = owalnuts.from_cfunc(addr, 3 + n, user_data=ctypes.addressof(s))
    return cft, (s, y)  # keep-alive tuple


def h_last_np(q, rho):
    mu, s = q[..., 0], np.exp(q[..., 1])
    n = q.shape[-1] - 3
    h = mu + s * q[..., 3] / np.sqrt(1 - rho * rho)
    for i in range(1, n):
        h = mu + rho * (h - mu) + s * q[..., 3 + i]
    return h


def pyextra(ds, big_n, k, seed, ticks, outdir, workdir):
    import owalnuts
    outdir, workdir = Path(outdir), Path(workdir)
    if outdir.exists():
        sys.exit(f"output exists: {outdir}")
    outdir.mkdir(parents=True)
    log = open(outdir / "ticks.jsonl", "w")
    lib = ctypes.CDLL(str(workdir / "libsv.so"))
    lib.sv_logp_grad.restype = ctypes.c_double
    lib.sv_logp_grad.argtypes = [ctypes.c_ssize_t, ctypes.POINTER(ctypes.c_double), ctypes.POINTER(ctypes.c_double), ctypes.c_void_p]
    rho = data(ds)["rho"]
    # C target vs Rust eval at 5 points (recorded, not gated): same density up to the lgamma constant.
    rng = np.random.default_rng(88 + big_n)
    pri = data(ds)["priors"]
    pts = [np.r_[pri["mu_mean"] + rng.normal(), np.log(.2) + .3 * rng.normal(), .001 * rng.normal(), rng.normal(size=big_n)]
           for _ in range(5)]
    pj, oj = workdir / f"pyextra-pts-{ds}-{big_n}.json", workdir / f"pyextra-out-{ds}-{big_n}.json"
    pj.write_text(json.dumps([p.tolist() for p in pts]))
    subprocess.run([str(rust_bin(workdir)), "eval", data_path(ds), str(big_n), str(pj), str(oj)], check=True)
    rust = json.loads(oj.read_text())
    _, keep = c_target(lib, ds, big_n, owalnuts)
    diffs, gerr = [], 0.0
    for p, r in zip(pts, rust):
        g = np.zeros(3 + big_n)
        lp = lib.sv_logp_grad(3 + big_n, p.ctypes.data_as(ctypes.POINTER(ctypes.c_double)),
                              g.ctypes.data_as(ctypes.POINTER(ctypes.c_double)), ctypes.addressof(keep[0]))
        diffs.append(lp - r["lp"])
        gerr = max(gerr, float(np.max(np.abs(g - np.asarray(r["grad"])) / (1 + np.abs(np.asarray(r["grad"]))))))
    check_rec = dict(tick=-1, event="c_target_check", lp_offset_spread=float(np.ptp(diffs)), max_rel_grad_err=gerr)
    log.write(json.dumps(check_rec) + "\n")
    # Tick 0: full fit through the Python API (defaults, 4 x 1000/1000, 4 threads).
    cft, keep = c_target(lib, ds, big_n, owalnuts)
    t0 = time.perf_counter()
    r0 = owalnuts.sample(cft, 3 + big_n, chains=4, warmup=1000, draws=1000, seed=seed, threads=4)
    wall0 = time.perf_counter() - t0
    q = r0.samples
    write_f32(outdir / "tick-000.f32", q[..., 0], q[..., 1], h_last_np(q, rho))
    state = r0.warm_state()
    log.write(json.dumps(dict(tick=0, n=big_n, status="ok", wall_seconds=wall0, chains=4, draws=1000,
                              steps=[float(x) for x in state.step_sizes], library_wall=r0.wall_seconds,
                              divergences=[int(x) for x in r0.divergent.sum(axis=1)])) + "\n")
    log.flush()
    for tick in range(1, ticks + 1):
        n = big_n + tick
        t0 = time.perf_counter()
        cft, keep = c_target(lib, ds, n, owalnuts)
        grown = state.extend_to(3 + n, 0.0, 1.0)
        r = owalnuts.sample_warm(cft, grown, draws=k, seed=seed * 1000003 + 16 * tick, threads=4)
        state = r.warm_state()
        wall = time.perf_counter() - t0
        q = r.samples
        write_f32(outdir / f"tick-{tick:03}.f32", q[..., 0], q[..., 1], h_last_np(q, rho))
        rec = dict(tick=tick, n=n, status="ok", wall_seconds=wall, library_wall=r.wall_seconds, k=k, chains=4,
                   draws=int(q.shape[1]), divergences=[int(x) for x in r.divergent.sum(axis=1)],
                   calls=int(r.target_calls))
        log.write(json.dumps(rec) + "\n")
        log.flush()


# ── queues ──────────────────────────────────────────────────────────────────────────────────

def cell_cmd(c, workdir):
    bin_, py = str(rust_bin(workdir)), sys.executable
    out = str(HERE / "artifacts" / "cells" / c["id"])
    if c["arm"] == "ref":
        return [py, str(HERE / "run_cells.py"), "ref", c["ds"], str(c["N"]), out, str(workdir)]
    if c["arm"] == "warm":
        return [bin_, "warm", data_path(c["ds"]), str(c["N"]), str(c["K"]), str(c["seed"]), str(c["ticks"]), out]
    if c["arm"] == "refit":
        return [bin_, "refit", data_path(c["ds"]), str(c["N"]), str(c["seed"]), str(c["ticks"]), out]
    if c["arm"] in ("cmdstan", "nutpie"):
        return [py, str(HERE / "run_cells.py"), "stan", c["arm"], c["ds"], str(c["N"]), str(c["seed"]), str(c["ticks"]),
                out, str(workdir)]
    if c["arm"] == "pyextra":
        venv_py = os.environ["WP88_PYVENV"]
        return [venv_py, "-I", str(HERE / "run_cells.py"), "pyextra", c["ds"], str(c["N"]), str(c["K"]), str(c["seed"]),
                str(c["ticks"]), out, str(workdir)]
    raise ValueError(c)


def run_queue(name, workdir):
    workdir = Path(workdir)
    art = HERE / "artifacts" / "cells"
    art.mkdir(parents=True, exist_ok=True)
    for c in PROTO["cells"]:
        if c["queue"] != name:
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
    if cmd == "check":
        check(sys.argv[2])
    elif cmd == "prep":
        prep(sys.argv[2])
    elif cmd == "ref":
        ref(sys.argv[2], int(sys.argv[3]), sys.argv[4], sys.argv[5])
    elif cmd == "stan":
        stan_arm(sys.argv[2], sys.argv[3], int(sys.argv[4]), int(sys.argv[5]), int(sys.argv[6]), sys.argv[7], sys.argv[8])
    elif cmd == "pyextra":
        pyextra(sys.argv[2], int(sys.argv[3]), int(sys.argv[4]), int(sys.argv[5]), int(sys.argv[6]), sys.argv[7], sys.argv[8])
    elif cmd == "plan":
        for q in ("A", "B", "C"):
            print("queue", q, [c["id"] for c in PROTO["cells"] if c["queue"] == q])
    elif cmd == "queue":
        run_queue(sys.argv[2], sys.argv[3])
