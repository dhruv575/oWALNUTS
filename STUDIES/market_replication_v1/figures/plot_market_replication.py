"""Render frozen per-month summaries, without fitting or selecting outcomes."""
import argparse
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

p = argparse.ArgumentParser()
p.add_argument('batch')
p.add_argument('output')
a = p.parse_args()
months = [('2026-04', 1440), ('2026-05', 1488), ('2026-06', 1440)]
comparisons = [('candidate_minus_rolling_t5', 'Rolling Student-t', '#2166ac'),
               ('candidate_minus_ewma_t5', 'EWMA Student-t', '#b35a00')]
fig, axes = plt.subplots(1, 2, figsize=(11, 4.8), sharey=True)
for axis, (key, title, color) in zip(axes, comparisons):
    for index, (month, count) in enumerate(months):
        s = json.loads((Path(a.batch) / month / 'summary.json').read_bytes())
        if s['month'] != month or s['planned_origins'] != count:
            raise ValueError('Fixed panel identity mismatch')
        v = s['paired'][key]
        ci = v['block_intervals']['48']
        if v['full_mean'] is None or ci is None or v['available_origins'] != count:
            raise ValueError('Every paired forecast required: ' + month)
        axis.hlines(index, ci[0], ci[1], color=color, lw=3)
        axis.scatter(v['full_mean'], index, color=color, s=45, zorder=3)
        axis.annotate(f"{v['full_mean']:+.4f} [{ci[0]:+.4f}, {ci[1]:+.4f}]",
                      (v['full_mean'], index), xytext=(0, 15),
                      textcoords='offset points', ha='center', fontsize=9)
    axis.axvline(0, color='#777777', lw=.9)
    axis.axvline(.01, color='#777777', lw=.8, ls='--')
    axis.set(title='SV minus ' + title,
             xlabel='Mean log-score difference (nats per forecast)',
             yticks=range(3), yticklabels=['April', 'May', 'June'],
             ylim=(2.45, -.65))
    axis.spines[['top', 'right']].set_visible(False)
    axis.grid(alpha=.15)
fig.suptitle('Fixed-method historical replication: all three mandatory months')
fig.text(.5, .025, 'Descriptive 95% intervals: 10,000 circular bootstrap resamples, 48-origin blocks.\n'
         'Adjacent months are dependent; no pooled significance claim. Dashed line: 0.01-nat reference.\n'
         'Predictive scores are not trading returns or profitability.', ha='center', fontsize=9, color='#444444')
fig.tight_layout(rect=(0, .14, 1, .95))
out = Path(a.output)
out.parent.mkdir(parents=True, exist_ok=True)
fig.savefig(out, dpi=180)
fig.savefig(out.with_suffix('.svg'))
plt.close(fig)
