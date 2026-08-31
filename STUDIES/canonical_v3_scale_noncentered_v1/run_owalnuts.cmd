@echo off
cd /d C:\dev\oWALNUTS\STUDIES\canonical_v3_scale_noncentered_v1
echo sampling started %DATE% %TIME% > artifacts\owalnuts-v1-log.txt
target\release\canonical-v3-scale-noncentered-v1.exe --out artifacts/owalnuts-v1 --kernel-commit d8617a8 >> artifacts\owalnuts-v1-log.txt 2>&1
echo exit %ERRORLEVEL% >> artifacts\owalnuts-v1-log.txt
