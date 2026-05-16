@echo off
title InvoiceApp — Dev/Refactor (port 8502)
cd /d "%~dp0"

:: Read current git branch so we can display it
for /f "delims=" %%i in ('git rev-parse --abbrev-ref HEAD 2^>nul') do set BRANCH=%%i
if "%BRANCH%"=="" set BRANCH=unknown

echo.
echo  =========================================
echo   InvoiceApp — DEV / REFACTOR
echo   Branch : %BRANCH%
echo   URL    : http://localhost:8502
echo   Close this window to stop the app.
echo  =========================================
echo.

:: Warn if somehow on main — dev launcher is not intended for the main branch
if /i "%BRANCH%"=="main" (
    echo  NOTE: you are on the main branch.
    echo  Use launch_app.bat for production, or
    echo  switch to your refactor branch first.
    echo.
    pause
)

:: Open browser after 4 seconds (gives Streamlit time to start)
start "" cmd /c "timeout /t 4 /nobreak >nul && start http://localhost:8502"

:: Launch Streamlit on a different port so production can run at the same time
streamlit run frontend/App.py --server.port 8502 --server.headless true

pause
