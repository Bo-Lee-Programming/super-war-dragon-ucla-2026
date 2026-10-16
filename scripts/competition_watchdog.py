"""Restart one fixed official runtime after exit; never change its strategy.

Run before the tournament, keep this process alive, and use the same state-dir
for every version on this machine. The OS lock prevents duplicate watchdogs.
The SDK itself handles network and per-seat recovery. This outer process only
handles a stopped supervisor; it does not inspect matches or make decisions.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys
import time


def acquire_lock(directory):
    directory.mkdir(parents=True, exist_ok=True)
    handle = (directory / "watchdog.lock").open("a+b")
    try:
        if os.fstat(handle.fileno()).st_size == 0:
            handle.write(b"0")
            handle.flush()
        handle.seek(0)
        if os.name == "nt":
            import msvcrt
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        handle.close()
        raise RuntimeError("Another competition watchdog holds this state directory.") from None
    return handle


def runtime_command(python, module, mode):
    command = [str(python), "-u", "-m", "agent", "--agent", module]
    if mode in ("both", "tournament"):
        command.append("--tournament")
    if mode in ("both", "testing"):
        command.append("--match")
    return command


def write_status(directory, **data):
    document = {"updated_at": datetime.now(timezone.utc).isoformat(),
                "watchdog_pid": os.getpid(), **data}
    temp = directory / "status.tmp"
    try:
        temp.write_text(json.dumps(document, indent=2), encoding="utf-8")
        temp.replace(directory / "status.json")
    except OSError:
        # A transient lock/disk issue in monitoring must not stop gameplay.
        pass


def terminate_runtime(process):
    if os.name == "nt":
        # Windows venv python.exe is a launcher with a Python child. Terminate
        # only this Popen-owned tree, otherwise the child could remain playing.
        subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                       creationflags=subprocess.CREATE_NO_WINDOW, check=False)
    else:
        process.terminate()
    process.wait(timeout=20)


def supervise(command, cwd, directory, *, max_starts=None, interval=5,
              backoff=10, popen=subprocess.Popen, sleep=time.sleep):
    """A STOP marker requests shutdown; create it only when no match is active."""
    stop = directory / "STOP"
    starts = 0
    while not stop.exists() and (max_starts is None or starts < max_starts):
        starts += 1
        with (directory / "runtime.stdout.log").open("ab", buffering=0) as out, \
             (directory / "runtime.stderr.log").open("ab", buffering=0) as err:
            out.write(("\nRuntime start " + datetime.now(timezone.utc).isoformat() + "\n").encode())
            process = popen(command, cwd=str(cwd), stdout=out, stderr=err,
                            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
            while process.poll() is None:
                write_status(directory, state="running", runtime_pid=process.pid,
                             starts=starts, module=command[5], cwd=str(cwd))
                if stop.exists():
                    terminate_runtime(process)
                    write_status(directory, state="stopped", starts=starts)
                    return
                sleep(interval)
            write_status(directory, state="restarting", exit_code=process.returncode, starts=starts)
        if max_starts is None or starts < max_starts:
            # Check STOP during the delay; no rapid authentication retry storm.
            for _ in range(backoff):
                if stop.exists():
                    return
                sleep(1)
    write_status(directory, state="stopped", starts=starts)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--python", default=sys.executable)
    parser.add_argument("--module", default="examples.free_multigame_agent_v10")
    parser.add_argument("--mode", choices=("both", "tournament", "testing"), default="both")
    parser.add_argument("--working-dir", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--state-dir", type=Path, default=Path(".local_runtime/control"))
    args = parser.parse_args()
    directory = args.state_dir.resolve()
    try:
        lock = acquire_lock(directory)
    except RuntimeError as exc:
        print(str(exc), flush=True)
        return 2
    with lock:
        supervise(runtime_command(args.python, args.module, args.mode),
                  args.working_dir.resolve(), directory)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
