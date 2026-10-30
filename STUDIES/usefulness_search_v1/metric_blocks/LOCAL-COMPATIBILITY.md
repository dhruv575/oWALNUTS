# Local WSL compatibility preflight after AWS budget stop

No AWS compute or budget override. Use archived Linux binary/models extracted
with exact archive/member SHA verification. Isolated local Python3.14 environment,
scientific package versions pinned to EC2 records; Intel TBB2020.3.254 supplies
libtbb.so.2. Python, compiler runtime, hardware and TBB binary may differ.

Before new local validation, require64 analytic proper-prior regression joint
density/gradient checks: centered log-density error<=1e-6 and scaled gradient
error<=1e-7. Replay an archived bounded pilot and record non-timing parity without
assuming it across hardware. Replay the archived automatic second-stage input
and require all original reference/accuracy gates. This is environment qualification
using exposed inputs, not independent statistical replication or algorithm evidence.
Do not mix local/EC2 time measurements. Keep failed compatibility checks.

Whole worker invocation180s/2GiB/64MiB, monitored at the full output root. Use only
four sampler chains and one BLAS thread. All important output lives in the Windows
workspace, not transient EC2/WSL memory. Freeze a separate unused-seed protocol
before any fresh local experiment; reserve interrupted cloud seeds as exposed.
