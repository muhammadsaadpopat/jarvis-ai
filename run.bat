@echo off
title J.A.R.V.I.S. Core
echo ==============================================
echo   J.A.R.V.I.S. OS Core Booting...
echo ==============================================

cd /d "%~dp0"

echo Activating Virtual Environment...
call .\venv\Scripts\activate

echo Launching Streamlit in Headless Mode...
set START_VOICE_ENGINE=true
start /b streamlit run main.py --server.port 8501 --server.headless true

echo Waiting for Streamlit server to start...
timeout /t 4 /nobreak >nul

echo Launching J.A.R.V.I.S. Widget Window...
if exist "%ProgramFiles%\Google\Chrome\Application\chrome.exe" (
    start "" "%ProgramFiles%\Google\Chrome\Application\chrome.exe" --app="http://localhost:8501/?widget=true" --window-size=400,400 --window-position=0,0
) else if exist "%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe" (
    start "" "%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe" --app="http://localhost:8501/?widget=true" --window-size=400,400 --window-position=0,0
) else if exist "%LocalAppData%\Google\Chrome\Application\chrome.exe" (
    start "" "%LocalAppData%\Google\Chrome\Application\chrome.exe" --app="http://localhost:8501/?widget=true" --window-size=400,400 --window-position=0,0
) else (
    start "" msedge --app="http://localhost:8501/?widget=true" --window-size=400,400 --window-position=0,0
)

echo Boot sequence complete. Closing console node.
exit
