@echo off
cd /d "%~dp0"
".venv\Scripts\python.exe" scripts\competition_watchdog.py --module examples.free_multigame_agent_v10 --mode both --state-dir .local_runtime\control
