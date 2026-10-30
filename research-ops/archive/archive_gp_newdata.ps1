$ErrorActionPreference='Stop'
$archive=Join-Path $PSScriptRoot '../../STUDIES/usefulness_search_v1/metric_blocks/local_recovery/gp_newdata_comparison_archive01/evidence.tar.gz'
$expected='c1b26f77c8fda91858e72e91da98af3eadc0ca38a2955d14138a3f1ac3734a34'
if((Get-FileHash -LiteralPath $archive -Algorithm SHA256).Hash.ToLower() -ne $expected){throw 'Local hash mismatch'}
$bucket='owalnuts-research-712710405275-us-east-2'
$key="verified/gp_newdata_comparison01/$expected.tar.gz"
$out=Join-Path $PSScriptRoot 'gp-newdata-s3-20261030'
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
@{passed=$true;bucket=$bucket;key=$key;version_id=$version;sha256=$actual;bytes=(Get-Item -LiteralPath $restored).Length;scope='Exact-version restore matches complete locally member-verified archive; dependency archives separate'} | ConvertTo-Json | Set-Content (Join-Path $out 'VERIFICATION.json')
Get-Content (Join-Path $out 'VERIFICATION.json')
