# Persistent confirmation controller

`controller.py` runs on the Windows workstation using the existing `owalnuts`
AWS login. `controller_remote.py` is installed outside the frozen scientific
source tree at `/home/ubuntu/.cache/owalnuts-transfer/controller_remote.py`.
No model, seeds, diagnostic thresholds, batch limits or endpoints change.

The local process coordinates all 255 fixed batches. Each batch must finish,
drain its processes, preserve its source hashes, upload its full archive, and
pass a streamed SHA256 check of the exact S3 object version before reclamation.
The next launch still passes the original supervisor's runtime, source, disk,
previous-archive and resource admission checks. Failed scientific slots stay
in the denominator. Forecast scores are never used to choose the next action.

The controller also copies compact evidence locally and verifies its manifest.
Verbose `SAMPLER.json` records are removed from EC2 only after their bytes match
the manifest bound to a verified S3 archive. Their archived copies remain intact.
Other compact reports, diagnostics, manifests and failure records stay on EC2.

The Windows file lock prevents duplicate local controllers. Remote operations
use a nonblocking Linux lock and refuse mutations while a supervisor is live.
Research supervisors detach from SSH, so losing a connection does not restart
or kill an experiment. An existing incomplete batch is never automatically
rerun. Interrupted packing, cleanup, or local evidence imports require review.

## Operation

Launch `target/aws-transfer-runtime/Scripts/python.exe` with
`STUDIES/bounded_confirmation_v1/controller.py`, working directory the repository
root, as a hidden background process with stdout/stderr redirected to files.
Read `target/confirmation-controller/status.json` and `events.jsonl`, and confirm
the recorded PID is live. An event file alone is not evidence of a live process.

Create `target/confirmation-controller/STOP` to prevent another controller
operation; this does not interrupt a detached bounded experiment already running.
Remove that sentinel before an explicitly authorized restart. Restarting the
controller resumes from receipts; it does not replace existing scientific jobs.

This implementation survives chat turns but depends on this workstation staying
awake and connected. AWS login refresh works only within its authorization
window; renewal can still require user approval. On an error the controller
records `blocked` and exits rather than bypassing a gate. It does not implement
phone notifications or claim completion of the broader research goal. Monitor
credentials, its live process, and evidence periodically. It ends after all
255 archives and compact local reviews are preserved, without unsealing scores.
