#!/usr/bin/env python3
"""Post-hoc DESCRIPTIVE localisation (not part of the frozen verdict): which
fields of the chain-2 proposal stream differ between the owned (A) and
unserialised (B) replays, and a compact chain-2 trace for transitions 0..9."""
import collections
import json
from pathlib import Path

ART = Path(__file__).resolve().parent / "artifacts"
load = lambda name: json.loads((ART / "raw" / f"{name}.json").read_text(encoding="utf-8"))
a, b = load("A_owned_abort-1"), load("B_unserialised_abort-1")
diff, by_outcome = collections.Counter(), collections.Counter()
for x, y in zip(a["trace_proposals"], b["trace_proposals"]):
    for key in x:
        if x[key] != y[key]:
            diff[key] += 1
            by_outcome[f"{key}|{x['outcome']}"] += 1
example = next(((x["gradient"], y["gradient"], x["outcome"]) for x, y in
                zip(a["trace_proposals"], b["trace_proposals"]) if x["gradient"] != y["gradient"]), None)
proposals = collections.defaultdict(list)
for p in a["trace_proposals"]:
    proposals[p["transition"]].append(p)
trace = []
for t in a["trace_transitions"]:
    ad = t["adaptation"] or {}
    trace.append({"transition": t["transition"], "selected_log_density": t["selected_log_density"],
                  "selected_theta": t["selected_theta"], "selected_rho": t["selected_rho"],
                  "active_step_before": ad.get("active_step_before"),
                  "active_step_after": ad.get("active_step_after"), "stage": ad.get("stage")})
per_transition = [{"transition": tr, "proposals": len(lst),
                   "outcomes": dict(collections.Counter(p["outcome"] for p in lst))}
                  for tr, lst in sorted(proposals.items())]
streams = {}
for arm in ("A_owned_abort", "B_unserialised_abort"):
    for rep in (1, 2, 3):
        r = load(f"{arm}-{rep}")
        streams[f"{arm}-{rep}"] = [(s["chain"], s["observations"], s["hash_fnv1a64"]) for s in r["chain_streams"]]
out = {
    "label": "post-hoc descriptive; the frozen verdict is in summary.json",
    "chain2_trace_proposals_compared": len(a["trace_proposals"]),
    "fields_differing_A1_vs_B1": dict(diff), "differences_by_field_and_outcome": dict(by_outcome),
    "example_differing_gradient_owned_vs_unserialised": example,
    "chain2_completed_transitions_equal_A1_vs_B1": a["trace_transitions"] == b["trace_transitions"],
    "chain2_first_kernel_nonfinite_equal_A1_vs_B1":
        a["chain_streams"][2]["first_kernel_nonfinite"] == b["chain_streams"][2]["first_kernel_nonfinite"],
    "chain2_first_kernel_nonfinite": a["chain_streams"][2]["first_kernel_nonfinite"],
    "chain2_start": a["starts"][2],
    "chain2_transitions_0_8": trace, "chain2_proposals_per_transition_0_9": per_transition,
    "per_chain_streams_all_gating_replays": streams,
}
(ART / "descriptive-localisation.json").write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
print(json.dumps({k: out[k] for k in ("fields_differing_A1_vs_B1", "differences_by_field_and_outcome",
                                      "chain2_completed_transitions_equal_A1_vs_B1",
                                      "chain2_first_kernel_nonfinite_equal_A1_vs_B1")}, indent=1))
