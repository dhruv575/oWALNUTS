"""Assemble demo/data/story-data.json from committed study artifacts.

Every number on the demo's funnel / state-space / throughput / provenance
sections is read from a study artifact here, or copied from the research
ledger with its entry named, so the page stays traceable. Run from the crate
root: ``python demo/build_story_data.py``.
"""
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "demo" / "data" / "story-data.json"


def geomean(xs):
    return math.exp(sum(math.log(x) for x in xs) / len(xs))


def load(rel):
    return json.loads((ROOT / rel).read_text(encoding="utf-8"))


def cell_geomean(table, *path):
    """Geometric mean of ess_per_second over the seeds that ran this cell."""
    vals = []
    for seed in table:
        node = table[seed]
        for key in path:
            node = node.get(key) if isinstance(node, dict) else None
            if node is None:
                break
        if isinstance(node, dict) and "ess_per_second" in node:
            vals.append(node["ess_per_second"])
    return {"ess_s": geomean(vals), "seeds": len(vals)}


# ---- WP4: exact state-space ground truth (T=1000 arms) ----
gt = load("STUDIES/exact_state_space_ground_truth_v1/artifacts/summary.json")
ARM_NAMES = {
    "I": "identity",
    "D": "posterior-variance diagonal",
    "P": "posterior-precision tridiagonal (ours)",
    "Q": "prior-precision only (the v7 analogue)",
}
state_space = {
    "T": 1000,
    "chains": gt["index"]["chains"],
    "retained": gt["index"]["retained"],
    "max_depth": gt["index"]["max_depth"],
    "arms": {},
}
for r in gt["results"]:
    if r["t"] != 1000:
        continue
    a = state_space["arms"].setdefault(r["arm"], {"name": ARM_NAMES[r["arm"]], "seeds": []})
    a["seeds"].append({
        "seed": r["seed"],
        "depth_histogram": r["depth_histogram"],
        "cap_rate": r["max_depth_rate"],
        "min_bulk_ess": r["min_bulk_ess"],
        "ess_per_call": r["min_bulk_ess_per_retained_call"],
        "calls": r["target_calls_total"],
        "wall": r["wall_seconds"],
        "mean_z2": r["mean_z_squared"],
        "max_abs_z": r["max_abs_z"],
        "max_rhat": r["max_rhat"],
        "step": sum(r["final_step_sizes"]) / len(r["final_step_sizes"]),
        "median_depth": r["median_depth"],
    })

# ---- WP15b / WP18: Python-facing T=1000 local level ----
b15 = load("integrations/python/bench/artifacts/summary.json")["local_level"]["1000"]
b18 = load("integrations/python/bench/artifacts/gil-free-compare.json")["local_level_t1000"]
python_t1000 = {
    "native_identity_t1": cell_geomean(b15, "native_identity"),
    "native_precision_t1": cell_geomean(b15, "native_precision"),
    "numpy_precision_t1": cell_geomean(b15, "numpy_precision"),
    "numpyro_identity_t1": cell_geomean(b15, "numpyro_identity", "warm"),
    "cfunc_precision_t1": cell_geomean(b18, "cfunc_precision_t1"),
    "cfunc_precision_t4": cell_geomean(b18, "cfunc_precision_t4"),
}

# ---- WP4B / WP12 on the real Polyscope target (ledger entries) ----
real_target = {
    "source": "wiki/research-ledger-2026-08-31.md: WP4B-REAL-TARGET-PATH-METRIC-V1, WP12-SSPD11-CONFIRMATION-V1",
    "sspd11_P_over_I_ess_per_call": [2.573, 2.963, 2.683],
    "sspd11_wall_P": "7-9 s",
    "sspd11_wall_I": "24-28 s",
    "frozen_globals": {
        "sspd11": {"FP_ess_per_call": 0.13, "FI_ess_per_call": 0.0025, "FP_depth": 4, "FI_depth": 5},
        "sspd10": {"FP_ess_per_call": 0.10, "FI_ess_per_call": 0.0005, "FP_caps": 0.0, "FI_caps": 0.74},
    },
    "arm_I_confirmed": "3/3 seeds",
    "arm_P_confirmed": "2/3 seeds (one R-hat 1.0102 vs 1.01 miss)",
}

