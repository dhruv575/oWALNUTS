"""Regenerate demo/data/site-data.json from v2 evidence + v1 external refs.

Keeps the funnel section byte-identical (frozen WP14-derived numbers), rebuilds
`cells` from artifacts/summary.json, rebuilds per-asset volatility bands from
the best available v2 native draw file, and updates `meta`.
"""

import json
import pathlib

import numpy as np

ROOT = pathlib.Path(__file__).resolve().parents[1]
DEMO = ROOT.parents[1] / "demo"
SYMBOLS = ["BTC", "ETH", "XRP", "BNB", "SOL"]
MAX_POINTS = 700
ANN = 100.0 * np.sqrt(365.0)


def cells(summary):
    rows = []
    for r in summary["results"]:
        if r.get("missing"):
            continue
        d = r["diagnostics"]
        rows.append({
            "asset": r["symbol"], "cell": r["cell"], "seed": r["seed"],
            "primary": r["gates"]["primary"], "globals": r["gates"]["globals"],
            "min_ess": round(r["min_bulk_primary"], 1),
            "wall": round(r["meta"]["wall_sampling"], 1),
            "div": r["meta"]["divergences"],
            "ess_s": round(r["min_bulk_primary"] / r["meta"]["wall_sampling"], 1),
            "phi": round(d["phi_mean"], 3),
        })
    return rows


def asset_series(sym):
    doc = json.loads((ROOT / "data" / f"{sym}.json").read_text())
    dates = [row[0][:10] for row in doc["closes"]][1:]
    t = len(dates)
    dim = t + 3
    src = None
    for cell in ("native",):
        p = ROOT / "artifacts" / "draws" / f"{sym}-{cell}-98001.f64"
        if p.exists():
            src = (p, cell)
            break
    raw = np.fromfile(src[0])
    draws = raw.size // (4 * dim)
    h = raw.reshape(4, draws, dim)[:, :, 3:].reshape(-1, t)
    q05, q50, q95 = np.percentile(h, [5, 50, 95], axis=0)
    idx = np.unique(np.linspace(0, t - 1, min(t, MAX_POINTS)).astype(int))
    return {
        "dates": [dates[i] for i in idx],
        "lo": [round(float(ANN * np.exp(q05[i] / 2.0)), 1) for i in idx],
        "mid": [round(float(ANN * np.exp(q50[i] / 2.0)), 1) for i in idx],
        "hi": [round(float(ANN * np.exp(q95[i] / 2.0)), 1) for i in idx],
        "first": dates[0][:4], "last": dates[-1][:10], "T": t,
        "source_cell": src[1],
    }


def main():
    site = json.loads((DEMO / "data" / "site-data.json").read_text())
    summary = json.loads((ROOT / "artifacts" / "summary.json").read_text())
    new_cells = cells(summary)
    site["cells"] = new_cells
    for sym in SYMBOLS:
        keep = {k: site["assets"][sym].get(k) for k in ()}
        site["assets"][sym] = {**asset_series(sym), **keep}
    healthy_pairs = [p for pairs in summary["agreement"].values() for p in pairs]
    site["agreement"] = {
        "pairs": len(healthy_pairs),
        "passed": sum(1 for p in healthy_pairs if p["pass"]),
        "worst_z": round(max((p["worst_z"] for p in healthy_pairs), default=0.0), 2),
    }
    site["meta"].update({
        "seeds": "seeds 98001–98003 (oWALNUTS v2, 3 per arm) · 97001 (nutpie/NumPyro references, 1 seed)",
        "date": "2026-08-31",
        "study": "flagship_crypto_sv_v2",
    })
    ndiv = sum(c["div"] for c in new_cells)
    (DEMO / "data" / "site-data.json").write_text(json.dumps(site))
    print(f"site-data.json: {len(new_cells)} cells, total divergences {ndiv}, "
          f"agreement {site['agreement']}")


if __name__ == "__main__":
    main()
