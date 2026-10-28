# E70 independent-reference precision extension

Status: running on the existing AWS instance. The frozen plan includes all 24
E66 reference points, with 4x16,000 retained draws instead of 4x4,000. Targets,
warmup, engine options and diagnostic gates are unchanged; seeds are fresh.
This is an exploratory new fit campaign, not a repair of the original study.

The first launch failed before sampling because the utilization monitor was
passed an integer instead of its expected core-allocation mapping. No campaign
directory or scientific job was created, and the monitor drained the process.
Its receipt is retained in evidence/attempt01. The mapping was corrected and
an isolated Linux containment test plus adapter argument test passed. The new
attempt uses a separate directory and the same frozen scientific settings.

Current root: `/home/ubuntu/lanes/reference-precision-extension-20261028-attempt02`.
The outer `supervise.py` contains the entire campaign (3,000 seconds, sampled
22 GiB RSS and 4 GiB output). Each job has its own four-core group and bounds.
Its final receipt is `SUPERVISION.json`; the all-job ledger is `campaign01/FINAL.json`.
Monitor live processes and these handles; do not relaunch because a polling
connection expires. First four jobs were observed exiting zero; numerical
completion is separate from passing convergence/precision gates.

Do not interpret partial results as a success rate. Final reporting must retain
all 24 slots and original failures, compare like-for-like identities and check
the original sealed artifact hashes. Report unavailable/failed jobs explicitly.
