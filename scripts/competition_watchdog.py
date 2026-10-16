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


def start_runtime(command, cwd, directory, popen):
    """Open child logs and launch; the child owns its inherited log handles."""
    streams = []
    try:
        for name in ("runtime.stdout.log", "runtime.stderr.log"):
            streams.append((directory / name).open("ab", buffering=0))
        out, err = streams
        out.write(("\nRuntime start " + datetime.now(timezone.utc).isoformat() + "\n").encode())
        return popen(command, cwd=str(cwd), stdout=out, stderr=err,
                     creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
    finally:
        # Parent copies are unnecessary after Popen duplicates/inherits them.
        # A close failure must never conceal a successfully launched process.
        for stream in streams:
            try:
                stream.close()
            except OSError:
                pass


def supervise(command, cwd, directory, *, max_starts=None, interval=5,
              backoff=10, popen=subprocess.Popen, sleep=time.sleep):
    """A STOP marker requests shutdown; create it only when no match is active."""
    stop = directory / "STOP"
    starts = 0
    while not stop.exists() and (max_starts is None or starts < max_starts):
        starts += 1
        try:
            process = start_runtime(command, cwd, directory, popen)
        except OSError as exc:
            # Retry temporary file-sharing, disk and executable-access errors.
            # Catch only launch failures: a running process must not be replaced
            # merely because a monitoring operation failed.
            write_status(directory, state="launch_failed", error_type=type(exc).__name__,
                         error_number=exc.errno, starts=starts)
        else:
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
