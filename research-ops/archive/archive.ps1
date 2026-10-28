$ErrorActionPreference = 'Stop'
$bucket = 'owalnuts-research-712710405275-us-east-2'
$archiveRoot = 'C:/dev/owalnuts/target'
$auditRoot = "$archiveRoot/s3-archive-20261028"
$names = @('bounded-inventory-evidence-20261027.tar.gz','fresh-real-production-20261027-evidence.tar.gz','fresh-real-readiness-20261027-evidence.tar.gz','long-horizon-k400-20261027-evidence.tar.gz','long-horizon-readiness-20261027-evidence.tar.gz','market-replication-20261027-evidence.tar.gz','prior-predictive-validation-20261027-evidence.tar.gz','return-tail-20261027-evidence.tar.gz','risk-confirmation-evidence-20261027.tar.gz')
foreach ($name in $names) {
    $source = Join-Path $archiveRoot $name
    $hash = (Get-FileHash -Algorithm SHA256 -LiteralPath $source).Hash.ToLowerInvariant()
    $key = "evidence/sha256/$hash/$name"
    & aws s3 cp $source "s3://$bucket/$key" --profile owalnuts --region us-east-2 --sse AES256 --metadata "sha256=$hash" --only-show-errors
    if ($LASTEXITCODE -ne 0) { throw "Upload failed: $name" }
    $headText = & aws s3api head-object --bucket $bucket --key $key --profile owalnuts --output json
    if ($LASTEXITCODE -ne 0) { throw "Head failed: $name" }
    $head = $headText | ConvertFrom-Json
    if ($head.Metadata.sha256 -ne $hash -or $head.ContentLength -ne (Get-Item -LiteralPath $source).Length -or !$head.VersionId) { throw "Metadata mismatch: $name" }
    $restored = Join-Path $auditRoot "$name.restored"
    & aws s3api get-object --bucket $bucket --key $key --version-id $head.VersionId --profile owalnuts $restored | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "Restore failed: $name" }
    $restoredHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $restored).Hash.ToLowerInvariant()
    if ($restoredHash -ne $hash) { throw "Restored bytes mismatch: $name" }
    $record = @{utc=[DateTime]::UtcNow.ToString('o'); name=$name; source=$source; bucket=$bucket; key=$key; version_id=$head.VersionId; bytes=$head.ContentLength; sha256=$hash; restored_sha256=$restoredHash; verified=$true}
    $record | ConvertTo-Json -Compress | Add-Content -Encoding ascii "$auditRoot/verified.jsonl"
    # Only remove this script's verified redundant download, inside its audit directory.
    $resolved = (Resolve-Path -LiteralPath $restored).Path
    if (!$resolved.StartsWith((Resolve-Path -LiteralPath $auditRoot).Path + [IO.Path]::DirectorySeparatorChar)) { throw 'Restore cleanup outside audit directory' }
    Remove-Item -LiteralPath $resolved
    Write-Output "Verified $name ($($head.ContentLength) bytes)"
}
