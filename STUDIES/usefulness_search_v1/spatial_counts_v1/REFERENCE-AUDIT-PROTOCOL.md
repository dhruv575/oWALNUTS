# Terminal reference audit, frozen 2026-10-31

Wait for the original and repaired drivers' terminal status, at most 2700s
after the repair launch. Never launch another sampler or repeat a failed fit.
Then audit under600s/4GiB/16MiB, BLAS1, disk floor1GiB. Verify both source
hash manifests, every group's supervision, seeds/settings and raw positions.
Reconstruct every retained physical functional through the pinned BridgeStan
model, compare to saved values, and independently recompute each group's
Rhat/ESS/MCSE and qualification. Recompute the combined gates and pairwise
agreement when all groups qualify. Resource failures remain failed groups.

Write a durable AUDIT.json and a concise RESULT.md, even when no reference
qualifies. Waiting process writes a heartbeat every30s and has a finite deadline.
The watcher performs no deletion, retries, heldout scoring or notification.
This is a terminal audit, not a claim of an indefinitely autonomous research queue.
