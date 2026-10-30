param([ValidateRange(1,4)][int]$Chunk)
$ErrorActionPreference='Stop'
$studyDir=$PSScriptRoot
$label='hybrid{0:d2}' -f $Chunk
$remoteBase='/home/ubuntu/lanes/metric-blocks-recovery-20261030'
$remoteRoot="$remoteBase/work/$label"
$python='/home/ubuntu/lanes/unified-readiness-20261027/installation02/work/env/bin/python'
$sshArgs=@('-o','BatchMode=yes','-o','HostKeyAlias=18.188.57.71','-i','C:/Users/dhruv/.ssh/owalnuts-bench.pem')
$hostName='ubuntu@18.223.162.103'
& ssh @sshArgs $hostName "OPENBLAS_NUM_THREADS=1 $python $remoteRoot/verify_hybrid.py" | Out-Null
if($LASTEXITCODE -ne 0){throw 'Chunk verification failed'}
& ssh @sshArgs $hostName "$python $remoteRoot/archive_hybrid.py"
if($LASTEXITCODE -ne 0){throw 'Archive creation failed; inspect state before retry'}
New-Item -ItemType Directory -Force "$studyDir/$label" | Out-Null
New-Item -ItemType Directory -Force "$studyDir/${label}_archive" | Out-Null
& scp @sshArgs "${hostName}:$remoteRoot/SUMMARY.json" "${hostName}:$remoteRoot/VERIFICATION.json" "$studyDir/$label/"
if($LASTEXITCODE -ne 0){throw 'Summary transfer failed'}
& scp @sshArgs "${hostName}:$remoteBase/work/$label-evidence.tar.gz" "$studyDir/${label}_archive/evidence.tar.gz"
if($LASTEXITCODE -ne 0){throw 'Archive transfer failed'}
& python "$studyDir/../archive_s3.py" "$studyDir/${label}_archive/evidence.tar.gz" "$studyDir/${label}_archive" "hybrid-fresh-validation-chunk$('{0:d2}' -f $Chunk)-20261030"
if($LASTEXITCODE -ne 0){throw 'Private archive restoration verification failed'}
& scp @sshArgs "$studyDir/${label}_archive/S3-VERIFICATION.json" "${hostName}:$remoteBase/work/$label-receipt.json"
if($LASTEXITCODE -ne 0){throw 'Receipt transfer failed'}
& ssh @sshArgs $hostName "$python $remoteBase/work/reclaim_chunk_results.py $label $remoteBase/work/$label-receipt.json"
if($LASTEXITCODE -ne 0){throw 'Reclamation failed; inspect audit before retry'}
& scp @sshArgs "${hostName}:$remoteBase/evidence/$label-RECLAIM.json" "$studyDir/$label/RECLAIM.json"
if($LASTEXITCODE -ne 0){throw 'Reclamation audit transfer failed'}
