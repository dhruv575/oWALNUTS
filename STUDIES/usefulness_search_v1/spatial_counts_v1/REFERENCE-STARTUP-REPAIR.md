# Administrative startup repair, 2026-10-31

Original groups 1,2,3 exited before sampler entry because ArviZ 0.23.4 used
the same ~/.cache/arviz/daily_warning.tmp in concurrent imports. Worker logs
show FileNotFoundError in its rename. Group 0 reached sampling and continues
unchanged in the original directory. No inferential outcome prompted repair.

Preserve all original results. In a distinct -v2 directory, run only groups
1,2,3 with unchanged settings, unused seeds and resource limits. Each sets
XDG_CACHE_HOME to its own output/cache BEFORE importing ArviZ. No package
upgrade or model change. The exact code change and both source bundles remain.
This explicitly reviewed administrative repair is the sole exception to the
no-retry rule; no inference timeout or accuracy failure will be rerun here.

After repaired workers finish, wait only until original launch +2440 seconds
for group 0 supervision. GROUP-SOURCES.json records the four distinct source
directories; combined summary reads original group 0 without copying/deleting
its evidence. Missing/failed groups fail the reference gate. Record original
startup failures separately from scientific results. No favorable partial
result changes settings, diagnostics or comparison claims.
