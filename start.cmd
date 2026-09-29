@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\pythonw.exe" (
    python -m venv .venv
    if errorlevel 1 (
        echo Python environment creation failed. Install Python 3.12 and retry.
        pause
        exit /b 1
    )
)
".venv\Scripts\python.exe" -c "import wmi, pythoncom" >nul 2>&1
if errorlevel 1 (
    ".venv\Scripts\python.exe" -m pip install -r requirements.txt
    if errorlevel 1 (
        echo Dependency installation failed. Check network and retry.
        pause
        exit /b 1
    )
)
start "" ".venv\Scripts\pythonw.exe" "%~dp0screen_dim.py"
