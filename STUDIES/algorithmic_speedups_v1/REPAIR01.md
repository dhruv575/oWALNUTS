# Native baseline launch repair

The original two native spatial jobs failed before sampling because libtbb.so.2
was not on the dynamic loader path. Preserve their logs and supervision files.
Rerun identical seeds and source under repair01 with LD_LIBRARY_PATH pointing
to the existing gp-portable-runtime-20261030/models directory. No inference
setting changed. Other original workers are allowed to finish.

The followup dispatcher reserves eight CPUs for these baselines and two for
physics, leaving two for the original dense controls. All jobs retain the
original wall/RSS/disk safeguards. Physics output is bounded to 24 MiB per job;
expected aggregate including spatial is below 200 MiB. Do not add more jobs
until inspecting disk and active workers.
