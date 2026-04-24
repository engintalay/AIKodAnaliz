#!/usr/bin/env bash
# Launch the AIKodAnaliz Desktop App
set -e

cd "$(dirname "$0")"

# Parse arguments
PULL_UPDATES=false
for arg in "$@"; do
    case $arg in
        --pull|-p)
            PULL_UPDATES=true
            ;;
    esac
done

# Git pull if requested
if [ "$PULL_UPDATES" = true ]; then
    echo "📦 Git remote kontrol ediliyor..."
    git fetch origin
    LOCAL=$(git rev-parse HEAD)
    REMOTE=$(git rev-parse origin/main)
    if [ "$LOCAL" != "$REMOTE" ]; then
        echo "🔄 Yeni versiyon bulundu! Local: $(git rev-parse --short HEAD), Remote: $(git rev-parse --short origin/main)"
        read -p "Güncelleme yapılsın mı? (E/h): " confirm
        if [ "$confirm" = "E" ] || [ "$confirm" = "e" ] || [ -z "$confirm" ]; then
            echo "📥 Güncelleme yapılıyor..."
            git pull origin main
            echo "📥 Bağımlılıklar güncelleniyor..."
            pip install -r requirements.txt --quiet
        else
            echo "⏭️  Güncelleme atlandı."
        fi
    else
        echo "✅ Versiyon güncel."
    fi
fi

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
