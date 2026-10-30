param([ValidateRange(2,4)][int]$Chunk)
$ErrorActionPreference='Stop'
$studyDir=$PSScriptRoot
$label='hybrid{0:d2}' -f $Chunk
$previous='hybrid{0:d2}' -f ($Chunk-1)
$receipt=Get-Content "$studyDir/${previous}_archive/S3-VERIFICATION.json" -Raw | ConvertFrom-Json
$audit=Get-Content "$studyDir/$previous/RECLAIM.json" -Raw | ConvertFrom-Json
if(!$audit.completed -or $audit.s3_version -ne $receipt.version_id){throw 'Previous chunk not finalized'}
$frozen=Get-Content "$studyDir/hybrid01/SUMMARY.json" -Raw | ConvertFrom-Json
$frozenNames=@('run_hybrid.py','hybrid_prepare.py','hybrid_gate.py','fisher_high_precision.py','selector.py','selector_full_shape.py','HYBRID-VALIDATION.md')
foreach($name in $frozenNames){
    $entry=@($frozen.inputs.PSObject.Properties | Where-Object { $_.Name.EndsWith('/'+$name) })
    if($entry.Count -ne 1 -or (Get-FileHash "$studyDir/$name" -Algorithm SHA256).Hash.ToLower() -ne $entry[0].Value){throw "Frozen source changed: $name"}
}
$remoteBase='/home/ubuntu/lanes/metric-blocks-recovery-20261030'
$remoteRoot="$remoteBase/work/$label"
$python='/home/ubuntu/lanes/unified-readiness-20261027/installation02/work/env/bin/python'
$sshArgs=@('-o','BatchMode=yes','-o','HostKeyAlias=18.188.57.71','-i','C:/Users/dhruv/.ssh/owalnuts-bench.pem')
$hostName='ubuntu@18.223.162.103'
& ssh @sshArgs $hostName "mkdir $remoteRoot"
if($LASTEXITCODE -ne 0){throw 'Chunk directory exists or creation failed; inspect state, never restart automatically'}
$upload=@($frozenNames+@('test_hybrid_gate.py','verify_hybrid.py','archive_hybrid.py') | ForEach-Object { "$studyDir/$_" })
& scp @sshArgs @upload "${hostName}:$remoteRoot/"
if($LASTEXITCODE -ne 0){throw 'Source transfer failed'}
& ssh @sshArgs $hostName "OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONPATH=$remoteBase/work/fisher04/mpmath-1.3.0-py3-none-any.whl $python $remoteRoot/run_hybrid.py $Chunk"
if($LASTEXITCODE -ne 0){throw 'Controller did not exit cleanly; inspect authoritative remote state before any action'}
