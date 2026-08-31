"""Gate evaluation and results tables for the flagship crypto SV study."""

import json
import pathlib

import numpy as np
import arviz as az

ROOT = pathlib.Path(__file__).resolve().parents[1]
SYMBOLS = ["BTC", "ETH", "XRP", "BNB", "SOL"]
CELLS = ["native", "pymc", "pymcB", "nutpie", "numpyro"]
POOL_PAIRS = {98001: 98011, 98002: 98012, 98003: 98013}
SEEDS = {"native": [98001, 98002, 98003, 98011, 98012, 98013],
         "pymc": [98001, 98002, 98003, 98011, 98012, 98013],
         "pymcB": [98001, 98002, 98003],
         "nutpie": [97001], "numpyro": [97001]}
V1_ROOT = ROOT.parent / "flagship_crypto_sv_v1"  # frozen external reference cells
PRIMARY = ["mu", "h_T", "mean_h"]
GLOBALS = ["a", "s"]
T = {"BTC": 3153, "ETH": 3153, "XRP": 2433, "SOL": 2159, "BNB": 1348}


def _root(cell):
    return V1_ROOT if cell in ("nutpie", "numpyro") else ROOT


def load_functionals(symbol, cell, seed):
    if cell.startswith("native"):
        dim = T[symbol] + 3
        path = _root(cell) / "artifacts" / "draws" / f"{symbol}-{cell}-{seed}.f64"
        raw = np.fromfile(path)
        chains = 4
        draws = raw.size // (chains * dim)
        raw = raw.reshape(chains, draws, dim)
        a = raw[:, :, 1]
        return {
            "mu": raw[:, :, 0], "a": a, "s": raw[:, :, 2],
            "phi": 2.0 / (1.0 + np.exp(-a)) - 1.0, "sigma": np.exp(raw[:, :, 2]),
            "h_T": raw[:, :, -1], "mean_h": raw[:, :, 3:].mean(axis=2),
        }
    d = np.load(_root(cell) / "artifacts" / "draws" / f"{symbol}-{cell}-{seed}.npz")
    return {k: d[k] for k in ("mu", "a", "s", "phi", "sigma", "h_T", "mean_h")}


def load_meta(symbol, cell, seed):
    meta = json.loads((_root(cell) / "artifacts" / "runs" / f"{symbol}-{cell}-{seed}.json").read_text())
    if "wall_sampling" not in meta:  # native Rust runner schema
        meta["wall_sampling"] = meta["wall_seconds"]
        meta["wall_cell"] = meta["wall_seconds"]
        meta["work"] = meta["target_calls_total"]
        meta["work_unit"] = "fused target calls (exact)"
    meta.setdefault("cell", cell)
    return meta


def diagnostics(f):
    idata = az.from_dict(posterior={k: f[k] for k in ("mu", "a", "s", "h_T", "mean_h")})
    summ = az.summary(idata, kind="diagnostics")
    out = {}
    for name in ("mu", "a", "s", "h_T", "mean_h"):
        row = summ.loc[name]
        flat = f[name].reshape(-1)
        ess = max(float(row["ess_bulk"]), 1.0)
        out[name] = {
            "rhat": float(row["r_hat"]),
            "bulk_ess": float(row["ess_bulk"]),
            "tail_ess": float(row["ess_tail"]),
            "mean": float(flat.mean()),
            "sd": float(flat.std()),
            "mcse": float(flat.std() / np.sqrt(ess)),
        }
    out["phi_mean"] = float(f["phi"].mean())
    out["sigma_mean"] = float(f["sigma"].mean())
    return out


def gates(diag, meta):
    primary = all(
        diag[k]["rhat"] <= 1.01 and diag[k]["bulk_ess"] >= 400 and diag[k]["tail_ess"] >= 400
        for k in PRIMARY
    ) and meta.get("max_depth_rate", 0.0) <= 0.01
    owalnuts = meta["cell"] in ("native", "pymc")
    if owalnuts:
        primary = primary and meta["divergences"] == 0 and meta.get("invalid", 0) == 0 and meta.get("exhaustions", 0) == 0
    globals_gate = all(
        diag[k]["rhat"] <= 1.05 and diag[k]["bulk_ess"] >= 100 for k in GLOBALS
    )
    globals_strict = all(
        diag[k]["rhat"] <= 1.01 and diag[k]["bulk_ess"] >= 400 for k in GLOBALS
    )
    return {"primary": bool(primary), "globals": bool(globals_gate),
            "globals_strict_1p01_400": bool(globals_strict)}


