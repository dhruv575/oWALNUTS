# Small-factor Fisher numerical qualification

Both frozen stages pass. This improves evaluation of the existing Fisher
estimator; it is not a new statistical estimator or a sampler-performance claim.

Float64 QR reduces the400-by-d sample factors to triangular d-by-d factors.
Only their products and the matrix square-root solve use80-digit arithmetic.
The unchanged original16-check suite passes: worst relative forward error
4.12e-9, formed covariance residual5.45e-9, permutation error8.42e-9. This includes
the difficult cases where earlier float64 and Newton implementations failed;
their failures remain preserved. No threshold relaxation or clipping was used.

On24 saved exposed hybrid01 pilot/score cells, all three repeated paired fits
per cell pass the1e-7 relative whitened covariance criterion against the original
80-digit full-sample oracle. Maximum observed error is1.624e-14. The geometric
paired fitting-time speedup is4.467x; per-cell geometric gains range2.968--6.982x.
Three repetitions are a small numerical timing sample, not independent model
replication. No target calls or new sampling were performed. Float64 factorization
can still lose input information; these checks do not prove arbitrary-condition
stability or bitwise sampler trajectory equivalence.

Whole-root supervision passed: algebra1.073s/43,388,928peakRSSbytes; model check
8.770s/108,953,600bytes. Both groups drained; final output462,393 and5,405,709bytes,
respectively. The pinned original fixtures, raw positions/scores, returned
covariances, timings and source hashes are retained.

Local105-member archive was read back and every member verified. SHA256:
5192635d84e94e7f6fda0ecc54d380078db5d9db1144e420abdac1d771b399c8.
No S3 upload or off-device backup is claimed.

The running sampler study was already terminal before this timing experiment.
Its failed continuation result remains unchanged. Do not attribute this4.467x
fitting gain to end-to-end WALNUTS runtime. Native full-schedule Fisher-HMC controls
are the next qualification step; any revised sampler implementation needs its
own frozen full-policy validation.
