# Verified research archive

Bucket: `s3://owalnuts-research-712710405275-us-east-2`, Ohio (us-east-2).
Created 2026-10-28 with user authorization. Public access is blocked, versioning
is enabled, default encryption is AES256, and bucket policy denies non-TLS
requests. No public ACL, new access key or EC2 instance role was introduced.
Access uses the existing authenticated `owalnuts` CLI profile.

## First verified batch

Nine completed evidence archives, 1,467,406,235 bytes total, were uploaded from
the verified local copies. Each object was downloaded by its exact version ID
and SHA-256 checked against the local original. Keys contain the content hash.
`evidence-20261028/verified.jsonl` records object keys, versions, sizes and hashes.
Both local originals and expanded evidence remain; only redundant EC2 tarballs
were removed after a separate remote-byte check. No active runtime was removed.

An additional 849 historical raw files (3,688,001,763 bytes) were removed from
three retired source checkouts, limited to
`STUDIES/chain_rescue_v2/artifacts/raw`. Every file matched its Git blob; all
283 unique blobs were independently read from the local main repository and
SHA-256 checked. Their source commits are ancestors of pushed `origin/main`.
Git objects in the old checkouts remain intact. These files are preserved in
Git, not counted as additional S3 evidence uploads. The manifests distinguish
these two preservation routes.

Total reclaimed: 5,155,407,998 bytes. EC2 `df -h /` changed from approximately
7.8 GB free to 13 GB free. This is initial bounded cleanup, not a claim that all
historical experiment data has been archived or all redundancy removed.

## Restore

For an archived experiment, read its record in `verified.jsonl`, then use:

```powershell
aws s3api get-object --bucket owalnuts-research-712710405275-us-east-2 --key <record.key> --version-id <record.version_id> --profile owalnuts <destination>
Get-FileHash -Algorithm SHA256 -LiteralPath <destination>
```

Require the recorded SHA-256 before extracting. Inspect archive member paths,
extract into a new directory, and verify the archive's internal artifact
manifest before using it. Restore any path-based input bindings before rerunning
an old campaign; immutable historical plans retain their original paths.

The deleted Git working files can be restored in their original checkout with
`git restore --source=<record.commit> --worktree -- <record.relative>`, using
the exact fields from `git-duplicates.json`. Verify the recorded SHA-256 after
restoration. Never use a broad `git reset --hard` for this purpose.

## Continuing policy

Keep current compute inputs/environments on EC2. Seal completed studies with
source revision, configurations, data provenance, raw outcomes, diagnostics and
hash manifests. Upload, restore by version, verify, and then consider redundant
working-copy removal. Preserve failed experiments too. Do not archive credentials.

S3 Standard is intentional while access patterns are developing. Versioned
overwrites retain billable old versions. Avoid repeated uploads to the same key
when the existing version has already passed verification. No expiration rule
has been enabled for scientific evidence. Current Ohio first-tier Standard rate
is $0.023/GB-month, verified against the AWS regional pricing feed on 2026-10-28;
requests and transfers are additional. This first batch is roughly $0.03/month
for storage alone. The full working-directory footprint is not the archived size.

The scripts are provenance for this fixed batch, not an unattended general
garbage collector. `archive.ps1` will upload new object versions if rerun; consult
the completed receipts first. Cleanup scripts deliberately reject missing,
changed or unexpected inputs rather than guessing.
