# Instance-local confirmation operations

The workstation controller was stopped at a safe boundary before batch 031.
Its STOP sentinel remains in place. The replacement `cloud_controller.py` runs
on the existing EC2 instance using the same frozen supervisor, workers, batches,
seeds, CPU affinity, memory/disk limits and archive admission functions. It uses
two-second process polling and performs archive handoffs directly on EC2,
eliminating workstation SSH round trips and local credential renewal from the
critical path. No scientific source or sampling configuration was changed.

The dedicated `owalnuts-confirmation-archive` instance role can only put objects
and read exact object versions matching confirmation batch/review archive names
inside the existing content-addressed research prefix. It cannot delete objects,
manage instances, list the bucket, or access unrelated objects. The checked-in
trust and permission documents describe the applied role. No long-lived access
keys were copied to the instance. SDK packages are installed under the operations
cache, imported only in the controller process; the sampling environment and
its inherited environment variables are unchanged.

All full raw archives still require exact-version streamed checksum verification
before cleanup. Compact evidence is checked against the raw manifest, then itself
uploaded and exact-version verified. Temporary expanded review copies are removed
after validation. Compact reports and control receipts remain on EC2; Windows
copies can be retrieved asynchronously rather than stalling the next batch.

Files on EC2:

- Entry point: `/home/ubuntu/.cache/owalnuts-transfer/cloud_controller.py`
- Status/events: `/home/ubuntu/.cache/owalnuts-transfer/cloud-controller/`
- Startup output: `/home/ubuntu/.cache/owalnuts-transfer/cloud-controller-launch.log`

The cloud controller holds the existing exclusive operations lock throughout its
run, preventing simultaneous workstation mutations. Read its status file and
verify the PID with process inspection; the old helper's locked status endpoint
cannot be used while this controller owns the lock. Create `STOP` inside the
cloud status directory to stop at the next safe operation boundary; active bounded
sampling remains detached and is not interrupted. A reviewed restart takes the
first unfinished batch number and reconciles receipts before acting. Uncertain
or inconsistent evidence fails closed. Do not restart the workstation controller
while the cloud controller is active.

This is an operational speed/reliability change. Estimate throughput from actual
full cycles after migration; do not present reduced startup or network overhead
as a sampler performance result. Final inference and all scientific failure
denominators remain unchanged.
