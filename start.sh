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

# Bağımlılıkları yükle
echo "📥 Bağımlılıklar yükleniyor..."
pip install -r requirements.txt

# Flask uygulamasını başlat
echo "✅ Sunucu başlatılıyor..."
echo "🌐 Tarayıcıda açın: http://localhost:5000"
echo "⚠️  LMStudio'nun çalıştığından emin olun (http://localhost:1234)"
echo ""

cd backend
python app.py
