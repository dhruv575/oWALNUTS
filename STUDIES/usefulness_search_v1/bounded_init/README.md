# Bounded initial-metric screen

Status: running; no verdict. Parent source checkpoint 2dbdc651. See PROTOCOL.md
for the frozen 78-cell design and gates. The candidate uses an existing
research-only InitialMetric option with bounds [0.1,1000]; no sampler source or
default changed. All three arm implementations are derived from the archived
WP94 harness by prepare_v2.py, using source.tar produced by git archive.

Build and nine targeted tests passed (six initial-metric tests, three default
fingerprints). Preflight confirms exact default/custom-noop samples and work,
and coordinatewise clipping equality on regression and zero-gradient funnel
starts. Two setup/audit mistakes were repaired before evidence without rerunning
any completed inference: prepare.py assumed identical match-arm syntax in all
three harnesses and stopped at the SV source; prepare_v2.py reads all originals
from the source archive, validates each patch, then writes. preflight.py treated
the funnel's integer chain count as the per-chain array; audit_preflight.py
correctly reads chains_data from the same completed files. Original scripts
and logs are retained. These are administrative failures, not sampler evidence.

Evidence is on the existing EC2 instance under /dev/shm/bounded-init-20261030.
Every job has a bounded supervisor and an immutable source/input manifest.
Do not rerun an observation timeout or promote an incomplete result. Final
analysis, verified archive, manuscript update and reviewed checkpoint are pending.
