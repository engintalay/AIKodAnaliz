# AIKodAnaliz - Yapılandırma Rehberi

Tüm yapılandırma **proje kökündeki `.env`** dosyasından okunur (`python-dotenv`). Şablon: [`.env.example`](.env.example) → `cp .env.example .env`.
`.env` yoksa her değişken kod varsayılanıyla çalışır. Tek gerçek kaynak modül: `config/config.py`.

## 1. Değişken Tablosu

### Uygulama (Flask)

| Değişken | Varsayılan | Açıklama |
|---|---|---|
| `FLASK_HOST` | `0.0.0.0` | Bind adresi |
| `FLASK_PORT` | `5000` | Port (`start.sh` bu portu temizleyerek başlar) |
| `FLASK_DEBUG` | `true` | Production'da `false` yapın |
| `SECRET_KEY` | `dev-secret-key-change-in-production` | **Session imzası — production'da mutlaka değiştirin** |

### Yerel AI Provider (LMStudio / llama.cpp / any OpenAI-compatible)

| Değişken | Varsayılan | Açıklama |
|---|---|---|
| `AI_PROVIDER` | `lmstudio` | `lmstudio` veya `llamacpp` |
| `LMSTUDIO_HOST` / `LMSTUDIO_PORT` | `localhost` / `1234` | `LMSTUDIO_API_URL` türetilirken kullanılır |
| `LMSTUDIO_API_URL` | `http://{host}:{port}/v1` | OpenAI-uyumlu kök URL |
| `LMSTUDIO_DEFAULT_MODEL` | `local-model` | Model adı (çoğu yerel sunucuda zorunlu değil) |
| `LMSTUDIO_MAX_TOKENS` | `1000` | Yanıt token limiti (`.env.example` 5000 önerir) |
| `LMSTUDIO_TEMPERATURE` | `0.7` | Özet tutarlılığı için ~0.2–0.4 önerilir |
| `LMSTUDIO_TOP_P` | `0.9` | |
| `LMSTUDIO_REQUEST_TIMEOUT` | `900` | Saniye. Uzun özet/chat istekleri için geniş |
| `AI_API_KEY` | *(boş)* | OpenAI-compatible sunucu API anahtarı. Doluysa tüm AI isteklerine `Authorization: Bearer <key>` eklenir |

### Embedding (RAG) — sohbetten bağımsızlandırılabilir (GELIS23)

| Değişken | Varsayılan | Açıklama |
|---|---|---|
| `EMBEDDING_MODEL` | `text-embedding-nomic-embed-text-v1.5` | Embedding model adı. Değişirse bir sonraki build'de eski model vektörleri otomatik yeniden üretilir (incremental) |
| `EMBEDDING_API_URL` | *(boş)* | Boş = sohbet `api_url`'i kullanılır. Dolu = embedding ayrı sunucuya gider |
| `EMBEDDING_API_KEY` | *(boş)* | Boşsa: embedding sohbetle AYNI sunucudaysa sohbet anahtarı kullanılır; ayrı URL verildiyse sohbet anahtarı o sunucuya gönderilmez, bu değişken gerekir |

