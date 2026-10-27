"""Plot frozen retrospective tail-loss intervals; no scoring or resampling."""
import argparse
import json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

p = argparse.ArgumentParser()
p.add_argument('batch', type=Path)
p.add_argument('output', type=Path)
a = p.parse_args()
months = [('2026-04', 1440), ('2026-05', 1488), ('2026-06', 1440)]
fig, axes = plt.subplots(1, 2, figsize=(11, 4.8), sharey=True)
for ax, baseline, title in zip(axes, ['rolling_t5', 'ewma_t5'],
                              ['Rolling Student-t', 'EWMA Student-t']):
    for i, (month, n) in enumerate(months):
        s = json.loads((a.batch / 'reports' / month / 'summary.json').read_bytes())
        if s['month'] != month or s['planned_origins'] != n or not s['full_scientific_panel']:
            raise ValueError('Complete fixed month required')
        for side, dy, color in [('long', -.13, '#2166ac'), ('short', .13, '#b35a00')]:
            v = s['comparisons'][baseline + '_' + side]
            ci = v['loss_block_intervals']['48']
            if v['available'] != n or ci is None or v['mean_advantage'] is None:
                raise ValueError('Complete comparison required')
            ax.hlines(i + dy, ci[0] * 1e6, ci[1] * 1e6, color=color, lw=2.5)
            ax.scatter(v['mean_advantage'] * 1e6, i + dy, color=color, s=35,
                       label=side.capitalize() + ' exposure' if i == 0 else None, zorder=3)
    ax.axvline(0, color='#666666', lw=.9)
    ax.set(title='Baseline: ' + title, yticks=range(3), yticklabels=['April', 'May', 'June'],
           ylim=(2.5, -.6), xlabel='Mean baseline minus SV pinball loss\n(10^-6 log-return units; positive favors SV)')
    ax.spines[['top', 'right']].set_visible(False)
    ax.grid(alpha=.15)
handles, labels = axes[0].get_legend_handles_labels()
fig.legend(handles, labels, frameon=False, ncol=2, loc='upper center', bbox_to_anchor=(.5, .92))
fig.suptitle('Retrospective 95% risk-limit comparison using stored E64 draws')
fig.text(.5, .025, 'Descriptive 95% intervals: 10,000 paired circular bootstrap resamples, 48-origin blocks.\n'
         'All 12 comparisons shown. Previously inspected historical data; no fresh confirmation or dollar-profit claim.',
         ha='center', fontsize=9, color='#444444')
fig.tight_layout(rect=(0, .115, 1, .86))
a.output.parent.mkdir(parents=True, exist_ok=True)
fig.savefig(a.output, dpi=180)
fig.savefig(a.output.with_suffix('.svg'))
plt.close(fig)
