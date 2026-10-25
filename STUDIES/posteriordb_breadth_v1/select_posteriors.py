#!/usr/bin/env python3
"""Frozen WP46 selection rule, applied to the posteriordb checkout before any sampling.

    python -I select_posteriors.py   ->  artifacts/selection.json

Eligible: posteriors at posteriordb 28f8d3d with a reference_posterior_name, minus the 17
posteriors of posteriordb_bench_v5/v6. For each eligible posterior the diagonal-metric
difficulty proxy is computed from the posteriordb reference draws only (correlation-matrix
condition number of the reference parameter columns; ties broken by name).

Reference tier rule:
  (a) include every eligible posterior that is the only eligible member of its dataset family
      (family = the data name with a trailing year stripped, so nes1972..nes1996 are one family);
  (b) from each multi-member family, include the 2 members with the largest condition number
      if the family has >= 4 eligible members, otherwise the 1 largest.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import numpy as np
from posteriordb import PosteriorDatabase

HERE = Path(__file__).resolve().parent
PDB = PosteriorDatabase(str(HERE / "posteriordb" / "posterior_database"))
USED = json.loads((HERE.parent / "posteriordb_bench_v6" / "protocol.json").read_text(encoding="utf-8"))["models"]


def family(data_name: str) -> str:
    return re.sub(r"\d{4}$", "", data_name)


def main() -> None:
    stats = {}
    for name in PDB.posterior_names():
        p = PDB.posterior(name)
        if not p.posterior_info.get("reference_posterior_name") or name in USED:
            continue
        ref = p.reference_draws()
        cols = list(ref[0].keys())
        arr = np.asarray([[c[n] for n in cols] for c in ref], dtype=float)
        flat = np.transpose(arr, (0, 2, 1)).reshape(-1, len(cols))
        sd = flat.std(0, ddof=1)
        keep = sd > 0
        if keep.sum() > 1:
            ev = np.linalg.eigvalsh(np.corrcoef(flat[:, keep], rowvar=False))
            cond = float(ev[-1] / ev[0]) if ev[0] > 1e-14 else float("inf")
            off = np.abs(np.corrcoef(flat[:, keep], rowvar=False) - np.eye(int(keep.sum())))
            maxcorr = float(off.max())
        else:
            cond, maxcorr = 1.0, 0.0
        stats[name] = {
            "model": p.model.name, "data": p.data.name, "family": family(p.data.name),
            "n_ref_params": len(cols), "ref_chains": int(arr.shape[0]), "ref_draws": int(arr.shape[2]),
            "corr_condition_number": cond, "max_abs_corr": maxcorr,
            "sd_ratio": float(sd[keep].max() / sd[keep].min()),
        }
    fams: dict[str, list[str]] = {}
    for n, s in stats.items():
        fams.setdefault(s["family"], []).append(n)
    used_families = {family(PDB.posterior(m).data.name) for m in USED}
    selected = []
    for fam, members in sorted(fams.items()):
        ranked = sorted(members, key=lambda n: (-stats[n]["corr_condition_number"], n))
        k = 1 if len(members) == 1 else (2 if len(members) >= 4 else 1)
        for n in ranked[:k]:
            selected.append({"posterior": n, "family": fam, "family_members_eligible": len(members),
                             "family_used_in_v6": fam in used_families, "rank_in_family": ranked.index(n) + 1,
                             **stats[n]})
    out = {"eligible": len(stats), "families": {f: sorted(m) for f, m in sorted(fams.items())},
           "selected": selected, "statistics": stats}
    (HERE / "artifacts").mkdir(exist_ok=True)
    (HERE / "artifacts" / "selection.json").write_text(json.dumps(out, indent=1) + "\n", encoding="utf-8")
    for s in selected:
        print(f"{s['posterior']:50s} family={s['family']:22s} n={s['family_members_eligible']} cond={s['corr_condition_number']:.4g} P={s['n_ref_params']}")
    print(len(selected), "selected of", len(stats), "eligible")


if __name__ == "__main__":
    main()
