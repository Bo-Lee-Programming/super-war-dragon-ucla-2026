@echo off
setlocal
cd /d "%~dp0"
echo [Super War Dragon V8] Official platform connection preflight - no match will be played.
if not exist ".venv\Scripts\python.exe" (
  echo Python environment missing. See official starter README.
  pause
  exit /b 2
)
".venv\Scripts\python.exe" -m agent --check-tournament --agent examples.free_multigame_agent_v8
set "CHECK_RC=%ERRORLEVEL%"
if not "%CHECK_RC%"=="0" (
  echo.
  echo Preflight failed: check Self-hosted selection, registration, Official Agent Key in private .env, and internet.
  echo Never share or publish the Agent Key.
)
pause
exit /b %CHECK_RC%
