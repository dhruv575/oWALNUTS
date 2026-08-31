"""Build and execute the public-facing notebook from the study artifacts.

Creates integrations/python/examples/crypto_sv.ipynb (executed, outputs
embedded) plus a self-contained copy of the figures and BTC data next to it.
Every quantitative claim in the notebook is read from the study artifacts at
execution time; the one live sampling cell runs a short demo budget and is
labelled as such.
"""

import json
import pathlib
import shutil

import nbformat as nbf
from nbclient import NotebookClient

STUDY = pathlib.Path(__file__).resolve().parents[1]
EXAMPLES = STUDY.parents[1] / "integrations" / "python" / "examples"
ASSETS = EXAMPLES / "crypto_sv_assets"


def md(source):
    return nbf.v4.new_markdown_cell(source)


def code(source):
    return nbf.v4.new_code_cell(source)


def build():
    ASSETS.mkdir(parents=True, exist_ok=True)
    for name in ("funnel.png", "volatility.png"):
        shutil.copyfile(STUDY / "figures" / name, ASSETS / name)
    shutil.copyfile(STUDY / "data" / "BTC.json", ASSETS / "BTC.json")
    shutil.copyfile(STUDY / "artifacts" / "summary.json", ASSETS / "summary.json")
    shutil.copyfile(
        STUDY / "artifacts" / "calibration" / "BTC-97001.json",
        ASSETS / "BTC-calibration-97001.json",
    )

    nb = nbf.v4.new_notebook()
    nb.metadata["kernelspec"] = {"name": "python3", "display_name": "Python 3", "language": "python"}
    cells = []

    cells.append(md(
        "# Stochastic volatility on the five largest cryptocurrencies with oWALNUTS\n\n"
        "This notebook samples the **full posterior** of a standard stochastic-volatility model —\n"
        "$r_t = e^{h_t/2}\\varepsilon_t$, $h_t = \\mu + \\phi(h_{t-1}-\\mu) + \\sigma\\eta_t$ —\n"
        "over every daily close in each asset's history (T up to 3,153, so up to 3,156 parameters),\n"
        "using [oWALNUTS](https://github.com/dhruv575/oWALNUTS): a Rust implementation of the\n"
        "within-orbit adaptive leapfrog No-U-Turn sampler (JMLR 2026) with linear-time structured\n"
        "metrics and a one-line PyMC entry point.\n\n"
        "Everything here is backed by the preregistered study\n"
        "`STUDIES/flagship_crypto_sv_v1` in the oWALNUTS repository (protocol, seeds, checksums,\n"
        "and a ledger entry); numbers shown below are loaded from its artifacts."
    ))

    cells.append(md(
        "## Why care: NUTS can silently miss part of the posterior\n\n"
        "On Neal's funnel — the classic hard geometry, with an exactly known marginal —\n"
        "NumPyro's NUTS places **almost zero** mass below $\\omega=-5$ where the true mass is 4.78%,\n"
        "emitting thousands of divergences; oWALNUTS at the paper's tuning matches the analytic\n"
        "marginal on every seed with zero divergences\n"
        "(study `STUDIES/numpyro_comparisons_v10_v1`, kernel v10):\n\n"
        "![funnel](crypto_sv_assets/funnel.png)"
    ))

    cells.append(code(
        "import json, pathlib, numpy as np\n"
        "assets = pathlib.Path('crypto_sv_assets')\n"
        "doc = json.loads((assets / 'BTC.json').read_text())\n"
        "closes = np.array([row[1] for row in doc['closes']])\n"
        "r = np.log(closes[1:] / closes[:-1])\n"
        "print(f\"BTC-USDT daily closes {doc['first']} to {doc['last']}  (T = {len(r)} returns)\")"
    ))

    cells.append(md(
        "## One line from PyMC\n\n"
        "Define the SV model in PyMC as usual; `owalnuts.from_pymc(model, gil_free=True)` compiles\n"
        "the joint log-density gradient to a GIL-free callback, so four chains sample in parallel\n"
        "from Rust. The structured metric — the AR(1)-plus-curvature tridiagonal precision of the\n"
        "latent path — is one call. *(Demo budget below: 300 warmup / 500 draws so the cell runs in\n"
        "seconds; the study runs 1,000/3,000 — see the results table.)*"
    ))

    cells.append(code(
        "import owalnuts, pymc as pm, pytensor.tensor as pt\n"
        "T = len(r)\n"
        "with pm.Model() as model:\n"
        "    mu = pm.Normal('mu', -10, 5)\n"
        "    phi_raw = pm.Beta('phi_raw', 20, 1.5)\n"
        "    phi = 2 * phi_raw - 1\n"
        "    sigma = pm.HalfNormal('sigma', 0.5)\n"
        "    pm.AR('h', rho=[mu * (1 - phi), phi], sigma=sigma, constant=True,\n"
        "          init_dist=pm.Normal.dist(mu, sigma / pt.sqrt(1 - phi**2)), shape=T)\n"
        "    pm.Normal('r', 0.0, pt.exp(model['h'] / 2), observed=r)\n"
        "\n"
        "target, dim, q0, names, unravel = owalnuts.from_pymc(model, gil_free=True)\n"
        "\n"
        "# One-shot structured metric from the study's stage-A calibration (see PREREGISTRATION.md)\n"
        "cal = json.loads((assets / 'BTC-calibration-97001.json').read_text())\n"
        "phi_h, s2 = cal['phi_hat'], cal['sigma_hat'] ** 2\n"
        "h_mean = np.asarray(cal['h_mean'])\n"
        "diag = np.full(T, (1 + phi_h**2) / s2); diag[[0, -1]] = 1 / s2\n"
        "diag += 0.5 * r**2 * np.exp(-h_mean)\n"
        "off = np.full(T - 1, -phi_h / s2)\n"
        "cov = 2.0 * np.asarray(cal['global_cov']).reshape(3, 3)\n"
        "prec = np.linalg.inv(cov)\n"
        "mass = owalnuts.tridiagonal_precision_mass(\n"
        "    np.array([prec[0, 0], prec[1, 1], prec[2, 2]]), np.array([prec[0, 1], prec[1, 2]])\n"
        ") + owalnuts.tridiagonal_precision_mass(diag, off)\n"
        "\n"
        "base = np.concatenate([[cal['mu_hat'], cal['a_hat'], cal['s_hat']], h_mean])\n"
        "starts = base + 0.3 * np.random.default_rng(1).standard_normal((4, dim))\n"
        "result = owalnuts.sample(\n"
        "    target, dim, init=starts, chains=4, warmup=300, draws=500, seed=1, threads=4,\n"
        "    tuning=owalnuts.Tuning(step_size=0.1, max_depth=9, max_refinement_levels=6),\n"
        "    adaptation=owalnuts.Adaptation(adapt_mass=False, paper=owalnuts.PaperAdaptation()),\n"
        "    mass=mass, max_target_evaluations=1_000_000_000)\n"
        "print(f'wall {result.wall_seconds:.1f}s, {result.target_calls:,} gradient evaluations, '\n"
        "      f'divergences {int(result.divergent.sum())}')\n"
        "post = result.samples\n"
        "phi_draws = 2 / (1 + np.exp(-post[:, :, 1])) - 1\n"
        "print(f'phi = {phi_draws.mean():.3f}, sigma = {np.exp(post[:, :, 2]).mean():.3f} (demo budget)')"
    ))

    cells.append(md("## The five-asset study (preregistered evidence)\n"))

    cells.append(code(
        "import pandas as pd\n"
        "summary = json.loads((assets / 'summary.json').read_text())\n"
        "rows = []\n"
        "for res in summary['results']:\n"
        "    if res.get('missing'):\n"
        "        continue\n"
        "    d, m = res['diagnostics'], res['meta']\n"
        "    rows.append({\n"
        "        'asset': res['symbol'], 'cell': res['cell'], 'seed': res['seed'],\n"
        "        'primary health': 'PASS' if res['gates']['primary'] else 'fail',\n"
        "        'globals gate': 'PASS' if res['gates']['globals'] else 'fail',\n"
        "        'min primary ESS': round(res['min_bulk_primary']),\n"
        "        'phi': round(d['phi_mean'], 3), 'sigma': round(d['sigma_mean'], 3),\n"
        "        'wall s': round(m['wall_sampling'], 1), 'divergences': m['divergences'],\n"
        "    })\n"
        "pd.DataFrame(rows)"
    ))

    cells.append(md(
        "## Posterior volatility paths\n\n"
        "Annualized volatility $100\\sqrt{365}\\,e^{h_t/2}$ with 90% posterior bands, from the\n"
        "oWALNUTS evidence runs:\n\n"
        "![volatility](crypto_sv_assets/volatility.png)"
    ))

    cells.append(md(
        "## Honest limitations\n\n"
        "- **Not every cell passed the preregistered health gates.** At this budget oWALNUTS passes\n"
        "  primary health on XRP/SOL/BNB but not BTC/ETH (T ≈ 3,150), where NumPyro/nutpie's\n"
        "  windowed adaptation extracts more global ESS; and the `from_pymc` arm hit stuck seeds on\n"
        "  ETH/SOL (R-hat up to 1.65, zero divergences) from unlucky starts under the frozen metric.\n"
        "  Full tables: `STUDIES/flagship_crypto_sv_v1/artifacts/RESULTS.md`.\n"
        "- **The global ridge is everyone's bottleneck.** corr$(a,s)\\approx-0.9$ throttles the\n"
        "  effective sample size of $(\\phi, \\sigma)$ in *every* backend tested (oWALNUTS, nutpie,\n"
        "  NumPyro). Block-diagonal metrics cannot express the global-path coupling; that is the\n"
        "  next research item (the arrowhead line).\n"
        "- **Pure-JAX models remain NumPyro's home turf** — oWALNUTS' advantage needs a compiled\n"
        "  gradient (PyMC/numba, Stan via BridgeStan, or Rust).\n"
        "- Wall times were measured on a shared machine; ESS per gradient evaluation is the robust\n"
        "  comparison and is in the study artifacts.\n"
        "- The $\\sigma_x \\to 0$ funnel boundary of state-space models (fixture sspd-10) is unsolved\n"
        "  by every Euclidean sampler tested, including NUTS at depth 12.\n"
    ))

    nb.cells = cells
    client = NotebookClient(nb, timeout=900, kernel_name="python3",
                            resources={"metadata": {"path": str(EXAMPLES)}})
    client.execute()
    out = EXAMPLES / "crypto_sv.ipynb"
    nbf.write(nb, out)
    print("wrote and executed", out)


if __name__ == "__main__":
    build()