# ---- WP18 Eight Schools, 4-core PyMC comparison ----
es = load("integrations/python/bench/artifacts/gil-free-compare.json")["eight_schools"]
eight_schools = {
    "protocol": "PyMC Eight Schools, 4 chains x 1,000/1,000, accept .95, depth 8; seeds 96001-96003; geometric mean of min bulk ESS/s",
    "backends": [],
}
for key, label, note in [
    ("owalnuts_pymc_cfunc_t4", "oWALNUTS from_pymc(gil_free) 4 threads", "exact fused-call work"),
    ("nutpie_cores4", "nutpie 4 cores", "leapfrog-proxy work; compile time excluded"),
    ("nutpie_cores1", "nutpie 1 core", "leapfrog-proxy work; compile time excluded"),
    ("owalnuts_pymc_cfunc_t1", "oWALNUTS from_pymc(gil_free) 1 thread", "exact fused-call work"),
    ("owalnuts_pymc_gil_t1", "oWALNUTS from_pymc (GIL) 1 thread", "Python callback per gradient"),
    ("numpyro", "NumPyro NUTS via pm.sample", "leapfrog-proxy work"),
]:
    vals = [es[s][key]["ess_per_second"] for s in es]
    eight_schools["backends"].append({
        "key": key, "label": label, "note": note,
        "ess_s": geomean(vals), "per_seed": vals,
        "max_rhat": max(es[s][key]["max_rhat"] for s in es),
        "divergences": sum(es[s][key]["divergences"] for s in es),
    })

# ---- WP8 strict track (Rust, v38 protocol) ----
strict = {
    "source": "STUDIES/eight_schools_v9_rebench_v1/artifacts/RESULTS.md (WP8)",
    "owalnuts_v9_min_bulk": 12830.11,
    "owalnuts_v9_min_tail": 10345.91,
    "cmdstan_min_bulk": 6290.30,
    "blackjax_min_tail": 4195.13,
    "published_v7_median": 19054.65,
    "like_for_like_v7_min": 8634.35,
}

# ---- Funnel extras (WP2 v8 -> WP6 v9) ----
funnel_extra = {
    "source": "STUDIES/funnel_bias_fix_v1 (WP6) and STUDIES/paper_funnel_reproduction_v1 (WP2)",
    "v9_F50_p5": 0.0474, "v9_F50_p6": 0.0223, "v9_F50_var": 9.04, "v9_F50_q1": -7.01,
    "exact_p5": 0.04779, "exact_p6": 0.02275, "exact_var": 9.0, "exact_q1": -6.98,
    "v8_F50_p5": 0.0971, "v8_F50_var": 11.41,
    "reference_R36_p5": 0.0477,
    "oracle_leaves": 4000, "v8_disagreements": 1555, "v9_tolerance": "1e-11",
}

# ---- Provenance ----
studies = sorted(p.name for p in (ROOT / "STUDIES").iterdir() if (p / "PREREGISTRATION.md").exists())
retractions = [
    {"what": "sspd-05 wall-clock advantage", "was": "5.4-7.3x (v7)",
     "now": "4.03x at per-work-unit parity", "where": "WP14 / STUDIES/numpyro_comparisons_v10_v1"},
    {"what": "Real-market T=48 comparison", "was": "reported NumPyro-favourable (pre-v9 pilot, 3.6% depth caps)",
     "now": "3/3 pass at depth 10, zero caps, 3.2-3.8x ESS/s", "where": "WP14 / STUDIES/numpyro_comparisons_v10_v1"},
    {"what": "Eight Schools 19,055 bulk ESS/s 'conservative minimum'", "was": "a median over seeds",
     "now": "true v7 minimum 8,634; v9 minimum 12,830 (still 2.04x CmdStan)",
     "where": "WP8 / STUDIES/eight_schools_v9_rebench_v1/RELEASE-NOTE.md"},
    {"what": "Funnel neck mass under kernel v8", "was": "P(w<-5) = 0.097, biased 2x (a real defect)",
     "now": "v9: 0.0474 vs exact 0.0478; every v8 refinement-active result marked provisional",
     "where": "WP2/WP6 / STUDIES/funnel_bias_fix_v1"},
    {"what": "'Any diagonal metric caps at T=1000'", "was": "stated in the Polyscope ledger",
     "now": "false: identity passes at depth 8 in centered coordinates; the pathology is the prior-based metric",
     "where": "WP4/WP4B/WP12"},
]

story = {
    "generated_from": "demo/build_story_data.py",
    "state_space": state_space,
    "python_t1000": python_t1000,
    "real_target": real_target,
    "eight_schools": eight_schools,
    "strict_track": strict,
    "funnel_extra": funnel_extra,
    "provenance": {
        "preregistered_studies": len(studies),
        "study_names": studies,
        "retractions": retractions,
        "reference": "Flatiron walnutpie f5bba365",
    },
}
OUT.write_text(json.dumps(story, indent=1), encoding="utf-8")
print("wrote", OUT, OUT.stat().st_size, "bytes;", len(studies), "preregistered studies")
print({k: (round(v["ess_s"]), v["seeds"]) for k, v in python_t1000.items()})
for b in eight_schools["backends"]:
    print(round(b["ess_s"]), b["label"])
