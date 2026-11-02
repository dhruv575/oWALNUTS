# Post-hoc parameterization control

Added after seeing the completed base case and partial mixed10 results, before
inspecting mixed100 results. The concentration stress specifically strengthens
some groups, so a practical comparison should allow centering those groups.
Otherwise the stress test could reward a sampler for a removable modeling issue.

On all three frozen cases, use the existing hybrid transform (center n>=1000,
noncenter other groups), conservative NUTS .999 and rebuilt WAL .9. Same four
confirmation seeds per case, four chains, 1000 warmup, 8000 retained draws,
depth11, references and gates. This is a 24-fit exploratory control, not fresh
replication or a replacement for the frozen noncentered campaign. Retain every
failure; no winner selection or parameter retuning. Serial execution begins
after the main campaign finishes. Same resource limits; dedicated RAM lane.
