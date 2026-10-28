"""Publication-format descriptive intervals from the pinned table source records."""
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from build_tables import records

def main():
    root=Path(__file__).resolve().parent/'figures';root.mkdir(exist_ok=True)
    data=records();colors={'ewma_t5':'#0072B2','rolling_t5':'#D55E00','always_retain':'#009E73','always_convert':'#CC79A7'}
    labels={'density':('Historical predictive density','SV − control log score (nats per origin)'),
            'tail':('Historical tail-risk scores','Control − SV pinball loss (×10⁻⁶ log-return loss)'),
            'decision':('Exploratory bounded-inventory decision','Control − SV cost (×10⁻⁶ endowed notional)')}
    plt.rcParams.update({'font.size':9,'axes.spines.top':False,'axes.spines.right':False,'pdf.fonttype':42,'svg.fonttype':'none'})
    for kind,(title,xlabel) in labels.items():
        rows=sorted((r for r in data if r['kind']==kind),key=lambda r:(r['month'],r['endpoint'],r['control']))
        fig,ax=plt.subplots(figsize=(9,max(4,1.5+.28*len(rows))))
        scale=1 if kind=='density' else 1e6
        for i,r in enumerate(rows):
            lo,hi=r['interval'];color=colors[r['control']]
            ax.plot([lo*scale,hi*scale],[i,i],color=color,lw=1.6)
            ax.plot(r['mean']*scale,i,'o',color=color,ms=4)
        ax.axvline(0,color='#555555',lw=.8,ls='--',zorder=0)
        ax.set_yticks(range(len(rows)),[f"{r['month']}  {r['endpoint']}  {r['control']}" for r in rows])
        ax.invert_yaxis();ax.set_xlabel(xlabel);ax.set_title(title,loc='left',weight='bold',pad=12)
        ax.grid(axis='x',alpha=.15);ax.set_axisbelow(True)
        fig.text(.02,.015,'Original 95% intervals, 48-origin blocks; descriptive, not simultaneous. Positive estimates favor SV.\nHistorical scope differs by study; no executable-profit claim. Full sources: TABLE-SOURCES.json.',fontsize=8)
        fig.tight_layout(rect=(0,.075,1,1))
        for ext in ('pdf','svg','png'):fig.savefig(root/f'{kind}.{ext}',dpi=180)
        svg=root/f'{kind}.svg'
        svg.write_text('\n'.join(line.rstrip() for line in svg.read_text(encoding='utf-8').splitlines())+'\n',encoding='utf-8')
        plt.close(fig)
    print('Rendered three figures with all 44 fixed comparisons')
if __name__=='__main__':main()
