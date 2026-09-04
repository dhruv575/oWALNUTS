# chain_rescue_v2 — WP36

Status: **preregistered; core candidate implemented; harness not implemented;
not run**.

`PREREGISTRATION.md` and `protocol.json` freeze the decision study before
candidate implementation or evidence. The baseline is `17f1d97`. The study
will compare `observe`, explicit immediate `current`, and `two_hit` on seven
fixed posteriordb models plus the 10-D funnel, using the 12 fresh paired
seeds 92101–92112.

The core opt-in APIs are `ChainRescueConfig::observe_only()` and
`ChainRescueConfig::two_hit()`. The production default remains immediate
`restart_from_best`. Observe-only synchronizes chains and retains each
window's log densities plus one pre-action position per boundary; restart
policies additionally retain source-window positions until that boundary.
No full source window is copied into telemetry.

There is still no study harness, study Cargo manifest, or evidence artifact,
and none of the registered evidence seeds has been run.
