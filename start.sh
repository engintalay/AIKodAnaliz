#!/bin/bash

# AIKodAnaliz Başlangıç Scripti

# Parse arguments
PULL_UPDATES=false
for arg in "$@"; do
    case $arg in
        --pull|-p)
            PULL_UPDATES=true
            ;;
    esac
done

echo "🚀 AIKodAnaliz başlatılıyor..."

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

# Python virtual environment kontrol
if [ ! -d "venv" ]; then
    echo "📦 Virtual environment oluşturuluyor..."
    python3 -m venv venv
fi

# Virtual environment etkinleştir
source venv/bin/activate

# .env dosyası varsa oku
if [ -f ".env" ]; then
    source <(grep -v '^#' .env | grep -v '^\s*$' | sed 's/^/export /')
fi

# Bağımlılıkları yükle
echo "📥 Bağımlılıklar yükleniyor..."
pip install -r requirements.txt --quiet

# Kullanılacak port
PORT=${FLASK_PORT:-5000}
HOST=${FLASK_HOST:-0.0.0.0}

# Flask uygulamasını başlat
echo "🧹 ${PORT} portu kontrol ediliyor..."
fuser -k ${PORT}/tcp 2>/dev/null || true

echo "✅ Sunucu başlatılıyor: http://${HOST}:${PORT}"
echo "⚠️  LMStudio'nun çalıştığından emin olun: http://${LMSTUDIO_HOST:-localhost}:${LMSTUDIO_PORT:-1234}"
echo ""

cd backend
python app.py
