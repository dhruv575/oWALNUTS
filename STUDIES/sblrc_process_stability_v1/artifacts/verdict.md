# Verdict

A process-stability fault reproduced in 1/46 diagnostic children: sample-r4-t4-990603 exited 0xC0000374 (STATUS_HEAP_CORRUPTION), silently, after the last durable heartbeat drop/before. The uninstrumented interval spans target drop plus the attempted next heartbeat; it is consistent with teardown but does not prove that teardown caused the fault.

Root cause: not established. This study is not posterior-performance evidence.
