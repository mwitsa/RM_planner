@echo off
cd /d "%~dp0"
where py >nul 2>nul
if %errorlevel%==0 (
  py app.py
) else (
  python app.py
)
set "APP_EXIT_CODE=%errorlevel%"
if not "%APP_EXIT_CODE%"=="0" (
  echo.
  echo Application stopped with exit code %APP_EXIT_CODE%.
  echo Copy the error above or take a screenshot before closing this window.
  pause
)
exit /b %APP_EXIT_CODE%
