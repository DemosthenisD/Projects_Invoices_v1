@echo off
title InvoiceApp — Local
cd /d "%~dp0"

echo.
echo  =========================================
echo   InvoiceApp — starting locally
echo   Browser will open in a few seconds.
echo   Close this window to stop the app.
echo  =========================================
echo.

:: Open browser after 4 seconds (gives Streamlit time to start)
start "" cmd /c "timeout /t 4 /nobreak >nul && start http://localhost:8501"

:: Launch Streamlit — headless flag stops Streamlit opening its own browser tab
streamlit run frontend/App.py --server.headless true

pause
