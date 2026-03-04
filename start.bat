@echo off
setlocal EnableDelayedExpansion

REM AIKodAnaliz Windows startup script

echo [INFO] Starting AIKodAnaliz...

REM Move to script directory
cd /d "%~dp0"

REM Find Python executable
set "PYTHON_CMD="
echo [INFO] Searching for Python...

REM Try py launcher first
where py >nul 2>nul
if %ERRORLEVEL%==0 (
    echo [INFO] Found py launcher
    set "PYTHON_CMD=py -3"
    goto :python_found
)

REM Try python with full path check (Windows Store Python)
python --version >nul 2>nul
if %ERRORLEVEL%==0 (
    echo [INFO] Found python command
    set "PYTHON_CMD=python"
    goto :python_found
)

REM Try python3
python3 --version >nul 2>nul
if %ERRORLEVEL%==0 (
    echo [INFO] Found python3 command
    set "PYTHON_CMD=python3"
    goto :python_found
)

REM Python not found
echo [ERROR] Python not found!
echo [ERROR] Please install Python 3.8+ from https://www.python.org/downloads/
echo [ERROR] Make sure to check "Add Python to PATH" during installation
pause
exit /b 1

:python_found
echo [INFO] Using: %PYTHON_CMD%
%PYTHON_CMD% --version

REM Create virtual environment if missing
if not exist "venv\Scripts\activate.bat" (
    echo [INFO] Creating virtual environment...
    %PYTHON_CMD% -m venv venv
    if %ERRORLEVEL% neq 0 (
        echo [ERROR] Failed to create virtual environment.
        pause
        exit /b 1
    )
)

REM Activate virtual environment
call "venv\Scripts\activate.bat"
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Failed to activate virtual environment.
    pause
    exit /b 1
)

REM Install dependencies
echo [INFO] Installing dependencies...
pip install -r requirements.txt
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Dependency installation failed.
    pause
    exit /b 1
)

REM Kill process using port 5000 (if any)
echo [INFO] Checking port 5000...
for /f "tokens=5" %%P in ('netstat -ano ^| findstr ":5000" ^| findstr "LISTENING"') do (
    echo [INFO] Killing process %%P on port 5000...
    taskkill /PID %%P /F >nul 2>nul
)

REM Start backend server
echo [INFO] Starting server...
echo [INFO] Open in browser: http://localhost:5000
echo [INFO] Make sure LMStudio is running at http://localhost:1234

title AIKodAnaliz Backend
cd backend
python app.py

endlocal
