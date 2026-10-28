# Three-update candidate-budget confirmation

All four paths and all twelve warm/cold update pairs completed. Every one of
503 coordinates passed Rhat<=1.01 and bulk/tail ESS>=400 in both methods for
every update; retained divergences and depth-limit hits were zero. Largest
absolute coordinate-mean discrepancy was 3.616 combined MCSEs. This is fresh
continuation randomness from shared static starting states, not independent
data generalization or exact posterior proof.

At cell width .001, warm sampling took 10.274--11.177 seconds per update;
cold adaptation plus sampling took 13.193--14.266. At width .00001, warm took
20.263--20.998 versus cold 10.796--11.402. Warm used 1,024 draws per chain,
cold 4,000 retained plus 2,000 adaptation. Actual phases are recorded separately
from compilation, summary computation and serialization. These costs and
threshold passes do not imply precision-matched superiority, especially since
the narrow-cell warm route is slower despite its smaller draw budget.

Outer elapsed time was 137.737 seconds, peak RSS 7,752,491,008 bytes and final
output 1,337,177,568 bytes. All processes drained and sources stayed unchanged.
The downloaded report archive and all launch source bindings were verified.
The full 1,327,816,304-byte archive was subsequently downloaded and verified;
all 24 traces were reproduced by the planned predictive-CDF analysis. See
../price-cell-repeated-predictive-20261028/RESULTS.md and FULL-ARCHIVE-VERIFIED.json.
The exact-version S3 restore also matched the full archive (S3-VERIFIED.json).
Subsequent verified cleanup removed twelve redundant cold NetCDF files and
the compressed EC2 archive, reclaiming 2,464,891,949 bytes (CLEANUP.json).
The full verified local/S3 archive, AWS warm draws and metadata remain available.

No market observation assumption, empirical predictive calibration, economic
decision value or profitability claim is established by these synthetic paths.
