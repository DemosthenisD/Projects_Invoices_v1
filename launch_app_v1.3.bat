@echo off
title InvoiceApp — v1.3 ux/improvements (port 8504)
cd /d "%~dp0"

:: Read current git branch so we can display it
for /f "delims=" %%i in ('git rev-parse --abbrev-ref HEAD 2^>nul') do set BRANCH=%%i
if "%BRANCH%"=="" set BRANCH=unknown

echo.
echo  =========================================
echo   InvoiceApp — v1.3
echo   Recurring Fees + Receivables
echo   Branch : %BRANCH%
echo   URL    : http://localhost:8504
echo   Close this window to stop the app.
echo  =========================================
echo.

:: Warn if not on the expected branch
if /i not "%BRANCH%"=="ux/improvements" (
    echo  WARNING: expected branch ux/improvements
    echo  but you are on: %BRANCH%
    echo  Switch branches or use another launcher.
    echo.
    pause
)

:: Open browser after 4 seconds (gives Streamlit time to start)
start "" cmd /c "timeout /t 4 /nobreak >nul && start http://localhost:8504"

:: Launch Streamlit on port 8504
streamlit run frontend/App.py --server.port 8504 --server.headless true

pause
