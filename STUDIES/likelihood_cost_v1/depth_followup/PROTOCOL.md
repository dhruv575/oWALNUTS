# Selected follow-up: depth limit 11, specified after the primary screen

The original 80-fit study is unchanged and retained. At n2048, full WALNUTS
passes 6/8 seeds versus diagonal NUTS 8/8 and low-rank NUTS 5/8. Every failure
is solely one or two retained depth-ten hits; all exact accuracy, MCSE, R-hat,
ESS and divergence checks pass. WALNUTS's two failures each have one depth hit.
The original mechanism rule therefore fails despite promising timings.

Increase the maximum trajectory depth from ten to eleven for ALL three full
likelihood arms. Keep target, data, settings, initial states, four chains,
750 warmup, 6,000 retained draws, exact gates and resource bounds unchanged.
This gives capped trajectories more room; it does not relabel depth hits as
passes. Eight fresh seeds per arm at n2048 only: 24 fits. No rerunning only
failed seeds and no further budget/depth escalation in this follow-up.

Use worker seed base815000000 (plus existing case/config/rep offsets), shuffle
825000000 and bootstrap835000000. Tests reuse independent test fixtures. Both
engines count retained hits at eleven. All files are frozen in source-depth11.
Judge by the same >=7/8 WALNUTS qualification, no fewer than either full NUTS,
>=1.5 median kernel speed ratio against both and lower bootstrap bounds >1.
Report all fits and primary-depth-ten results. Optimized controls remain those
from the original screen; do not present this as an advantage over them.
This is a post-screen fresh-seed follow-up, not independent confirmation of
a previously successful primary claim.
