#!/usr/bin/env bash
# Launch the AIKodAnaliz Desktop App
set -e

cd "$(dirname "$0")"

# Create virtual environment if missing
if [ ! -f "venv/bin/activate" ]; then
    if command -v python3 >/dev/null 2>&1; then
        python3 -m venv venv
    else
        python -m venv venv
    fi
fi

# Activate virtual environment
source venv/bin/activate

# Install/update requirements
python -m pip install --disable-pip-version-check -r requirements.txt

# Run the desktop app
python -m desktop_app "$@"
