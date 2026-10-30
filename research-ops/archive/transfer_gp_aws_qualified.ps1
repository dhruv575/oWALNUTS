$ErrorActionPreference='Stop'
$root=Join-Path $PSScriptRoot '../../STUDIES/usefulness_search_v1/metric_blocks/local_recovery'
$out=Join-Path $root 'gp_aws_qualified_remote01.tar.gz'
if(Test-Path -LiteralPath $out){throw 'Existing transfer; inspect rather than overwrite'}
$info=New-Object System.Diagnostics.ProcessStartInfo
$info.FileName='ssh.exe'
$info.Arguments='-o BatchMode=yes -i C:/Users/dhruv/.ssh/owalnuts-bench.pem ubuntu@18.223.111.36 /home/ubuntu/venv/bin/python /home/ubuntu/stream_gp_aws_qualified_archive.py'
$info.UseShellExecute=$false;$info.RedirectStandardOutput=$true;$info.RedirectStandardError=$true;$info.CreateNoWindow=$true
$process=New-Object System.Diagnostics.Process;$process.StartInfo=$info
$stream=[IO.File]::Open($out,[IO.FileMode]::CreateNew)
try{
 if(-not $process.Start()){throw 'SSH start failed'}
 $errorTask=$process.StandardError.ReadToEndAsync()
 $process.StandardOutput.BaseStream.CopyTo($stream)
 $process.WaitForExit();$errorText=$errorTask.Result
}finally{$stream.Dispose()}
$errorText | Set-Content (Join-Path $root 'gp_aws_qualified_transfer.log')
if($process.ExitCode -ne 0){throw "SSH transfer failed: $errorText"}
if($errorText -notmatch 'ARCHIVE_SHA256=([a-f0-9]{64})'){throw 'Missing remote digest'}
$remoteHash=$Matches[1];$localHash=(Get-FileHash -LiteralPath $out -Algorithm SHA256).Hash.ToLower()
if($remoteHash -ne $localHash){throw 'Transfer hash mismatch'}
@{passed=$true;sha256=$localHash;bytes=(Get-Item -LiteralPath $out).Length;scope='Binary streamed tar; remote stream SHA256 matches local file; no extra EC2 tarball'} | ConvertTo-Json | Set-Content (Join-Path $root 'gp_aws_qualified_transfer.json')
Get-Content (Join-Path $root 'gp_aws_qualified_transfer.json')
