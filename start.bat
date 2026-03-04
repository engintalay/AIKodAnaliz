@echo off
setlocal EnableDelayedExpansion

REM AIKodAnaliz Windows startup script

echo [INFO] Starting AIKodAnaliz...

REM Move to script directory
cd /d "%~dp0"

REM Find Python executable
set "PYTHON_CMD="
where py >nul 2>nul
if %ERRORLEVEL%==0 (
    set "PYTHON_CMD=py -3"
) else (
    where python >nul 2>nul
    if %ERRORLEVEL%==0 (
        set "PYTHON_CMD=python"
    )
)

if "%PYTHON_CMD%"=="" (
    echo [ERROR] Python not found. Install Python 3 and add it to PATH.
    pause
    exit /b 1
)

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

REM Disable proxy environment variables
echo [INFO] Disabling proxy settings...
set HTTP_PROXY=
set HTTPS_PROXY=
set ALL_PROXY=
set http_proxy=
set https_proxy=
set all_proxy=
set NO_PROXY=*
set no_proxy=*

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
