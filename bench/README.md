# Benchmark box

Wall-time claims must come from a dedicated, documented machine; ESS per
gradient is the machine-independent primary figure everywhere else. This
directory makes any fresh Linux box a reproducible benchmark runner.

## Provision

- **Hetzner Cloud** (recommended: dedicated vCPUs, cheapest): Ubuntu 24.04,
  type `CCX33` (8 dedicated AMD EPYC vCPU) or `CCX23` (4 vCPU); add your SSH
  key; `ssh root@<ip>`.
- **AWS EC2**: Ubuntu 24.04, `c7i.2xlarge` (Intel) or `c7a.2xlarge` (AMD),
  80 GB gp3, SSH-only security group; `ssh ubuntu@<ip>`.

Either way the machine should run nothing else while a suite runs.

## Run

```bash
curl -fsSL https://get.docker.com | sh
git clone https://github.com/dhruv575/oWALNUTS && cd oWALNUTS
docker build -t owalnuts-bench bench/
docker run --rm --cpus=4 -v "$PWD/bench-out:/out" owalnuts-bench <commit-sha> sv-v2
```

Suites: `sv-v2` (native + PyMC thread-safe at 4 threads + three-seed nutpie
and NumPyro references, all five assets, sequential), `sv-v2-native`,
`smoke` (one BNB cell, a few minutes). Output: `bench-out/` holds
`measured_on.json` (CPU model, cores, kernel, toolchains, timestamps), the
per-cell run JSONs, `summary.json`, `RESULTS.md`, and the `.npz` functionals
— the same schema the study's `make_site_data.py` consumes, so the demo can
be regenerated from a benchmark-box run with a "measured on …" stamp.

`--cpus=4` caps the container at four cores so the native 4-thread cells and
the PyMC 4-thread cells see identical resources; raise `BENCH_THREADS` and
`--cpus` together if you want more.

## Notes

- Pinned stack: Rust 1.88, PyMC 5.28.5, nutpie 0.16.8, NumPyro 0.21.0,
  ArviZ 0.23.4 (the v1/v2 study versions). CmdStan is not in the image; the
  Eight Schools strict track (`STUDIES/eight_schools_v9_rebench_v1`) is the
  next suite to add.
- JAX compile time is excluded from NumPyro's sampling wall by the study
  scripts, as in v1; end-to-end walls are also recorded.
- Stop the server when the run finishes; a full `sv-v2` suite is well under
  an hour on `CCX33`.
