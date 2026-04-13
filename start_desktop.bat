@echo off
setlocal

REM Launch the AIKodAnaliz Desktop App (Windows)
cd /d "%~dp0"

REM Activate virtual environment if available
if exist "venv\Scripts\activate.bat" (
    call "venv\Scripts\activate.bat"
)

REM Run the desktop app
python -m desktop_app %*
