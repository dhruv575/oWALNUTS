# Target-only mixed T1000 profile

Exploratory posthoc diagnosis, not a sampler benchmark or qualification. Uses archived pair00-public fixture, starts for chains0/3 and canonical retained positions (chain0,draw0),(chain1,draw999),(chain3,draw1999). No RNG, new seeds, MCMC or target modifications.

The profile invokes the current public compile_target(data,flow,32,mixed_slopes), captures optimized PyTensor graph inventory, and measures five blocks of1500 target calls (7500total) plus matching ctypes no-op and zero-gradient controls. Pointers and ABI objects are created outside timed loops. Control costs are disclosed separately; subtracting them cannot isolate Rust trajectory overhead exactly. Stored normalized value/gradient checks run in a separate process against both JAX direct mixed density and canonical density+Jacobian.

Each process has CPU0, a600-second contained timeout, and8GiB process memory cap before numerical imports. launch.py uses existing assign-before-resume hardware_control with no unsafe outer timeout. Existing compiler caches remain. All sources/runtime/raw input hashes are in config.json; any drift fails closed. Outputs are exclusive, attempts retained. No source edits or retries under same output names.

Command: `C:/dev/owalnuts/target/python-workflow-env/Scripts/python.exe C:/dev/owalnuts/target/mixed-target-profile-v1/launch.py`. Exact per-phase commands are persisted in profile-started.json and parity-started.json before execution.
