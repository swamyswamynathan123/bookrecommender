@echo off
setlocal
cd /d "%~dp0"

where uv >nul 2>nul
if errorlevel 1 (
    echo uv is not installed. Install it from https://docs.astral.sh/uv/ and run start.bat again.
    pause
    exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
    echo Creating the Python environment...
    uv venv || goto :failed
    uv pip install -r requirements.txt || goto :failed
)

if not exist ".env" (
    copy ".env.example" ".env" >nul
    echo Created .env from .env.example.
    echo Fill in your API keys in .env, then run start.bat again.
    pause
    exit /b 0
)

".venv\Scripts\streamlit.exe" run app.py
if errorlevel 1 goto :failed
exit /b 0

:failed
echo.
echo Something went wrong - see the messages above.
pause
exit /b 1
