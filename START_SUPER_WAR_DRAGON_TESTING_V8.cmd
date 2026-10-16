@echo off
setlocal
cd /d "%~dp0"
echo [Super War Dragon V8] SELF-HOSTED PRIVATE TESTING ONLY; not tournament submission.
echo First create a Testing match in the official website with Mine (self-hosted) seat.
if not exist ".venv\Scripts\python.exe" (
  echo Python environment missing. See official starter README.
  pause
  exit /b 2
)
".venv\Scripts\python.exe" -m agent --check-tournament --agent examples.free_multigame_agent_v8
if errorlevel 1 (
  echo [BLOCKED] Self-hosted connection preflight failed, so no Testing runtime started.
  echo Check Agent Configuration, your own private .env, registration and network.
  pause
  exit /b 1
)
echo [READY] Listening for official Testing assignments. Ctrl+C stops this runtime.
".venv\Scripts\python.exe" -m agent --match --agent examples.free_multigame_agent_v8
set "RUN_RC=%ERRORLEVEL%"
echo Testing runtime exited with code %RUN_RC%.
pause
exit /b %RUN_RC%
