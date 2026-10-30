# Corrected exposed mechanics replay

REPLAY-AUDIT.json shows that the affected chain escaped before its final saved
draw, despite occupying the other basin for most of the original retained run.
The first replay therefore did not exercise the intended separated-basin start;
retain it as a failed input assumption, including zero accepted proposals.

Change only the input positions to each chain's FIRST retained draw, verified
in the audit. Keep all other settings, seeds, budgets and interpretation from
REPLAY-PROTOCOL.md. Original retained tuning is fixed, so these positions use
the same recorded mass and step. Save to distinct replay-v2-* directories.
This correction is exposed-data mechanics work, not a fresh validation or a
statistically independent replicate. Log-density constants differ between the
proportional Python target and full Rust target; this does not alter ratios.
