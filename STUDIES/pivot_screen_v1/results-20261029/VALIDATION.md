# Execution and validation receipt

- Pre-main protocol/source Git checkpoint: `2e92ea94`.
- Runtime: exact package versions and source hashes in SUMMARY.json and the raw
  archive's main-v1/MANIFEST.json.
- `python -m unittest test_screen test_inference`: six tests passed on EC2.
- `python -m unittest test_analysis`: two tests passed on EC2.
- Four disjoint sparse-case timing pilots completed, excluded from main results.
- Main planned/terminal/reported count: 400/400/400. All process groups drained;
  supervisor's final source-unchanged check passed.
- Sampled per-job resource limits: 900 seconds, 1 GiB RSS, 32 MiB output; 12
  exclusive one-core worker slots. No cap termination was observed.
- Raw archive SHA256 matched after transfer to Windows. Streaming verification
  checked all 3,853 evidence members and main source bindings. See
  ARCHIVE-VERIFICATION.json for the machine-readable verification receipt.
- The first local archive verification used random access inside gzip and was
  stopped for inefficient decompression. The verifier was changed to a single
  sequential pass and completed. No scientific job or evidence was changed.
- Remote evidence originals and verified local archive retained. S3 upload was
  not attempted after `aws sts get-caller-identity --profile owalnuts` reported
  an expired login. The existing confirmation-only EC2 role was not repurposed
  or expanded to bypass that limitation.
- Original option-flow working-tree changes were not included in this checkpoint.
