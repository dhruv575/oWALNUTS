# Administrative repair, before scientific analysis

All 36 initial jobs completed, but the analysis assertion found auto3 recorded
window 2. The preparation script globally replaced SELECT_WINDOW after inserting
the environment-variable name, turning STUDY_SELECT_WINDOW into
STUDY_select_window(). Missing that key silently selected the fallback 2.
Thus initial auto3 is not the candidate. Preserve all original runs and source
hashes; do not interpret them as evidence about later selection.

Repair replaces the identifier before inserting the function body. Verify a
reserved-seed preflight records window 3 before running any repaired study.
The repaired comparison uses fresh seeds 926200001--926200003 and shuffle seed
926299999, same targets, budgets, thresholds and gates. No failed cell is rerun
as if it were an original valid comparison. Original run01 remains immutable;
repaired binaries/source and run02 are separate. Preflight seed 926299998 is
excluded from scientific results. Validate selected window in every result.
