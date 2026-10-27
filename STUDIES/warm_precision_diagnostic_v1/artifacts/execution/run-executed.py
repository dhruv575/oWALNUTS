"""Durable, bounded six-cell supervisor. Run --preflight or --run on the box."""
import argparse
import hashlib
import json
import os
import platform
import signal
import subprocess
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROTO = json.loads((HERE / "protocol.json").read_text())
ART = HERE / "artifacts"


def utc():
    return datetime.now(timezone.utc).isoformat()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")
    tmp.replace(path)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def preflight():
    checks = []
    for name, spec in PROTO["inputs"].items():
        path = Path(spec["path"])
        actual = sha(path)
        if actual != spec["sha256"]:
            raise RuntimeError(f"{name} hash changed: {actual}")
        checks.append(dict(name=name, path=str(path), sha256=actual, bytes=path.stat().st_size))
    repo = PROTO["source_repo"]
    commit = subprocess.check_output(["git", "-C", repo, "rev-parse", "HEAD"], text=True).strip()
    status = subprocess.check_output(["git", "-C", repo, "status", "--porcelain", "--untracked-files=no"], text=True)
    if commit != PROTO["source_commit"] or status:
        raise RuntimeError("Original source checkout is not clean at the frozen commit")
    return dict(utc=utc(), inputs=checks, source_commit=commit, source_tracked_status=status,
                python=platform.python_version(), platform=platform.platform(),
                study_sources={p.name: sha(p) for p in (HERE/"run.py", HERE/"protocol.json", HERE/"PLAN.md")},
                processes=subprocess.check_output(["ps", "-eo", "pid,psr,pcpu,args", "--sort=-pcpu"], text=True))


def stop(proc):
    try:
        os.killpg(proc.pid, signal.SIGTERM)
    except ProcessLookupError:
        return
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        proc.wait(timeout=5)


def run():
    # Exclusive creation prevents a second supervisor or a silent restart.
    ART.mkdir(exist_ok=False)
    evidence = preflight()
    write(ART/"preflight.json", evidence)
    started = time.monotonic()
    deadline = started + PROTO["sampling_seconds_cap"]
    write(ART/"launch.json", dict(pid=os.getpid(), utc=utc(), deadline_seconds=PROTO["sampling_seconds_cap"],
                                 protocol_sha256=sha(HERE/"protocol.json"), source_sha256=sha(HERE/"run.py")))
    (ART/"cells").mkdir()
    (ART/"logs").mkdir()
    status_dir = ART/"status"
    status_dir.mkdir()
    halt = threading.Event()
    halt_reason = []
    threads = []

    def lane(name):
        try:
            for cell in (c for c in PROTO["cells"] if c["lane"] == name):
                record = dict(cell=cell, status="planned", supervisor_pid=os.getpid())
                record_path = status_dir/(cell["id"]+".json")
                if halt.is_set() or time.monotonic() >= deadline:
                    record.update(status="not_started_budget", end_utc=utc())
                    write(record_path, record)
                    continue
                output = ART/"cells"/cell["id"]
                if output.exists():
                    raise RuntimeError(f"Refusing existing output {output}")
                cmd = ["taskset", "-c", cell["cores"], PROTO["inputs"]["binary"]["path"], "warm",
                       PROTO["inputs"]["data_"+cell["stream"]]["path"], str(PROTO["window"]),
                       str(cell["K"]), str(PROTO["sampler_seed"]), str(PROTO["ticks"]), "frozen",
                       str(PROTO["save_every"]), str(output)]
                env = dict(os.environ, RAYON_NUM_THREADS="4", OMP_NUM_THREADS="1", OPENBLAS_NUM_THREADS="1",
                           MKL_NUM_THREADS="1", NUMEXPR_NUM_THREADS="1")
                t0 = time.monotonic()
                record.update(status="starting", command=cmd, start_utc=utc())
                write(record_path, record)
                with (ART/"logs"/(cell["id"]+".log")).open("wb") as log:
                    proc = subprocess.Popen(cmd, stdout=log, stderr=subprocess.STDOUT, env=env, start_new_session=True)
                    record.update(pid=proc.pid, status="running")
                    write(record_path, record)
                    while proc.poll() is None:
                        if halt.is_set() or time.monotonic() >= deadline:
                            stop(proc)
                            record["status"] = "interrupted_budget"
                            break
                        write(status_dir/("heartbeat-"+name+".json"), dict(pid=proc.pid, cell=cell["id"], utc=utc(), elapsed_seconds=time.monotonic()-t0))
                        time.sleep(2)
                    record.update(returncode=proc.wait(), end_utc=utc(), elapsed_seconds=time.monotonic()-t0)
                    if record["status"] == "running":
                        record["status"] = "process_completed" if record["returncode"] == 0 else "process_failed"
                    write(record_path, record)
                    print(json.dumps(record), flush=True)
        except Exception as exc:
            halt_reason.append(f"lane {name}: {exc}")
            halt.set()
            write(status_dir/("lane-error-"+name+".json"), dict(utc=utc(), error=str(exc)))

    for name in ("A", "B"):
        worker = threading.Thread(target=lane, args=(name,))
        worker.start()
        threads.append(worker)
    while any(t.is_alive() for t in threads):
        size = 0
        for p in ART.rglob("*"):
            try:
                if p.is_file():
                    size += p.stat().st_size
            except FileNotFoundError:
                pass  # An atomic status-file replacement may race the inventory.
        if size > PROTO["artifact_bytes_cap"]:
            halt_reason.append("artifact_bytes_cap")
            halt.set()
        if time.monotonic() >= deadline:
            if "sampling_seconds_cap" not in halt_reason:
                halt_reason.append("sampling_seconds_cap")
            halt.set()
        time.sleep(2)
    for worker in threads:
        worker.join()
    statuses = []
    for cell in PROTO["cells"]:
        path = status_dir/(cell["id"]+".json")
        if not path.exists():
            write(path, dict(cell=cell, status="not_started_supervisor_error", end_utc=utc()))
        statuses.append(json.loads(path.read_text()))
    write(ART/"DONE.json", dict(utc=utc(), supervisor_pid=os.getpid(), elapsed_seconds=time.monotonic()-started,
                               halt_reasons=halt_reason, cells=statuses))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--preflight", action="store_true")
    mode.add_argument("--run", action="store_true")
    args = parser.parse_args()
    if args.preflight:
        print(json.dumps(preflight(), indent=2))
    else:
        run()
