"""Frozen health, mechanism, and advancement rules for diagnostic v3."""
import argparse, json, math, os, tempfile
from pathlib import Path
import arviz as az
import numpy as np

SEEDS=[2026092101,2026092102,2026092103]
EXPECTED=[(s,c,m) for s in SEEDS for c in (1,10) for m in ("adaptive_diagonal","fixed_identity")]

def atomic_create(path,value):
    if path.exists(): raise FileExistsError(path)
    path.parent.mkdir(parents=True,exist_ok=True)
    fd,tmp=tempfile.mkstemp(prefix=path.name,suffix=".pending",dir=path.parent)
    try:
        with os.fdopen(fd,"w") as f: json.dump(value,f,indent=2); f.flush(); os.fsync(f.fileno())
        os.link(tmp,path)
    finally: Path(tmp).unlink(missing_ok=True)

def diagnostics(samples):
    return [{"coordinate":i,"rank_rhat":float(az.rhat(samples[:,:,i],method="rank")),
             "bulk_ess":float(az.ess(samples[:,:,i],method="bulk")),
             "tail_ess":float(az.ess(samples[:,:,i],method="tail",prob=(.05,.95))),
             "mean":float(samples[:,:,i].mean()),"variance":float(samples[:,:,i].var())}
            for i in range(10)]

def dispersion(steps): return math.log(max(steps))-math.log(min(steps))

def analyze(directory):
    paths=sorted(directory.glob("cell-??.json"))
    if len(paths)!=12: raise RuntimeError("exactly 12 complete cells required")
    cells=[]
    for index,(path,expected) in enumerate(zip(paths,EXPECTED)):
        raw=json.loads(path.read_text())
        actual=(raw.get("seed"),raw.get("restart_center_multiplier"),raw.get("metric_policy"))
        if raw.get("cell_index")!=index or actual!=expected or raw.get("callback_cap")!=1_000_000_000 or raw.get("wall_cap_seconds")!=300:
            raise RuntimeError(f"cell {index} violates protocol")
        samples=np.asarray(raw.pop("samples"),dtype=np.float64)
        if samples.shape!=(4,10000,10): raise RuntimeError(f"cell {index} sample shape")
        diag=diagnostics(samples); scale=diag[0]
        keys=("target_calls","divergences","invalid_stops","refinement_exhaustions",
              "maximum_depth_stops","recoverable_target_failures","reverse_coarser_stops",
              "reverse_coarser_rejections")
        totals={k:sum(chain[k] for chain in raw["chains"]) for k in keys}
        steps=[chain["qualified_step_size"] for chain in raw["chains"]]
        gates={"zero_divergences":totals["divergences"]==0,"zero_invalid":totals["invalid_stops"]==0,
          "zero_refinement_exhaustion":totals["refinement_exhaustions"]==0,
          "zero_recoverable":totals["recoverable_target_failures"]==0,
          "maximum_depth_rate":totals["maximum_depth_stops"]/40000<=.01,
          "rank_rhat":max(d["rank_rhat"] for d in diag)<=1.05,
          "scale_bulk_ess":scale["bulk_ess"]>=80,"scale_tail_ess":scale["tail_ess"]>=80,
          "scale_mean":abs(scale["mean"])<=1,"scale_variance":6<=scale["variance"]<=13.5,
          "step_dispersion":max(steps)/min(steps)<=4,
          "projected_bulk":5*scale["bulk_ess"]>=400,"projected_tail":5*scale["tail_ess"]>=400}
        current=[]; trajectory=[]; missing=0; observations=0; total_move=0.; boundary_move=0.
        for chain in raw["chains"]:
            boundaries={u["transition"] for u in chain["metric_updates"]}
            for point in chain["checkpoints"]:
                observations+=1
                if point["current"]["mean"] is None or point["trajectory"]["mean"] is None: missing+=1
                else: current.append(point["current"]["mean"]); trajectory.append(point["trajectory"]["mean"])
                move=abs(math.log(point["step_after"]/point["step_before"])); total_move+=move
                if point["transition"] in boundaries: boundary_move+=move
        corr=float(np.corrcoef(current,trajectory)[0,1]) if len(current)>1 else None
        masses=[math.exp(np.mean(np.log(c["mass_diagonal"]))) for c in raw["chains"]]
        metric_corr=float(np.corrcoef(np.log(steps),np.log(masses))[0,1]) if np.std(np.log(masses)) else None
        raw.update({"coordinate_diagnostics":diag,"health_totals":totals,"steps":steps,
          "log_step_dispersion":dispersion(steps),"scale_bulk_ess_per_target_call":scale["bulk_ess"]/totals["target_calls"],
          "gates":gates,"eligible":all(gates.values()),"acceptance_correlation":corr,
          "acceptance_missing_rate":missing/observations,"boundary_step_movement_fraction":boundary_move/total_move if total_move else 0,
          "step_mass_correlation":metric_corr})
        cells.append(raw)
    get={(c["seed"],c["restart_center_multiplier"],c["metric_policy"]):c for c in cells}
    ratios=[]; dispersion_reductions=[]
    for seed in SEEDS:
        one=get[(seed,1,"adaptive_diagonal")]; ten=get[(seed,10,"adaptive_diagonal")]
        ratios.append(ten["scale_bulk_ess_per_target_call"]/one["scale_bulk_ess_per_target_call"])
        dispersion_reductions.append(one["log_step_dispersion"]-ten["log_step_dispersion"])
    center10=[get[(s,10,"adaptive_diagonal")] for s in SEEDS]
    restart_supported=(float(np.median(dispersion_reductions))>=math.log(2)
      and all(max(c["steps"])/min(c["steps"])<=4 for c in center10)
      and float(np.median(ratios))>=1.25 and min(ratios)>=.8)
    window_supported=all(get[(s,c,"adaptive_diagonal")]["boundary_step_movement_fraction"]>=.5
      and get[(s,c,"fixed_identity")]["boundary_step_movement_fraction"]<.5 for s in SEEDS for c in (1,10))
    acceptance_supported=any(c["acceptance_correlation"] is None or c["acceptance_correlation"]<.5 or c["acceptance_missing_rate"]>=.2 for c in cells)
    metric_seeds=0
    for s in SEEDS:
        a=get[(s,10,"adaptive_diagonal")]; f=get[(s,10,"fixed_identity")]
        if a["log_step_dispersion"]-f["log_step_dispersion"]>=math.log(2) and a["step_mass_correlation"] is not None and abs(a["step_mass_correlation"])>=.7: metric_seeds+=1
    metric_supported=metric_seeds>=2
    selected=all(c["eligible"] for c in center10) and restart_supported
    return {"schema":"neal-funnel-dual-averaging-diagnostic-v3-summary","cells":cells,
      "mechanisms":{"restart_centering_supported":restart_supported,"window_instability_supported":window_supported,
      "acceptance_noise_supported":acceptance_supported,"metric_coupling_supported":metric_supported,
      "center10_ess_call_ratios":ratios,"dispersion_reductions":dispersion_reductions,"metric_supporting_seeds":metric_seeds},
      "advancement":{"selected":selected,"decision":"advance center10 to confirmation" if selected else "no selection"}}

if __name__=="__main__":
    p=argparse.ArgumentParser(); p.add_argument("--input",type=Path,required=True); p.add_argument("--output",type=Path,required=True)
    a=p.parse_args(); atomic_create(a.output,analyze(a.input))
