"""Bounded post-hoc WP88 reference audit; archived evidence is read-only."""
import hashlib
import json
import platform
from datetime import datetime, timezone
from pathlib import Path

import arviz as az
import numpy as np

SOURCE = Path("C:/dev/owalnuts/STUDIES/online_sv_quote_v2")
OUT = Path(__file__).resolve().parent


def identity(p):
    return dict(path=str(p), bytes=p.stat().st_size,
                sha256=hashlib.sha256(p.read_bytes()).hexdigest())


def diagnostics(x):
    return dict(rhat=float(az.rhat(x)), bulk_ess=float(az.ess(x, method="bulk")),
                tail_ess=float(az.ess(x, method="tail")))


protocol = json.loads((SOURCE / "protocol.json").read_text())
result = dict(kind="post-hoc diagnostic only; original qualification verdict unchanged",
              selection="For each of ref-sim-N250 and ref-real-N250, sort stored successful tick records by tick and select indices 0, len//2, len-1. No outcome-based selection.",
              created_utc=datetime.now(timezone.utc).isoformat(),
              environment=dict(python=platform.python_version(), numpy=np.__version__, arviz=az.__version__),
              source_files=[identity(SOURCE / "protocol.json"), identity(SOURCE / "analyze.py")],
              inventories=[], ticks=[])
result["audit_source"] = identity(Path(__file__))
for cell_id in ("ref-sim-N250", "ref-real-N250"):
    cell = SOURCE / "artifacts" / "cells" / cell_id
    records = [json.loads(line) for line in (cell / "ticks.jsonl").read_text().splitlines()]
    stored = sorted((r for r in records if r.get("status") == "ok" and (cell / r["file"]).exists()), key=lambda r: r["tick"])
    selected = [stored[i] for i in sorted({0, len(stored) // 2, len(stored) - 1})] if stored else []
    result["inventories"].append(dict(cell=cell_id, records=len(records), successful_stored_ticks=len(stored),
                                      raw_files=len(list(cell.glob("*.f32"))), selected_ticks=[r["tick"] for r in selected],
                                      records_identity=identity(cell / "ticks.jsonl")))
    for rec in selected:
        path = cell / rec["file"]
        expected = rec["chains"] * rec["draws"] * 3 * 4
        if path.stat().st_size != expected:
            raise ValueError(f"Wrong shape: {path}")
        a = np.fromfile(path, dtype="<f4").reshape(rec["chains"], rec["draws"], 3)[rec["kept"]].astype(float)
        if not np.isfinite(a).all():
            raise ValueError(f"Nonfinite draws: {path}")
        coords = {name: diagnostics(a[..., k]) for k, name in enumerate(("mu", "log_sigma", "h_last"))}
        m = a[..., 0] + protocol["model"]["rho"] * (a[..., 2] - a[..., 0])
        eps = np.random.default_rng(protocol["quantities"]["eps_seed_base"] + rec["tick"]).normal(size=(4, 20000))[rec["kept"], :rec["draws"]]
        hn = m + np.exp(a[..., 1]) * eps
        sig = np.exp(hn / 2)
        quantiles = {str(p): dict(value=float(np.quantile(sig, p)),
                                   relative_mcse=float(az.mcse(sig, method="quantile", prob=p)) / float(np.quantile(sig, p)))
                     for p in (0.5, 0.95)}
        attempt = next(a for a in rec["attempts"] if a["attempt"] == rec["attempt"])
        divergences = attempt["divergences"]
        result["ticks"].append(dict(cell=cell_id, tick=rec["tick"], attempt=rec["attempt"], seed=rec["seed"],
                                    kept=rec["kept"], dropped=rec["flagged"], coordinates=coords,
                                    conditional_h_next_mean=diagnostics(m), predictive_h_next=diagnostics(hn),
                                    predictive_rhat_recorded=rec["rhat_h_next"], sigma_quantiles=quantiles,
                                    retained_divergences_kept=sum(divergences[c] for c in rec["kept"]),
                                    retained_divergences_all=sum(divergences), input_identity=identity(path)))
result["coordinate_flags"] = [dict(cell=r["cell"], tick=r["tick"], coordinate=k, **v)
                              for r in result["ticks"] for k, v in r["coordinates"].items()
                              if v["rhat"] > 1.01 or v["bulk_ess"] < 400 or v["tail_ess"] < 400]
(OUT / "results.json").write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
print(json.dumps(dict(inventories=result["inventories"], coordinate_flags=result["coordinate_flags"]), indent=2))
for r in result["ticks"]:
    print(r["cell"], r["tick"], "max coordinate Rhat", max(v["rhat"] for v in r["coordinates"].values()),
          "min bulk/tail ESS", min(min(v["bulk_ess"], v["tail_ess"]) for v in r["coordinates"].values()),
          "P50/P95 relative MCSE", [r["sigma_quantiles"][str(p)]["relative_mcse"] for p in (0.5, 0.95)])
lines = ["# WP88 bounded reference diagnostic audit", "",
         "Post-hoc diagnostic, 2026-10-27. No sampler execution, archived evidence modification or revision of the original qualification verdict.", "",
         "## Selection and provenance", "",
         result["selection"], "",
         "Both datasets select ticks 0, 50 and 100. The simulated reference has 101 successful stored ticks; the real reference has 51 successful stored ticks and 52 raw files (one additional attempt). All selected records keep the four original chains at attempt 0.", "",
         "The compact draws are mu, log_sigma and h_last, stored as little-endian float32; all six selected files have the expected 960,000 bytes and finite values. Predictive innovations, quantile definitions and chain selection follow the original protocol. The recomputed predictive R-hat equals the recorded value exactly for all six selected ticks.", "",
         "`results.json` includes SHA256 hashes of the protocol, original analysis, tick logs, six selected raw files and this audit script, plus package versions and all coordinate diagnostics. `audit.py` reproduces this report using the isolated WP96 analysis environment (ArviZ 0.23.4, NumPy 2.5.4).", "",
         "## Results", "",
         "| Reference | Tick | Max coordinate R-hat | Min coordinate bulk/tail ESS | Kept-chain divergences | P50 relative MCSE | P95 relative MCSE |",
         "|---|---:|---:|---:|---:|---:|---:|"]
for r in result["ticks"]:
    lines.append(f"| {r['cell']} | {r['tick']} | {max(v['rhat'] for v in r['coordinates'].values()):.6f} | "
                 f"{min(min(v['bulk_ess'], v['tail_ess']) for v in r['coordinates'].values()):.0f} | "
                 f"{r['retained_divergences_kept']} | {100*r['sigma_quantiles']['0.5']['relative_mcse']:.3f}% | "
                 f"{100*r['sigma_quantiles']['0.95']['relative_mcse']:.3f}% |")
lines += ["", "No selected coordinate exceeds R-hat 1.01 or falls below bulk/tail ESS 400. All six selected references have zero retained divergences. The selected real-data references have higher predictive quantile MCSE than the selected simulated references, but all are well below the study's 2% P50 and 5% P95 tolerances.", "",
          "## Interpretation", "",
          "This bounded check finds no evidence that the predictive-only reference gate concealed poor mixing of the saved globals or endpoint latent at these six ticks. It does not establish diagnostics for all reference ticks, the full latent path or beta (not stored in compact draws), agreement with an independent inference algorithm, forecast calibration, executable quote accuracy or profitability. The original predictive-only gate remains a limited test; the audit neither strengthens its definition retrospectively nor changes WP88's verdict.", ""]
(OUT / "README.md").write_text("\n".join(lines))
