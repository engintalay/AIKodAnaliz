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
| `AI_PROVIDER` | `lmstudio` | `lmstudio`, `llamacpp`, `vllm` veya `openai` |
| `LMSTUDIO_HOST` / `LMSTUDIO_PORT` | `localhost` / `1234` | `LMSTUDIO_API_URL` türetilirken kullanılır |
| `LMSTUDIO_API_URL` | `http://{host}:{port}/v1` | OpenAI-uyumlu kök URL |
| `LMSTUDIO_DEFAULT_MODEL` | `local-model` | Model adı (çoğu yerel sunucuda zorunlu değil) |
| `LMSTUDIO_MAX_TOKENS` | `1000` | Yanıt token limiti (`.env.example` 5000 önerir) |
| `LMSTUDIO_TEMPERATURE` | `0.7` | Özet tutarlılığı için ~0.2–0.4 önerilir |
| `LMSTUDIO_TOP_P` | `0.9` | |
| `LMSTUDIO_REQUEST_TIMEOUT` | `900` | Saniye. Uzun özet/chat istekleri için geniş |
| `AI_SUMMARY_WORKERS` | `3` | Toplu özetlemede paralel thread sayısı (min 1) |
| `AI_SUMMARY_MAX_TOKENS` | `2048` | Özet yanıtı için token limiti (min 256); `ai_settings.summary_max_tokens` ile ezilebilir |
| `AI_API_KEY` | *(boş)* | OpenAI-compatible sunucu API anahtarı. Doluysa tüm AI isteklerine `Authorization: Bearer <key>` eklenir |

### Embedding (RAG) — sohbetten bağımsızlandırılabilir (GELIS23)

| Değişken | Varsayılan | Açıklama |
|---|---|---|
| `EMBEDDING_MODEL` | `text-embedding-nomic-embed-text-v1.5` | Embedding model adı. Değişirse bir sonraki build'de eski model vektörleri otomatik yeniden üretilir (incremental) |
| `EMBEDDING_API_URL` | *(boş)* | Boş = sohbet `api_url`'i kullanılır. Dolu = embedding ayrı sunucuya gider |
| `EMBEDDING_API_KEY` | *(boş)* | Boşsa: embedding sohbetle AYNI sunucudaysa sohbet anahtarı kullanılır; ayrı URL verildiyse sohbet anahtarı o sunucuya gönderilmez, bu değişken gerekir |

### Model seçimi ve meta veri (GELIS24)

| Ayar | Yer | Açıklama |
|---|---|---|
| `model_name` | `ai_settings` (global) | Varsayılan sohbet modeli. Yeni ve mevcut DB'lere `LMSTUDIO_DEFAULT_MODEL` ile tohumlanır |
| `context_limit` | `ai_settings` (global) | Prompt'a giren maks. bağlam. Yeni ve mevcut DB'lere `CONTEXT_LIMIT_TOKENS` ile tohumlanır |
| `ai_model` | `user_settings` (kullanıcı bazlı) | Kullanıcının seçtiği model. Boş/NULL ise global `model_name` kullanılır |
| `summary_max_tokens` | `ai_settings` (global) | AI özet yanıtı için token limiti. Yeni ve mevcut DB'lere `AI_SUMMARY_MAX_TOKENS` ile tohumlanır |

Etkin model: **`user_settings.ai_model` > `ai_settings.model_name` > `LMSTUDIO_DEFAULT_MODEL`**.

Model listesi ve meta verisi `GET/POST /api/ai-settings/models` ile alınır. Kaynaklar sırayla denenir ve birleştirilir:

- OpenAI-uyumlu `/v1/models` → model kimlikleri
- LM Studio `/api/v0/models` → `max_context_length`, `state`, `quantization`, `publisher`, `arch`
- llama.cpp `/props` → `default_generation_settings` (`n_ctx`, `n_predict`, `temperature`, `top_p`, `top_k`, `repeat_penalty`)

`provider` değeri `lmstudio`, `llamacpp`, `vllm` veya `openai` olabilir. `vllm`/`openai` seçiliyse yalnız `/v1/models` kullanılır (LM Studio ve llama.cpp uç noktaları yoktur); `lmstudio`/`llamacpp` seçiliyse iki yerel zenginleştirme de denenir.

