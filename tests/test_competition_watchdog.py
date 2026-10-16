import json

import pytest

from scripts.competition_watchdog import acquire_lock, runtime_command, supervise


def test_guard_restarts_same_version_after_supervisor_exit(tmp_path):
    commands = []

    class ExitedProcess:
        pid = 123
        returncode = 1

        def poll(self):
            return self.returncode

    def launch(command, **kwargs):
        commands.append(list(command))
        return ExitedProcess()

    command = runtime_command("python", "examples.free_multigame_agent_v10", "both")
    supervise(command, tmp_path, tmp_path, max_starts=2, backoff=0, popen=launch)
    assert commands == [command, command]
    assert "--tournament" in command and "--match" in command
    assert json.loads((tmp_path / "status.json").read_text())["starts"] == 2


def test_os_lock_prevents_second_guard_and_releases_on_close(tmp_path):
    first = acquire_lock(tmp_path)
    try:
        with pytest.raises(RuntimeError):
            acquire_lock(tmp_path)
    finally:
        first.close()
    acquire_lock(tmp_path).close()


def test_stop_marker_prevents_runtime_start(tmp_path):
    (tmp_path / "STOP").touch()
    def unexpected_start(*args, **kwargs):
        raise AssertionError("must not start")
    supervise(runtime_command("python", "agent", "testing"), tmp_path, tmp_path,
              popen=unexpected_start)
    assert json.loads((tmp_path / "status.json").read_text())["starts"] == 0


def test_transient_process_launch_failure_is_retried(tmp_path):
    attempts = []

    class ExitedProcess:
        pid = 123
        returncode = 0

        def poll(self):
            return self.returncode

    def launch(command, **kwargs):
        attempts.append(list(command))
        if len(attempts) == 1:
            raise PermissionError("temporary executable access failure")
        return ExitedProcess()

    command = runtime_command("python", "examples.free_multigame_agent_v10", "both")
    supervise(command, tmp_path, tmp_path, max_starts=2, backoff=0, popen=launch)
    assert attempts == [command, command]
    assert json.loads((tmp_path / "status.json").read_text())["starts"] == 2


def test_transient_log_open_failure_is_retried(tmp_path, monkeypatch):
    from pathlib import Path
    original_open = Path.open
    denied = False
    launches = []

    def open_with_one_failure(path, *args, **kwargs):
        nonlocal denied
        if path.name == "runtime.stderr.log" and not denied:
            denied = True
            raise PermissionError("temporary log sharing violation")
        return original_open(path, *args, **kwargs)

    class ExitedProcess:
        pid = 123
        returncode = 0

        def poll(self):
            return self.returncode

    def launch(command, **kwargs):
        launches.append(list(command))
        return ExitedProcess()

    monkeypatch.setattr(Path, "open", open_with_one_failure)
    command = runtime_command("python", "examples.free_multigame_agent_v10", "both")
    supervise(command, tmp_path, tmp_path, max_starts=2, backoff=0, popen=launch)
    assert denied and launches == [command]
    assert json.loads((tmp_path / "status.json").read_text())["starts"] == 2


def test_child_keeps_writable_logs_after_parent_handles_close(tmp_path):
    import subprocess
    import sys
    from scripts.competition_watchdog import start_runtime

    command = [sys.executable, "-u", "-c",
               "import sys; print('child stdout'); print('child stderr', file=sys.stderr)"]
    child = start_runtime(command, tmp_path, tmp_path, subprocess.Popen)
    try:
        assert child.wait(timeout=15) == 0
    finally:
        if child.poll() is None:
            child.kill()
            child.wait(timeout=5)
    assert "child stdout" in (tmp_path / "runtime.stdout.log").read_text()
    assert "child stderr" in (tmp_path / "runtime.stderr.log").read_text()
