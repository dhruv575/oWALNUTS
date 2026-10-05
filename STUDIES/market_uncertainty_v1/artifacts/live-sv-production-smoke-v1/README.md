# Actual production-path synthetic smoke — prepared only

Do not execute until root releases the rolling-campaign timing hold. No fixture generation, imports, tests, or sampler has run for this preparation.

The runner creates 24 half-hour synthetic receipt origins, trade flow and small native returns. It invokes the real issue() function and its unmodified contained public production worker (4 chains, 1,000 warmup, first-passing 1,000/2,000/4,000 retained tiers). Initialization/sampler/predictive seeds 1/2/3 are declared development-test reuse, not fresh scientific streams. No fake worker or relaxed gates.

The synthetic origin clock starts after issuer/scorer imports and advances using real monotonic elapsed time. Issuance has the actual 60-second deadline; production_worker receives remaining time minus its five-second reserve. Imports and post-hoc scoring remain charged in outer elapsed time. A timeout, failed gate or late publication is retained; no retry. Synthetic future receipts are added only to a separate copied capture after issuance. Provisional and simulated terminal reconciliation use the same pinned issuance. This demonstrates integration, never a live market forecast or receipt-history acquisition.

After authorization, from C:/dev/owalnuts:

    target/python-workflow-env/Scripts/python.exe target/sv-online-production-smoke-v1/smoke.py prepare --out target/sv-online-production-smoke-v1/prepared-v1
    target/python-workflow-env/Scripts/python.exe -m pytest target/sv-online-production-smoke-v1/test_smoke.py -q
    target/python-workflow-env/Scripts/python.exe target/sv-online-production-smoke-v1/smoke.py admit --config target/sv-online-production-smoke-v1/prepared-v1/config.json
    target/python-workflow-env/Scripts/python.exe target/sv-online-production-smoke-v1/smoke.py run --config target/sv-online-production-smoke-v1/prepared-v1/config.json --out target/sv-online-production-smoke-v1/run-v1

All directories and result files use exclusive creation. Preparation captures exact current study/options sources, Python executable, runner, receipt files and released adapter/native hashes. The actual worker receives the pinned PYTHONPATH. An integration_pass requires a timely issued interval and both real scoring paths to score the same later synthetic return. A completed runner with integration_pass=false is a retained negative result, not a request for automatic rerun.
