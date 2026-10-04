# Saved-data resource probes

Both probes use the two existing reference pilot compact outputs. They generate
no new posterior draws and provide no bootstrap accuracy or coverage evidence.
Both actual reference outputs passed diagnostic compact-adapter admission.
The pilot exclusion rule still prevents using these outputs in the future bank.

Five common CDF queries at quadrature order 128 cost approximately 1.16–1.19
seconds for each 4k prefix and 2.32–2.39 seconds for each 8k fit. A conditional
linear extrapolation to 64 fits and the full 16/32/64/128 ladder gives roughly
24–97 minutes for 16–64 common queries, excluding fitting and the rest of the
analysis. Neither fit-count nor order scaling was measured at bank size. Five
queries are insufficient to establish an admissible inversion grid.

Both timing runs may overlap short correctness tests. Preserve both as
descriptive shared-machine measurements; neither is an isolated benchmark.
Their similar cost scale motivates a prospective grid adequacy and resource
check with margin, not a precise performance claim or another timing repeat.

The parameter probe used 2,048 shared bootstrap multiplicity vectors over only
two fits: about .35 seconds plus .17 seconds of cache setup. That small system
does not establish 64-fit bootstrap cost or uncertainty validity. Mixed-family
parameter batching was unsupported when these probes were written; the later
integrated routing change has 19 passing tests and preserves scalar outputs.

Original probe JSON binds its compact inputs. Scripts are archived for method
inspection and may require restoring their original workspace-relative paths.
The next step is deterministic common-grid refinement with explicit estimated
numerical error, unresolved outcomes at its cap, and actual saved-data checks.
