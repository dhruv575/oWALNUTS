# Callback failure capture

Separate diagnostic replay of the first failed WALNUTS fit: identical fixture,
seed and warmup count, threads reduced to 1 to make first-failure capture
race-free, retained draws reduced to 1. This is not a replacement reference run.
The same chain 3 transition 1 NaN occurred, and CAPTURE.npz preserves the first
failing input and observations. CAPTURE.json records its summary.

All input coordinates are finite; log_sigma=-29850.343 and mean(h)/2=-343526.463.
The native composition's exp(mean(h)/2) underflows to zero and triggers its
explicit NaN branch. This explains this captured callback failure, not every
possible future numerical failure. A stable direct formulation must be checked
before another sampling panel.

Run on one AWS CPU with a 120-second timeout and 4-GiB virtual-memory limit;
diagnostic sampling elapsed .472 seconds. Sources, raw capture and log are kept.
