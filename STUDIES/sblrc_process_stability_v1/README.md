# sblrc process stability diagnostic v1 — silent post-sampling fault reproduced

Status: preregistered in commit `44e42e9` before implementation or execution;
the instrumented harness was committed as `8e18e50` before execution. The
fixed 46-child matrix is complete.

## Question

WP35 observed one `sblrc` oWALNUTS subprocess end nonzero without stderr or a
raw result. This isolated study instruments model load, initialization,
evaluation, exact 1,000-warmup/1,000-retained sampling, result publication,
and explicit drop under one- and four-replica/thread configurations.

This is a process diagnostic only. Its seeds and outputs are not posterior
performance evidence, and evidence seed 90101 was forbidden and was not run.
The fixed design and classification rule are in `PREREGISTRATION.md` and
`protocol.json`.

## Verdict

**The process fault reproduced in one of 46 preregistered diagnostic
children.** The failing child was `sample-r4-t4-990603`: four replicas, four
threads, four chains, and exactly 1,000 warmup plus 1,000 retained transitions
per chain.

- Sampling completed and the raw result was durably written. It records a
  retained-sample count of 4,000, an all-finite aggregate, and a diagnostic
  checksum after 146,627 target calls; it does not contain the raw draws.
- Atomic heartbeats completed through `sampling/after` and
  `result_write/after`. The final event was `drop/before`; `drop/after` and
  `process/complete` were absent.
- The child then exited with raw/unsigned code `3221226356`, signed 32-bit
  `-1073740940`, hexadecimal `0xC0000374` (`STATUS_HEAP_CORRUPTION`), after
  3.313 seconds. Captured stdout and stderr were both empty, so this is a
  silent failure under the frozen rule.
- The other 45 children succeeded. This includes every standalone and
  in-process repeated load/drop child, every evaluation child, all three
  one-replica/thread sampling children, and two of three four-replica/thread
  sampling children.

The last durable event bounds an uninstrumented interval spanning the explicit
target drop plus the attempted `drop/after` heartbeat write. This is consistent
with teardown, but it is not proof that target destruction, library unload, or
any particular prior operation caused the fault. The root cause remains **not
established**. No child was rerun.

Full process records, immutable heartbeat events, raw outputs, stdout/stderr,
all 46 pre-launch markers, the matrix table, and the machine-readable verdict
are under `artifacts/`.

## Matrix result

| mode | configuration | result |
|---|---|---:|
| one load/drop | 1 replica / 1 thread | 12/12 succeeded |
| one load/drop | 4 replicas / 4 threads | 12/12 succeeded |
| evaluation | 1 replica / 1 thread | 6/6 succeeded |
| evaluation | 4 replicas / 4 threads | 6/6 succeeded |
| exact sampling | 1 replica / 1 thread / 1 chain | 3/3 succeeded |
| exact sampling | 4 replicas / 4 threads / 4 chains | 2/3 succeeded; 1 silent post-result fault |
| 20 in-process load/drop cycles | 1 replica / 1 thread | 2/2 succeeded |
| 20 in-process load/drop cycles | 4 replicas / 4 threads | 2/2 succeeded |

Durations are retained only as hang/timeout diagnostics, not performance
evidence. No child timed out and no raw output was missing.

## Executed-harness provenance

The binary left at the path named by every launch marker was hashed after the
study and before any review rebuild:

- executed-path SHA-256:
  `7f0c610b5904dc1a57cfbc0acb7e209496882e01bbfaaab86194806e1a90b95f`
  (3,826,944 bytes);
- clean committed-source rebuild SHA-256:
  `7b794659f65c47d091c9a388d8414e8d3639876c2196f2fa7225cdb113edfd7b`
  (3,826,944 bytes).

The full hashes differ, so byte-for-byte identity is not claimed. The
implementation commit and rebuild commit have identical Rust harness,
`Cargo.toml`, and `Cargo.lock` Git blobs, and every PE section in the two
executables has identical layout and SHA-256. The observed differences are in
the PE timestamp/checksum and trailing non-section data. This strongly ties the
loadable image to the committed source, but the binary was not hashed before
the children ran, so the post-execution capture remains a limitation. Full
commands, hashes, source identities, section hashes, and that limitation are
archived in `artifacts/executed-harness-manifest.json`.

## Checkout-portable checksums

The study-local `.gitattributes` requires LF for every tracked text file.
`checksums.py` also canonicalizes CRLF or lone-CR checkout bytes to LF in
memory before hashing. `CHECKSUMS.sha256` therefore records canonical Git
content rather than a platform-specific checkout representation; checksum
generation and verification never rewrite an input file.

`python checksums.py write` regenerates the manifest,
`python checksums.py verify` checks the current worktree, and
`python checksums.py verify-git HEAD` checks canonical blobs at a committed
revision. The manifest includes `.gitattributes` and `checksums.py` themselves.
Hashes for unchanged protocol and artifact content are preserved from the
original manifest; this portability update changes only control/documentation
metadata and the manifest that records it.

## Verify the archived study

```powershell
cd STUDIES\sblrc_process_stability_v1
cargo +1.88.0-x86_64-pc-windows-gnu fmt -- --check
cargo +1.88.0-x86_64-pc-windows-gnu check --locked
cargo +1.88.0-x86_64-pc-windows-gnu test --locked
python -m unittest -v test_run_stability.py
& 'C:\dev\owalnuts-wt\posteriordb-v6\STUDIES\posteriordb_bench_v6\.venv\Scripts\python.exe' .\run_stability.py verify
& 'C:\dev\owalnuts-wt\posteriordb-v6\STUDIES\posteriordb_bench_v6\.venv\Scripts\python.exe' .\run_stability.py analyze
python .\checksums.py verify
python .\checksums.py verify-git HEAD
```

`verify` reports the current harness size/hash and checks it against the
archived executed-binary manifest. `analyze` only regenerates summaries from
the 46 archived process records; it launches no child.

The archived records prevent reruns in two layers. An existing process record
is returned without launching anything. If a process record were absent but
its archived pre-launch marker remained, the orchestrator would record an
interrupted case rather than relaunch that child. The `run` command is
therefore unnecessary for verification and is intentionally omitted above.

The machine's default MSVC Rust target could not link because `link.exe` is
not installed. This was a build-environment issue, not a diagnostic result;
the installed Windows-GNU Rust 1.88 toolchain used by WP35 passed formatting,
check, and tests and built the executed release harness.
