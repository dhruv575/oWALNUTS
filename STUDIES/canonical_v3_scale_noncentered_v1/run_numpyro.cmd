@echo off
cd /d C:\dev\oWALNUTS\STUDIES\canonical_v3_scale_noncentered_v1
C:\dev\polyscope\.venv-bench\Scripts\python.exe numpyro_reference.py > artifacts\numpyro-log.txt 2>&1
echo exit %ERRORLEVEL% >> artifacts\numpyro-log.txt
