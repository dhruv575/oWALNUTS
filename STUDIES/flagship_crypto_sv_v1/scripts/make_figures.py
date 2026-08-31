"""Figures for the flagship crypto SV study and notebook.

figures/funnel.png       - the correctness opener, from WP14's frozen artifacts
figures/volatility.png   - annualized volatility paths with 90% bands, 5 assets
Colors are colorblind-safe on a light ground: blue #3b6fb6, orange #d1731e,
grey #6a7076; light background so the figure reads in both notebook themes.
"""

import json
import pathlib

import numpy as np
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = pathlib.Path(__file__).resolve().parents[1]
WP14 = ROOT.parent / "numpyro_comparisons_v10_v1"
BLUE, ORANGE, GREY = "#3b6fb6", "#d1731e", "#6a7076"
SYMBOLS = ["BTC", "ETH", "XRP", "BNB", "SOL"]


def funnel_figure():
    """oWALNUTS exact vs NumPyro missing the neck, against the analytic N(0,9)."""
    summary = json.loads((WP14 / "artifacts" / "summary.json").read_text())
    rows = summary["3_funnel"]["rows"]
    ow = [r for r in rows if r["arm"] == "FN-F"]
    np_rows = [r for r in rows if r["backend"] == "numpyro"]
    # omega draws from one owalnuts run (chains x draws x 10, omega is coord 0).
    seed = ow[0]["seed"]
    dim = 10
    raw = np.fromfile(WP14 / "artifacts" / "funnel" / f"funnel-FN-F-{seed}.f64")
    draws = raw.reshape(4, -1, dim)
    omega = draws[:, :, 0].reshape(-1)

    fig, (ax1, ax2) = plt.subplots(
        1, 2, figsize=(10.5, 4.0), gridspec_kw={"width_ratios": [1.6, 1.0]}
    )
    fig.patch.set_facecolor("white")
    xs = np.linspace(-10, 10, 400)
    exact = np.exp(-0.5 * (xs / 3.0) ** 2) / (3.0 * np.sqrt(2 * np.pi))
    ax1.hist(omega, bins=120, density=True, color=BLUE, alpha=0.55,
             label="oWALNUTS draws (paper tuning)")
    ax1.plot(xs, exact, color="black", lw=1.4, label="exact N(0, 3$^2$) marginal")
    ax1.axvline(-5, color=GREY, lw=0.8, ls="--")
    ax1.set_xlabel("$\\omega$ (funnel scale parameter)")
    ax1.set_ylabel("density")
    ax1.set_title("Neal's funnel, $\\omega$ marginal")
    ax1.legend(frameon=False, fontsize=9)
    ax1.set_facecolor("white")

    labels, values, colors = ["exact"], [0.04779], ["black"]
    for i, r in enumerate(ow):
        tm = next(t for t in r["tail_mass"] if t["threshold"] == -5.0)
        labels.append(f"oW {i + 1}")
        values.append(tm["observed"])
        colors.append(BLUE)
    for r in np_rows:
        tm = next(t for t in r["tail_mass"] if t["threshold"] == -5.0)
        acc = r.get("settings", {}).get("target_accept", r.get("target_accept", "?"))
        labels.append(f"NP {r['seed'] % 10}\n@{acc}")
        values.append(tm["observed"])
        colors.append(ORANGE)
    ax2.bar(range(len(values)), values, color=colors, alpha=0.8)
    ax2.axhline(0.04779, color="black", lw=1.0, ls=":")
    ax2.set_xticks(range(len(values)), labels, fontsize=7)
    ax2.text(0.02, 0.72, "oWALNUTS = blue\nNumPyro NUTS = orange",
             ha="left", va="top", transform=ax2.transAxes, fontsize=8)
    ax2.set_ylabel("P($\\omega < -5$)")
    ax2.set_title("Mass below $\\omega=-5$ (exact: 0.0478)")
    div_total = sum(r.get("divergences", 0) for r in np_rows)
    ax2.text(0.98, 0.95, f"NumPyro divergences: {div_total}",
             ha="right", va="top", transform=ax2.transAxes, fontsize=8, color=ORANGE)
    fig.tight_layout()
    out = ROOT / "figures" / "funnel.png"
    fig.savefig(out, dpi=150)
    print("wrote", out)


def volatility_figure():
    fig, axes = plt.subplots(len(SYMBOLS), 1, figsize=(10.5, 2.1 * len(SYMBOLS)), sharex=False)
    fig.patch.set_facecolor("white")
    for ax, sym in zip(axes, SYMBOLS):
        doc = json.loads((ROOT / "data" / f"{sym}.json").read_text())
        dates = [row[0] for row in doc["closes"]][1:]
        d = np.load(ROOT / "artifacts" / "draws" / f"{sym}-native-97001.npz") if (
            ROOT / "artifacts" / "draws" / f"{sym}-native-97001.npz").exists() else None
        if d is None:
            # native draws are .f64; quantiles from raw
            t = len(dates)
            raw = np.fromfile(ROOT / "artifacts" / "draws" / f"{sym}-native-97001.f64")
            draws = raw.reshape(4, -1, t + 3)[:, :, 3:].reshape(-1, t)
            q05, q50, q95 = np.percentile(draws, [5, 50, 95], axis=0)
        else:
            q05, q50, q95 = d["h_q05"], d["h_q50"], d["h_q95"]
        ann = np.sqrt(365.0)
        vol = lambda h: 100.0 * ann * np.exp(h / 2.0)
        x = np.arange(len(dates))
        ax.fill_between(x, vol(q05), vol(q95), color=BLUE, alpha=0.25, lw=0,
                        label="90% band")
        ax.plot(x, vol(q50), color=BLUE, lw=0.9, label="posterior median")
        ticks = np.linspace(0, len(dates) - 1, 6).astype(int)
        ax.set_xticks(ticks, [dates[i][:7] for i in ticks], fontsize=7)
        ax.set_ylabel(f"{sym}\nann. vol %", fontsize=8)
        ax.set_facecolor("white")
        if ax is axes[0]:
            ax.legend(frameon=False, fontsize=8, loc="upper right")
            ax.set_title("Posterior annualized volatility, oWALNUTS full SV posterior")
    fig.tight_layout()
    out = ROOT / "figures" / "volatility.png"
    fig.savefig(out, dpi=150)
    print("wrote", out)


if __name__ == "__main__":
    (ROOT / "figures").mkdir(exist_ok=True)
    funnel_figure()
    try:
        volatility_figure()
    except FileNotFoundError as e:
        print("volatility figure skipped (evidence not complete):", e)
