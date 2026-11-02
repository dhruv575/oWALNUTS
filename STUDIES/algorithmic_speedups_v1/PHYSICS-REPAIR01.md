# Physics preflight serialization repair

The preparation job computed its frozen transport but failed while serializing
a NumPy boolean in the numerical-check summary. No evaluation sampling ran.
Preserve physics/prepare and the original worker source as
physics_worker_before_repair01.py.txt. Convert check scalars to Python types,
and resolve the training artifact relative to each campaign's output directory.
Rerun the unchanged preparation seed and checks under physics_repair01, then
launch the original fixed evaluation jobs only if all checks pass.
