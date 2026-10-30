# Temporary-workspace loss and verified recovery

On 2026-10-30 around 08:47 UTC, the contents of /dev/shm disappeared before this
audit's archive completed. The instance had not rebooted (uptime remained over
two days). The last observed systemd-tmpfiles-clean service completion was
08:03 UTC, not the disappearance time. We did not issue a cleanup command; the
cause/actor remains unknown. Do not claim that systemd or another agent caused it.

The first audit's analysis01 JSON files had already been copied locally. Initial
raw replay and curvature files had not yet been archived and were lost. Earlier
research checkpoints remain protected by their verified private S3 archives.

Recovery uses the existing local copy of the exact-version S3-restored reconsider
archive, SHA256 f4603f795562c0b1b6e67e7dc9184da8ec22d4377f053795a5ede6ce13d3a729,
previous version qdsWDPfzKcTqSlU0mOwKUGMPEyqErQvD. Its complete 218-member
inventory is reverified before extraction. Source and baseline draws are restored
without changing their bytes. This is not a new download from S3.

The recovered work runs on a dedicated tmpfs mounted under
/home/ubuntu/lanes/metric-blocks-recovery-20261030/work, outside /dev/shm. Each
completed replay is also copied to the persistent evidence directory immediately.
The original locally authored helper files are retained; recovery/ contains
path-adjusted copies, restored-path hash validation and durable per-job copies.
The scientific instrumentation, seeds, targets and algorithms are unchanged.

Reproduce both twelve-cell audits, verify complete baseline parity again, compare
the recovered first analysis with the locally saved original, and recompute the
curvature audit before archiving. This is recovery/reproducibility verification,
not additional independent scientific replication. The initial unarchived raw
curvature records cannot be asserted byte-identical because they no longer exist.

The final archive must contain RESTORE.json and RECOVERY-VERIFICATION.json along
with reproduced evidence. The root disk admission floor still applies; the
protected mount avoids spending root disk capacity on build products. Keep the
cleanup cause unresolved until evidence identifies it, and retain this incident.
