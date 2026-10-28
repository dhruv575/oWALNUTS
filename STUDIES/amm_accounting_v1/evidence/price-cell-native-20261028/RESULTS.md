# Native callback parity admission

Twelve deterministic finite fixtures passed against the analytic implementation,
at T1, T12 and T250 (5, 27 and 503 coordinates). Maximum absolute density error
was 2.911e-11; maximum absolute gradient error was 2.001e-11. Extreme logistic
coordinates up to +/-1000 were included. Mutating caller-owned cell arrays
after compilation did not alter the native callback; NaN coordinates yielded
a NaN value and all-NaN gradient rather than a valid density.

The pinned AWS runtime compiled and ran these checks in 1.758 seconds under a
120-second outer timeout. This validates the tested native evaluation path,
not posterior sampling or warm retargeting. The analytic implementation has a
separate Stan comparison, but this check is not itself a direct native/Stan
comparison on every possible input. Retain these scope limits before sampling.
