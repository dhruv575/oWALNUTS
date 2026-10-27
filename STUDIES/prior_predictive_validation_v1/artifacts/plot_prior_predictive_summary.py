"""Render only statistics already present in the frozen campaign summary."""
import argparse,json
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

def render(source,destination):
    summary=json.loads(Path(source).read_text())
    arms=[("candidate","Resident K400","#235789"),("baseline","NIG lag baseline","#9b5a19"),("oracle","Privileged oracle","#277a63")]
    fig,axes=plt.subplots(1,3,figsize=(12,4.3),sharey=True)
    limits=[0.05]
    for ax,(name,label,color) in zip(axes,arms):
        result=summary["arms"][name];ecdf=result["pit_ecdf"]
        count=result["pit_mean"]["available_origins"]
        ax.set_title(label,fontsize=12,fontweight="bold")
        ax.axhline(0,color="#555555",lw=1,ls="--")
        if ecdf is not None:
            grid=np.asarray(ecdf["grid"]);estimate=np.asarray(ecdf["estimate"])
            lower=np.asarray(ecdf["lower"])-grid;upper=np.asarray(ecdf["upper"])-grid
            ax.fill_between(grid,lower,upper,color=color,alpha=.18)
            ax.plot(grid,estimate-grid,color=color,lw=2,marker="o",ms=3)
            limits.extend([abs(lower).max(),abs(upper).max()])
        else:
            ax.text(.5,.5,"Full-panel envelope unavailable",ha="center",va="center",transform=ax.transAxes)
        ax.text(.5,.02,f"{count:,} / 1,024 forecasts available",ha="center",transform=ax.transAxes,fontsize=9,color="#555555")
        ax.set_xlim(.05,.95);ax.set_xlabel("PIT threshold")
        ax.grid(axis="y",alpha=.15);ax.spines[["top","right"]].set_visible(False)
    bound=max(limits)*1.12
    for ax in axes:ax.set_ylim(-bound,bound)
    axes[0].set_ylabel("Empirical PIT CDF minus uniform CDF")
    fig.suptitle("Prior-predictive calibration: 32 independent streams",fontsize=15,fontweight="bold")
    fig.text(.5,.025,"Shading: frozen descriptive 95% whole-stream bootstrap envelope. Matched-model check; not market validation.",ha="center",fontsize=9,color="#555555")
    fig.tight_layout(rect=(0,.07,1,.91))
    destination=Path(destination);destination.parent.mkdir(parents=True,exist_ok=True)
    fig.savefig(destination,dpi=180,bbox_inches="tight");plt.close(fig)
if __name__=="__main__":
    parser=argparse.ArgumentParser();parser.add_argument("summary");parser.add_argument("output");args=parser.parse_args();render(args.summary,args.output)
