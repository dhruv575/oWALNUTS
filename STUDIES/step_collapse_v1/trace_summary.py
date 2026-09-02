"""Print a per-window warmup summary of one study cell: python trace_summary.py <cell.json> [chain]"""
import json
import sys

import numpy as np


def summarize(path, only=None):
    d = json.load(open(path, encoding="utf-8"))
    sched = d["schedule"]
    W = d["warmup"]
    bounds = [(0, sched["initial_fast_end"], "init")] + [(a, b, f"w{i}") for i, (a, b) in enumerate(sched["windows"])] + [(sched["terminal_fast_start"], W, "term")]
    print(f"{d['model']} {d['variant']} seed {d['seed']}  min bulk ESS {d['min_bulk_ess']:.0f} rhat {d['max_rhat']:.3f} grads {d['gradients_total']} ESS/grad*1e3 {1e3*d['min_bulk_ess_per_gradient']:.3f}")
    for c, ch in enumerate(d["chains_data"]):
        if only is not None and c != only:
            continue
        t = ch["trace"]
        h = np.array(t["step_size"]); acc = np.array([np.nan if a is None else a for a in t["acceptance_statistic"]])
        depth = np.array(t["depth"]); stop = np.array(t["stop"]); lvl = np.array([-1 if l is None else l for l in t["selected_level"]])
        err = np.array(t["max_abs_energy_error"]); leaves = np.array(t["leaves_built"]); moved = np.array(t["moved"])
        st = d["starts"][c]
        print(f" chain {c}: start lp {st['log_density']:.3g} |grad| {st['gradient_norm']:.3g}  final h {ch['final_step_size']:.4g}  retained caps {ch['retained_depth_caps']} mean depth {ch['retained_mean_depth']:.2f} refined {ch['retained_refined_fraction']:.3f} exh {ch['retained_exhaustions']} div {ch['retained_divergences']}")
        for a, b, name in bounds:
            s = slice(a, b)
            if b <= a:
                continue
            stops = {k: int((stop[s] == k).sum()) for k in ["max_depth", "exhausted", "outer_uturn", "recursive_uturn", "reverse_coarser", "invalid"]}
            stops = {k: v for k, v in stops.items() if v}
            lv = lvl[s]
            lvd = {int(k): int((lv == k).sum()) for k in np.unique(lv)}
            print(f"   {name:5s} [{a:4d},{b:4d}) h {h[a]:.3g}->{h[b-1]:.3g} acc mean {np.nanmean(acc[s]):.3f} med {np.nanmedian(acc[s]):.3f} depth {depth[s].mean():.1f} leaves {leaves[s].mean():.0f} maxerr med {np.median(err[s]):.3g} moved {moved[s].mean():.2f} lvl {lvd} stops {stops}")
        for u in ch["metric_updates"]:
            md = u["mass_diagonal"]
            print(f"   update w{u['window_index']} @{u['transition']}: h {u['step_before']:.3g} -> search {u['step_after_search']} restart {u['step_after_restart']}; mass diag min {min(md):.3g} max {max(md):.3g} n {u['sample_count']}")
        for e in ch["step_searches"]:
            print(f"   search {e['reason']}: {e['initial_step']:.3g} -> {e['selected_step']:.3g} ({e['target_calls']} calls)")
        print(f"   final mass diag: {np.array2string(np.array(ch['final_mass_diagonal']), precision=3, max_line_width=200)}")
        s = slice(W, None)
        print(f"   retained: acc mean {np.nanmean(acc[s]):.3f} depth {depth[s].mean():.2f} leaves {leaves[s].mean():.0f} moved {moved[s].mean():.2f}")


if __name__ == "__main__":
    summarize(sys.argv[1], int(sys.argv[2]) if len(sys.argv) > 2 else None)