Normalize edilmiş alanlar: `id`, `context_length`, `max_output_tokens`, `suggested_max_tokens`, `state`, `type`, `quantization`, `publisher`, `arch`, `defaults`. `context_length` için vLLM'in `max_input_tokens` alanı da kabul edilir. `suggested_max_tokens`, sağlayıcı çıktı limiti biliniyorsa o değer, değilse `min(context_length, 4096)` olur. UI bu değeri `max_tokens` alanının üst sınırı olarak uygular.

Ayarlar ekranındaki **Model** alanı bir dropdown'dır: "Modelleri Yükle" listeyi doldurur, kayıtlı model listede yoksa `(kayıtlı)` seçeneği olarak korunur. Kaydetme akışı, model seçiliyse `POST /api/ai-settings/generation/test` ile gerçek bir yanıt testi de çalıştırır; bu test uyarı niteliğindedir ve başarısız olsa da seçim kaydedilir. Global `model_name` yalnızca admin tarafından kaydedilir.

> ⚠️ **Öncelik sırası (chat):** `ai_settings` tablosundaki değerler (UI'daki **Ayarlar** ekranı) env varsayılanlarını **ezer**. Kullanıcı `ai_api_url` ile kendi sunucusuna yönlenmişse yalnız kendi `ai_api_key`'i kullanılır — global anahtar kullanıcının sunucusuna asla gönderilmez.
> **Öncelik sırası (embedding):** UI'dan kaydedilen `embedding_*` ayarları > env değerleri > kod default'u.
> **Öncelik sırası (model):** `user_settings.ai_model` > `ai_settings.model_name` > `LMSTUDIO_DEFAULT_MODEL`.
> Not: Bazı dağıtımlarda `ai_settings` tablosuna tohumlanan `timeout` değeri env'den kısaysa o değeri kullanır — timeout sorunlarında önce UI ayarlarına bakın.

### Rate limit ve hata ayrıntısı (GELIS25)

| Değişken | Varsayılan | Açıklama |
|---|---|---|
| `LLM_RATE_LIMIT_COOLDOWN` | `60` | 429/kota hatasında sunucu süre bildirmezse bu kadar saniye beklenir |
| `LLM_RATE_LIMIT_MAX_WAIT` | `120` | Sonraki istek en fazla bu kadar saniye bekletilir; daha uzun beklemede istek gönderilmez, kalan süre kullanıcıya bildirilir |

- Hata gövdesi OpenAI (`error.message`), vLLM/FastAPI (`detail`), LiteLLM (`error`) ve düz metin biçimlerinden ayrıştırılır; kullanıcıya `HTTP <kod>` yerine okunabilir ayrıntı gösterilir.
- Bekleme süresi önce `Retry-After` başlığından (saniye veya HTTP-date), yoksa gövdedeki `try again in 20s`, `retry after 30`, `"retry_after": 20` gibi ipuçlarından okunur.
- 429 her zaman rate-limit sayılır; 500 asla sayılmaz; diğer kodlarda yalnız gövde `rate limit`, `quota exceeded`, `too many requests` gibi ifadeler içeriyorsa sayılır.
- Bekleme kaydı süreç genelinde ve thread-safe'dir; anahtar sunucu URL'sidir. Aynı sunucuya giden tüm kullanıcılar beklemesi paylaşır.
- Chat akışında bekleme `event:status`, ayrıntılı hata `event:error` (`{error, retry_after_seconds}`) olarak gönderilir; ayarlar ekranındaki model/bağlantı/yanıt testleri de `retry_after_seconds` bilgisini gösterir.

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

> ✅ **DZT-12:** İlk kurulumda admin kullanıcısı `ADMIN_USERNAME` / `ADMIN_PASSWORD` env değerleriyle oluşturulur. Demo kullanıcılar (`developer/dev123`, `analyzer/analyzer123`) yalnızca admin yoksa tohumlanır. Tüm parolalar Werkzeug `scrypt` ile hash'lenir; eski düz metin kayıtlar açılışta otomatik hash'e çevrilir. İlk girişten sonra **Parola Değiştir** ekranından değiştirmeniz önerilir.

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
