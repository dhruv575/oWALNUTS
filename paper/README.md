# Research manuscript artifacts

This is an evolving research manuscript, not yet submission-ready. Start with
[the research plan and claim matrix](RESEARCH-PAPER.md) and the
[implemented methods](METHODS.md).

## Reproduce the completed-study results

From the repository root, using Python and Matplotlib:

```powershell
python paper/build_tables.py
python -m unittest discover -s paper -p 'test_*.py'
python paper/plot_results.py
```

`TABLE-SOURCES.json` pins each input summary by SHA-256. The renderer rejects
changed inputs and incomplete comparison denominators. It transcribes the
original means and intervals; it does not rerun inference or bootstrap analysis.
The tests check the 44-comparison denominator and preservation of selected
negative or inconclusive findings. They do not independently validate the
original statistical analyses.

Outputs are [numerical tables](RESULTS-TABLES.md), machine-readable
`table-data.json`, and PDF, SVG and PNG versions of three figures in `figures/`.
The figures retain every comparison in their corresponding table. Rendering
was checked with Python's installed Matplotlib 3.11.1; vector-file metadata may
differ between rendering dates. Hash-pinned numerical input is authoritative.

## Current empirical interpretation

Across the four density panels, SV's mean log-score advantage over rolling t5
ranges from 0.051015 to 0.134925 nats per origin. Each displayed original
48-origin-block interval is positive. Advantages over EWMA t5 are smaller,
0.013710 to 0.023670; the June interval includes zero. These comparisons concern
the combined forecasting systems and do not identify an advantage of the
oWALNUTS sampler over another sampler for the same model.

Tail-loss evidence differs across evaluation stages. The retrospective
April-June panels do not resolve an advantage over EWMA on either side using
these intervals. In the December-February historical/project-access holdouts,
five of six EWMA comparisons have positive intervals; February's short-side
estimate is slightly negative and unresolved. Two original reference failures
remain part of the evidence. These are descriptive per-comparison intervals,
not a multiplicity-adjusted overall success test.

The fixed-cost bounded-inventory experiment does not establish a useful
decision advantage over EWMA. Always-retain is a poor control for this
downside-only objective, and gains over it do not establish trading value.
Always-convert and rolling t5 have identical costs on these panels; June's SV
decisions also match their cost exactly. This experiment resets the endowment
at each origin, excludes upside and is not a self-financing portfolio return.

Reference precision, repeated warm-path fidelity, matched-model algorithm
comparisons, a feasible economic experiment and defensible originality remain
separate research requirements before the intended paper can be finalized.
