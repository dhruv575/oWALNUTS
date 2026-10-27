# Local parent supervision

The parent-owned supervisor runs the frozen evaluator in its pinned Python
environment with BLAS/OpenMP thread counts set to one. It tracks the Windows
virtualenv launcher and its actual Python descendant by PID and creation time.
Every 0.25 seconds it measures their combined RSS and output bytes. Exceeding
2 GiB RSS or 50 MiB output terminates owned processes; these are sampled limits,
not instantaneous operating-system allocation reservations.

Imports/setup have a separate 60-second allowance. The evaluator's internal
monotonic processing deadline remains 120 seconds for preflight or the frozen
formula for the full stage. The external monitor permits one second of deadline
scheduling grace and imposes an independent monotonic whole-process ceiling of
phase budget plus 60 seconds. Teardown allows at most three seconds followed by
two seconds after kill. It never restarts a stage.

Supervisor records live alongside the output directory, allowing preflight to
create a genuinely new directory. The terminal evaluator state, partial origin
files and full planned-row summary establish evidence completeness; process
exit alone does not establish valid predictions. Report sampled peak RSS as such.
