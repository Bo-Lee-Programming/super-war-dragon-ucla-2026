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