def main():
    results = []
    for symbol in SYMBOLS:
        for cell in CELLS:
            for seed in SEEDS[cell]:
                try:
                    meta = load_meta(symbol, cell, seed)
                except FileNotFoundError:
                    if cell not in ("pymcB",) and seed not in (98011, 98012, 98013):
                        results.append({"symbol": symbol, "cell": cell, "seed": seed, "missing": True})
                    continue
                f = load_functionals(symbol, cell, seed)
                diag = diagnostics(f)
                g = gates(diag, meta)
                draws_total = f["mu"].size
                wall = meta["wall_sampling"]
                work = meta["work"]
                min_bulk_primary = min(diag[k]["bulk_ess"] for k in PRIMARY)
                results.append({
                    "symbol": symbol, "cell": cell, "seed": seed,
                    "diagnostics": diag, "gates": g, "meta": {
                        k: meta.get(k) for k in (
                            "wall_sampling", "wall_cell", "work", "work_unit",
                            "divergences", "max_depth_rate", "algorithm_revision",
                            "backend_version", "parity")
                    },
                    "min_bulk_primary": min_bulk_primary,
                    "primary_bulk_ess_per_s": min_bulk_primary / wall,
                    "primary_bulk_ess_per_work": min_bulk_primary / max(work, 1),
                    "a_bulk_ess_per_s": diag["a"]["bulk_ess"] / wall,
                    "draws_total": draws_total,
                })
    # Pooled 8-chain extension rows (Amendments A6/A7): identical config, 2x chains.
    def _stuck(f):
        d = diagnostics(f)
        return any(d[k]["rhat"] > 1.2 for k in ("mu", "a", "s", "h_T", "mean_h"))

    for symbol in SYMBOLS:
      for base_cell, pooled_cell in (("native", "native8c"), ("pymc", "pymc8c")):
        for seed, partner in POOL_PAIRS.items():
            try:
                fa = load_functionals(symbol, base_cell, seed)
                fb = load_functionals(symbol, base_cell, partner)
                ma = load_meta(symbol, base_cell, seed)
                mb = load_meta(symbol, base_cell, partner)
            except FileNotFoundError:
                continue
            if base_cell == "pymc" and (_stuck(fa) or _stuck(fb)):
                continue  # A7: stuck halves are never pooled
            f = {k: np.concatenate([fa[k], fb[k]], axis=0) for k in fa}
            diag = diagnostics(f)
            meta = {"cell": pooled_cell, "divergences": ma["divergences"] + mb["divergences"],
                    "invalid": ma.get("invalid", 0) + mb.get("invalid", 0),
                    "exhaustions": ma.get("exhaustions", 0) + mb.get("exhaustions", 0),
                    "max_depth_rate": max(ma.get("max_depth_rate", 0.0), mb.get("max_depth_rate", 0.0)),
                    "wall_sampling": ma["wall_sampling"] + mb["wall_sampling"],
                    "work": ma["work"] + mb["work"], "work_unit": ma["work_unit"],
                    "algorithm_revision": ma.get("algorithm_revision")}
            g = gates(diag, meta)
            min_bulk_primary = min(diag[k]["bulk_ess"] for k in PRIMARY)
            results.append({
                "symbol": symbol, "cell": pooled_cell, "seed": seed,
                "diagnostics": diag, "gates": g,
                "meta": {k: meta.get(k) for k in ("wall_sampling", "work", "work_unit", "divergences", "max_depth_rate", "algorithm_revision")},
                "min_bulk_primary": min_bulk_primary,
                "primary_bulk_ess_per_s": min_bulk_primary / meta["wall_sampling"],
                "primary_bulk_ess_per_work": min_bulk_primary / max(meta["work"], 1),
                "a_bulk_ess_per_s": diag["a"]["bulk_ess"] / meta["wall_sampling"],
                "draws_total": f["mu"].size,
            })
    # Agreement among healthy cells, per symbol.
    agreement = {}
    for symbol in SYMBOLS:
        healthy = [r for r in results if not r.get("missing") and r["symbol"] == symbol and r["gates"]["primary"]]
        pairs = []
        for i in range(len(healthy)):
            for j in range(i + 1, len(healthy)):
                worst = 0.0
                for k in ("mu", "a", "s", "h_T", "mean_h"):
                    da, db = healthy[i]["diagnostics"][k], healthy[j]["diagnostics"][k]
                    se = np.hypot(da["mcse"], db["mcse"])
                    worst = max(worst, abs(da["mean"] - db["mean"]) / max(se, 1e-12))
                pairs.append({
                    "a": f'{healthy[i]["cell"]}-{healthy[i]["seed"]}',
                    "b": f'{healthy[j]["cell"]}-{healthy[j]["seed"]}',
                    "worst_z": float(worst),
                    "pass": bool(worst <= 3.0),
                })
        agreement[symbol] = pairs
    summary = {"schema": "flagship-crypto-sv-v2/summary", "results": results, "agreement": agreement}
    (ROOT / "artifacts" / "summary.json").write_text(json.dumps(summary, indent=1))

    lines = ["| asset | cell | seed | primary | globals | R-hat a/s | bulk ESS a/s | min primary ESS | wall s | div |",
             "|---|---|---|---|---|---|---|---|---|---|"]
    for r in results:
        if r.get("missing"):
            lines.append(f"| {r['symbol']} | {r['cell']} | {r['seed']} | MISSING | | | | | | |")
            continue
        d = r["diagnostics"]
        lines.append(
            f"| {r['symbol']} | {r['cell']} | {r['seed']} | "
            f"{'PASS' if r['gates']['primary'] else 'fail'} | {'PASS' if r['gates']['globals'] else 'fail'} | "
            f"{d['a']['rhat']:.3f}/{d['s']['rhat']:.3f} | {d['a']['bulk_ess']:.0f}/{d['s']['bulk_ess']:.0f} | "
            f"{r['min_bulk_primary']:.0f} | {r['meta']['wall_sampling']:.1f} | {r['meta']['divergences']} |")
    (ROOT / "artifacts" / "RESULTS.md").write_text("\n".join(lines))
    print("\n".join(lines))


if __name__ == "__main__":
    main()
