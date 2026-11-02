# Additional bounded native pilot

The native density/gradient preflight passes on 24 points, including rho=4.
Two original four-core spatial controls remain active. Use the remaining four
CPU slots for a third, explicitly additional native-grid seed 954100003 while
the original two grid seeds wait for those controls to drain. Even if the
additional pilot overlaps both queued grid jobs, the total is at most 12 CPUs.
Same model, numerical gates, 1000 warmup/2000 draws and 900-second cap.
Report all three seeds; this is not a replacement for a failed seed.
