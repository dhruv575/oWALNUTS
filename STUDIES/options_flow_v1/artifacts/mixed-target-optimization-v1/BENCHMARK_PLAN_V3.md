# Matched target benchmark version 3

Supersedes the unexecuted version2 preparation only. All original source and configuration files remain unchanged. Statistical/target/timing scope is identical to BENCHMARK_PLAN.md.

Worker hashes the exact configuration bytes used at admission, checks that identity again before success, and records the admitted hash. Launcher checks the same configuration identity before each contained process and after each terminal process; drift stops later admissions and returns failure. The launcher uses task_dir, not a generic HOME variable.

No benchmark has run. Command after root GO:

`C:/dev/owalnuts/target/python-workflow-env/Scripts/python.exe target/mixed-target-optimization-v1/launch_benchmark_v3.py --config target/mixed-target-optimization-v1/benchmark-config-v3.json --out target/mixed-target-optimization-v1/benchmark-run-v3`
