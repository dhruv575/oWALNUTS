$ErrorActionPreference='Stop'
$archive=Join-Path $PSScriptRoot '../../STUDIES/usefulness_search_v1/real_counts_v1/application_archive01/evidence.tar.gz'
$expected='b33d881c03b5fd5e98c94bdee44b4ebb9372ff26bcdcd37f91f4f64776a6de05'
if((Get-FileHash -LiteralPath $archive -Algorithm SHA256).Hash.ToLower() -ne $expected){throw 'Local hash mismatch'}
$bucket='owalnuts-research-712710405275-us-east-2'
$key="verified/real_counts_application01/$expected.tar.gz"
$out=Join-Path $PSScriptRoot 'real-counts-application-s3-20261030'
if(Test-Path -LiteralPath $out){throw 'Receipt directory already exists; inspect before retrying'}
New-Item -ItemType Directory -Path $out | Out-Null
$put=aws s3api put-object --bucket $bucket --key $key --body $archive --profile owalnuts --region us-east-2 --output json
if($LASTEXITCODE -ne 0){throw 'Upload failed'}
$put | Set-Content (Join-Path $out 'UPLOAD.json')
$version=($put | ConvertFrom-Json).VersionId
if(-not $version){throw 'Missing version'}
$restored=Join-Path $out 'restored.tar.gz'
aws s3api get-object --bucket $bucket --key $key --version-id $version --profile owalnuts --region us-east-2 $restored | Set-Content (Join-Path $out 'DOWNLOAD.json')
if($LASTEXITCODE -ne 0){throw 'Restore failed'}
$actual=(Get-FileHash -LiteralPath $restored -Algorithm SHA256).Hash.ToLower()
if($actual -ne $expected){throw 'Restored hash mismatch'}
@{passed=$true;bucket=$bucket;key=$key;version_id=$version;sha256=$actual;bytes=(Get-Item -LiteralPath $restored).Length;scope='Exact-version restore matches complete locally member-verified archive; with exact-version training dependency recorded in archive'} | ConvertTo-Json | Set-Content (Join-Path $out 'VERIFICATION.json')
Get-Content (Join-Path $out 'VERIFICATION.json')
