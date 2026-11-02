# Audit serialization repair

The first post-sampling audit completed calculations but could not serialize
NumPy int64 probe indices. Convert indices to ordinary Python integers and
rerun the identical deterministic audit. No model, samples, thresholds or
probe selection changes. Preserve the original auditor source on the lane.
