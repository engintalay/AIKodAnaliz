@echo off
setlocal

REM Launch the AIKodAnaliz Desktop App (Windows)
cd /d "%~dp0"

REM Create virtual environment if missing
if not exist "venv\Scripts\activate.bat" (
    where py >nul 2>nul
    if %ERRORLEVEL%==0 (
        py -3 -m venv venv
    ) else (
        python -m venv venv
    )
)

REM Activate virtual environment
call "venv\Scripts\activate.bat"

REM Install/update requirements
python -m pip install --disable-pip-version-check -r requirements.txt
if %ERRORLEVEL% neq 0 (
    echo [ERROR] requirements kurulumu basarisiz.
    exit /b 1
)

REM Run the desktop app
python -m desktop_app %*
