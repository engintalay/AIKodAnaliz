# AIKodAnaliz - Docker Kullanım Kılavuzu

## Hızlı Başlangıç (Docker ile)

### Gereksinimler
- Docker & Docker Compose
- 4GB RAM
- 10GB Disk (LMStudio modelleri için)

### Kurulum

```bash
# 1. Docker image'ını build et
docker-compose build

# 2. Servisleri başlat
docker-compose up

# 3. Tarayıcıda aç
# http://localhost:5000

# 4. LMStudio UI'na erişin
# http://localhost:8000
```

### Servisleri Durdurmak

```bash
docker-compose down
```

### Lokal Geliştirme (Docker olmadan)

```bash
# Virtual environment oluştur
python3 -m venv venv
source venv/bin/activate

# Bağımlılıkları yükle
pip install -r requirements.txt

# Uygulamayı başlat
python backend/app.py
```

## Docker Volumes

- **database**: SQLite veritabanı dosyaları
- **uploads**: Yüklenen proje ZIP dosyaları
- **lmstudio_models**: LM Studio modelleri cache

## Network

- `aikodanaliz-net`: AIKodAnaliz ↔ LMStudio iletişimi
- Port mapping:
  - 5000: Flask web server
  - 1234: LMStudio API
  - 8000: LMStudio Web UI

## Environment Variables

```bash
# Varsayılan değerler (docker-compose.yml'de set)
FLASK_APP=backend/app.py
FLASK_ENV=development
DB_CONNECTION_TYPE=sqlite
```

## Production Deployment

Production için öneriler:
```yaml
# docker-compose.prod.yml
- FLASK_ENV: production
- LMSTUDIO_URL: https://lmstudio.example.com
- DB_CONNECTION_TYPE: postgresql  # PostgreSQL kullan
- DEBUG: "False"
- WORKERS: 4
```

---
