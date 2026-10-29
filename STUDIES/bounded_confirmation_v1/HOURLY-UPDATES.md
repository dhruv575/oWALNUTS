# Hourly research consultations

User instruction, 2026-10-29: send hourly updates starting immediately. This
supersedes the earlier milestone-only notification cadence for this thread.

The EC2 system timer `owalnuts-hourly-updates.timer` runs a separate oneshot
service as ubuntu every hour. The initial consultation was accepted at
2026-10-29 07:43:39 UTC; the first scheduled follow-up is 08:43:40 UTC.
The notifier calls the same Agent Comms `/bridge/consult` endpoint and request-ID
scheme used by the `consult_user` MCP implementation, pinned to thread
`01a18138-672f-76d0-8e2b-5e782bc9a8e6`. It does not need the workstation online.

The report reads operational receipts and diagnostic qualification counts only.
It verifies the controller PID/command, reports finished and archived slots,
missing reports, disk space and an ETA from recent complete cycles. Forecast
scores remain sealed. A stopped controller is reported as stopped rather than
silently reusing a stale status as proof of health.

Consultation payloads are persisted before transmission and retried unchanged.
Accepted slots are recorded to prevent duplicate hourly notifications. Network
failures retry after 60 seconds. The relay configuration is kept outside Git,
mode 0600, at `/home/ubuntu/.cache/owalnuts-transfer/hourly-updates-secret.json`;
its bridge credential is never logged. Receipts and pending payloads live in
the sibling `hourly-updates` directory. No owner or device credentials are used.

Inspect with `systemctl list-timers owalnuts-hourly-updates.timer` and
`journalctl -u owalnuts-hourly-updates.service`. To stop future notifications,
disable/stop the timer and stop the service (including pending retry restarts).
This notification service does not alter or stop research jobs.