> ⚠️ **Öncelik sırası (chat):** `ai_settings` tablosundaki değerler (UI'daki **Ayarlar** ekranı) env varsayılanlarını **ezer**. Kullanıcı `ai_api_url` ile kendi sunucusuna yönlenmişse yalnız kendi `ai_api_key`'i kullanılır — global anahtar kullanıcının sunucusuna asla gönderilmez.
> **Öncelik sırası (embedding):** UI'dan kaydedilen `embedding_*` ayarları > env değerleri > kod default'u.
> Not: Bazı dağıtımlarda `ai_settings` tablosuna tohumlanan `timeout` değeri env'den kısaysa o değeri kullanır — timeout sorunlarında önce UI ayarlarına bakın.

### Veritabanı

| Değişken | Varsayılan | Açıklama |
|---|---|---|
| `DB_CONNECTION_TYPE` | `sqlite` | Şimdilik yalnız SQLite kullanılır |
| `DB_HOST` / `DB_PORT` / `DB_NAME` / `DB_USER` / `DB_PASSWORD` | `localhost` / `5432` / `aikodanaliz` / `admin` / *(boş)* | **Yer tutucu** — PostgreSQL desteği henüz uygulanmadı (todo). SQLite dosyası: `database/aikodanaliz.db` (otomatik oluşur, WAL modu) |

### Limitler

| Değişken | Varsayılan | Açıklama |
|---|---|---|
| `MAX_PROJECT_SIZE_MB` | `100` | ZIP/WAR yükleme üst sınırı |
| `CONTEXT_LIMIT_TOKENS` | `4000` | AI prompt'una giren maks. bağlam |

### Yönetici / Demo Hesaplar

| Değişken | Varsayılan |
|---|---|
| `ADMIN_USERNAME` | `admin` |
| `ADMIN_PASSWORD` | `admin123` |

> ⚠️ **Bilinen tutarsızlık:** `ADMIN_USERNAME/ADMIN_PASSWORD` config'de tanımlıdır ancak ilk kurulumda kullanıcıları **tohumlayan kod `backend/database.py` içinde sabittir** ve env'i okumaz:
> `admin/admin123`, `developer/dev123`, `analyzer/analyzer123`.
> İlk açılıştan sonra parolaları **Parola Değiştir** ekranından değiştirin; parolalar mevcut sürümde **düz metin** saklanır (production'da hash önerilir — todo).

### Masaüstü uygulaması için ek anahtarlar

`desktop_app` yalnız `FLASK_HOST` + `FLASK_PORT`'u backend adresi olarak kullanır; login ekranındaki "Sunucu Adresi" alanı her zaman override eder. Bkz. [DESKTOP_APP.md](DESKTOP_APP.md).

## 2. Başlangıç Scriptleri

| Script | Ne yapar |
|---|---|
| `start.sh` (Linux/macOS) | Opsiyonel `--pull/-p` git güncellemesi → venv → `.env` export → `pip install` → portu temizle → backend'i `FLASK_HOST:FLASK_PORT` üzerinde başlat |
| `start.bat` (Windows) | Aynı akış + `py/python/python3` tespiti; ayrıca **HTTP(S)_PROXY değişkenlerini sıfırlar** (`NO_PROXY=*`) — proxy arkasında LMStudio'ya erişememe sorununun çözümü budur |
| `start_desktop.sh` | Backend'i başlatmaz; masaüstü istemcisini açar (`--pull` destekli) |
| `start_desktop.bat` / `.cmd` | Windows masaüstü başlatıcı (`.env` okuma / `--pull` yok) |

## 3. AI Provider Kurulumu

1. **LMStudio:** Modeli yükleyip Developer sekmesinden local server'ı başlatın (`http://localhost:1234`). Embedding için `nomic-embed-text-v1.5` modelini de indirin (opsiyonel ama önerilir).
2. **llama.cpp:** `llama-server` OpenAI-uyumlu modda (`-em` bayrağı ile embedding desteği).
3. AIKodAnaliz'de **Ayarlar → Bağlantı Testi** ile doğrulayın.
4. Embedding modeli yoksa sistem otomatik leksik aramaya düşer — sohbet/RAG yine çalışır (bkz. [RAG_AND_CHAT.md](RAG_AND_CHAT.md)).

## 4. Production Kontrol Listesi

- [ ] `SECRET_KEY` güçlü ve benzersiz
- [ ] `FLASK_DEBUG=false`
- [ ] Demo hesap parolaları değiştirildi
- [ ] Uygulama reverse-proxy (HTTPS) arkasında; auth istemeyen uçlar (`/api/analysis/*`, `/api/report`, `/api/ai-settings/*`, `/api/users/marks*`) dışa kapatılmalı (bkz. [API.md](API.md) "Bilinen Davranışlar")
- [ ] `venv/bin/python -m unittest discover -s tests/unit -p "test_*.py"` geçiyor
- [ ] Gerekirse PostgreSQL/geçiş planı için `todo.md`'ye bakın
