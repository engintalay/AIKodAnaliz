#!/usr/bin/env bash
# Launch the AIKodAnaliz Desktop App
cd "$(dirname "$0")"

# Activate virtual environment if available
if [ -f "venv/bin/activate" ]; then
    source venv/bin/activate
fi

# Run the desktop app
python -m desktop_app "$@"
