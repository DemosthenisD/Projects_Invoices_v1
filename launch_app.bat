@echo off
title InvoiceApp — Production (port 8501)
cd /d "%~dp0"

:: Read current git branch so we can display it
for /f "delims=" %%i in ('git rev-parse --abbrev-ref HEAD 2^>nul') do set BRANCH=%%i
if "%BRANCH%"=="" set BRANCH=unknown

echo.
echo  =========================================
echo   InvoiceApp — PRODUCTION
echo   Branch : %BRANCH%
echo   URL    : http://localhost:8501
echo   Close this window to stop the app.
echo  =========================================
echo.

:: Warn if not on main, since this launcher is intended for production
if /i not "%BRANCH%"=="main" (
    echo  WARNING: you are NOT on the main branch.
    echo  If you want production, run: git checkout main
    echo.
    pause
)

:: Open browser after 4 seconds (gives Streamlit time to start)
start "" cmd /c "timeout /t 4 /nobreak >nul && start http://localhost:8501"

:: Launch Streamlit — headless flag stops Streamlit opening its own browser tab
streamlit run frontend/App.py --server.headless true

pause
