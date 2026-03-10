#!/bin/bash

# AIKodAnaliz Başlangıç Scripti

echo "🚀 AIKodAnaliz başlatılıyor..."

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
