"""One durable timed-analysis invocation, after explicit cross-study coordination."""
import json
import os
import signal
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
record_path = HERE/"analysis-execution.json"
with record_path.open("x") as handle:
    handle.write("{}\n")
record = dict(start_utc=datetime.now(timezone.utc).isoformat(), wrapper_pid=os.getpid(),
              affinity="0-3", hard_process_seconds_cap=300,
              timing_context="After both diagnostic sampling lanes drained; before WP97 official pooling; WP97 references may still run on cores8-15")
proc = None
started = time.monotonic()
try:
    env = dict(os.environ, OMP_NUM_THREADS="1", OPENBLAS_NUM_THREADS="1", MKL_NUM_THREADS="1", NUMEXPR_NUM_THREADS="1", NUMBA_NUM_THREADS="1")
    cmd = ["taskset", "-c", "0-3", "/home/ubuntu/venv/bin/python", str(HERE/"analyze.py")]
    with (HERE/"analysis.log").open("wb") as log:
        proc = subprocess.Popen(cmd, env=env, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
        record.update(pid=proc.pid, command=cmd, status="running")
        record_path.write_text(json.dumps(record, indent=2)+"\n")
        record["returncode"] = proc.wait(timeout=300)
        record["status"] = "completed" if record["returncode"] == 0 else "failed"
except Exception as exc:
    record.update(status="interrupted_or_failed", error=str(exc))
finally:
    if proc is not None and proc.poll() is None:
        try:
            os.killpg(proc.pid, signal.SIGTERM)
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            os.killpg(proc.pid, signal.SIGKILL)
            proc.wait()
        except ProcessLookupError:
            pass
    record.update(end_utc=datetime.now(timezone.utc).isoformat(), elapsed_seconds=time.monotonic()-started)
    record_path.write_text(json.dumps(record, indent=2)+"\n")
