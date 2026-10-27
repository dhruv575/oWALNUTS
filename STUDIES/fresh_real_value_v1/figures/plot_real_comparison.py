"""Plot only frozen full-panel summaries; no fitting, resampling, or data selection."""
import argparse, json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

p = argparse.ArgumentParser()
p.add_argument('summary')
p.add_argument('output')
a = p.parse_args()
s = json.loads(Path(a.summary).read_bytes())
comparisons = [('candidate_minus_rolling_t5', 'Rolling Student-t', '#2166ac'),
               ('candidate_minus_ewma_t5', 'EWMA Student-t', '#b35a00')]
fig, axes = plt.subplots(2, 1, figsize=(9, 7), gridspec_kw={'height_ratios': [2, 1]})
for index, (key, label, color) in enumerate(comparisons):
    v = s['paired'][key]
    if v['full_mean'] is None or v['cumulative'] is None:
        raise ValueError('Full-panel figure requires every paired forecast: ' + key)
    axes[0].plot(np.arange(1489)/48 + 1, [0.] + v['cumulative'], color=color, label=label, lw=1.6)
    interval = v['block_intervals']['48']
    if interval is None:
        raise ValueError('Frozen primary block interval missing')
    axes[1].hlines(index, interval[0], interval[1], color=color, lw=3)
    axes[1].scatter(v['full_mean'], index, color=color, s=45, zorder=3)
    axes[1].text(interval[0], index + .15,
                 f" {v['full_mean']:+.4f} [{interval[0]:+.4f}, {interval[1]:+.4f}]", fontsize=9)
axes[0].axhline(0, color='#777777', lw=.8)
axes[0].set(xlim=(1,32), xlabel='Forecast target time (UTC)',
            ylabel='Cumulative SV minus baseline log score (nats)',
            title='August historical comparison: all 1,488 origins')
axes[0].set_xticks([1,8,15,22,29,32], ['Aug 1','Aug 8','Aug 15','Aug 22','Aug 29','Sep 1'])
axes[0].legend(frameon=False)
axes[1].axvline(0, color='#777777', lw=.8)
axes[1].axvline(.01, color='#777777', lw=.8, ls='--', label='Predeclared 0.01-nat reference')
axes[1].set(yticks=[0,1], yticklabels=[x[1] for x in comparisons], ylim=(-.4,1.5),
            xlabel='Mean SV minus baseline log score (nats per forecast)')
axes[1].legend(frameon=False, fontsize=8, loc='lower right')
for ax in axes:
    ax.spines[['top','right']].set_visible(False)
    ax.grid(alpha=.16)
fig.text(.5,.012,'Intervals: frozen 10,000-resample circular block bootstrap, 48 half-hour origins per block.\nHistorical predictive evidence; not trading returns or profitability.',ha='center',fontsize=9,color='#444444')
fig.tight_layout(rect=(0,.065,1,1))
out = Path(a.output)
out.parent.mkdir(parents=True, exist_ok=True)
fig.savefig(out, dpi=180)
fig.savefig(out.with_suffix('.svg'))
plt.close(fig)
