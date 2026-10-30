# Operations

The continuing goal was explicitly requested on 2026-10-29. Audit01 completed
using archived ODE draws, with all original reference qualifications preserved.
The qualified public target shows a maximum 0.10396 absolute parameter-tail
probability discrepancy under Laplace. This is exploratory, not an application
validation. It motivates testing stronger cheap corrections before more MCMC.

The first 32 importance jobs saved samples but failed JSON serialization of a
NumPy Boolean introduced by the post-proposal density audit. The zero completed
rows in importance-analysis01 describe an invalid administrative attempt, not
inferential failure of either importance proposal. Preserve that source tree,
draws, errors and manifests unchanged.

The fix converts that Boolean to a Python bool. A separate `is-repaired` root
preserves the original attempt and reruns all 32 jobs with identical proposals,
budgets and seeds. A 16384-draw defensive-mixture preflight (rep98, outside the
0–7 screen replicates) completed, including value-only/gradient density checks.
Corrected code is at STUDIES/usefulness_search_v1/is_worker.py; original code is
in commit 71149fde and the remote original source tree.
