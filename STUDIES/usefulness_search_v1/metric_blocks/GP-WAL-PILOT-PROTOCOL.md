# WALNUTS pilot cost repair

The fresh-data transport workflow failed its full-pilot-inclusive advancement
rule despite positive sampling-only efficiency. Test one cost mechanism: use
raw WALNUTS dense/.9 for the pilot instead of native diagonal/.999. Preserve
four chains,1100 warmup,2000 retained, first100 retained per chain for map fit,
bounded map K4/ridge10, and the original 24-functional pilot accuracy gates.
All four fixed datasets included, seeds950200001..4; no tuning, extensions,
retries or dropping failures. Maps are produced only for qualified pilots.
This is a calibration/repair on exposed data, not fresh generalization evidence.
Record full gradient calls and map-fit time; no claimed downstream benefit until
fresh production validation and full costs vs raw WALNUTS and strong baselines.
Existing native pilots and failed workflow results remain immutable.
Four bounded workers x four chains, BLAS1;180s/2GiB/64MiB each,2GiB free disk.
