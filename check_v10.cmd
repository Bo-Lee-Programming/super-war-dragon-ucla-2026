@echo off
cd /d "%~dp0"
".venv\Scripts\python.exe" -m agent --check-tournament --agent examples.free_multigame_agent_v10
