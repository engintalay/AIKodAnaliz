FROM python:3.11-slim

WORKDIR /app

# Bağımlılıkları yükle
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Uygulama dosyalarını kopyala
COPY . .

# Port açılışı
EXPOSE 5000

# Veritabanı ve uploads klasörlerini oluştur
RUN mkdir -p database uploads

# Flask uygulamasını başlat
CMD ["python", "backend/app.py"]
