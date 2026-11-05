# AIKodAnaliz - Mimari Belgelendirme

> Güncellendi: Kasım 2026 (chat/RAG, doküman desteği, RBAC, audit, export/import ve masaüstü istemcisi eklendi).

## Sistem Genel Yapısı

```
┌───────────────────────────┐   ┌────────────────────────────┐
│  Web UI (frontend/)       │   │ Desktop App (desktop_app/) │
│  HTML+CSS+vanilla JS      │   │ PyQt6 istemcisi            │
│  Cytoscape.js grafikler   │   │ SSE sohbet, çoklu proje    │
└────────────┬──────────────┘   └──────────────┬─────────────┘
             │ HTTP/REST + SSE                  │ HTTP/REST + SSE
             ▼                                  ▼
┌─────────────────────────────────────────────────────────────┐
│                Backend (Flask, backend/)                     │
│  11 Blueprint + çekirdek servisler                           │
│  ├── Proje yönetimi (upload/git/add-file)                    │
│  ├── Kod analizi (Tree-sitter AST + sqlparse)                │
│  ├── AI entegrasyonu (OpenAI-uyumlu lokal sunucu)            │
│  ├── RAG (FTS5 + embedding hibrit arama)                     │
│  ├── Sohbet (SSE stream, context builder)                    │
│  ├── RBAC (roller + proje izinleri) ve audit log             │
│  ├── Export/Import (.aikodanaliz ZIP)                        │
│  └── Ayarlar (global ai_settings + kullanıcı override)       │
└────────────┬───────────────────────────┬────────────────────┘
             ▼                           ▼
┌───────────────────────────┐   ┌─────────────────────────────┐
│ SQLite (WAL)              │   │ OpenAI-uyumlu AI Provider   │
│ database/aikodanaliz.db   │   │ LMStudio veya llama.cpp     │
│ + FTS5 sanal tablolar     │   │ /v1/chat/completions        │
└───────────────────────────┘   │ /v1/embeddings              │
                                └─────────────────────────────┘
```

## Backend Bileşenleri

### Çekirdek modüller (backend/)

| Modül | Satır | Görev |
|---|---|---|
| `app.py` | ~122 | Flask uygulaması, blueprint kayıtları, statik sunum, health/heartbeat |
| `database.py` | ~447 | SQLite şeması (15 tablo + 2 FTS5), migration'lar, demo kullanıcı seed'i |
| `lmstudio_client.py` | ~509 | OpenAI-uyumlu chat client; kullanıcı bazlı URL override; think/reasoning temizliği; proxy bypass |
| `ai_client.py` | 14 | Provider-nötr dışa aktarım (`LocalAIClient`/`AIClient` alias'ı) |
| `rag_index.py` | ~726 | FTS5 + embedding hibrit indeks/arama (`RagIndex`) |
| `permission_manager.py` | ~305 | Rol hiyerarşisi, `check_permission` / `check_project_access` decorator'ları, izin grant/revoke |
| `progress_tracker.py` | ~161 | Bellek-içi görev ilerlemesi (UI progress + AI metrikleri) |
| `logger.py` | ~107 | Merkezi log + **audit log** yazımı (`log_audit` → `audit_logs`) |

### Analizörler (backend/analyzers/)

- **`advanced_analyzer.py` (~1037 satır) — ana analizör.** Tree-sitter **zorunlu** (regex fallback yok). Diller: Java, Python, JavaScript, TypeScript (tsx), PHP. SQL dosyaları `sqlparse` ile ayrıca işlenir (procedure/function/view/trigger + tablo bağımlılıkları; trigger = entry point). Çıktı: fonksiyonlar (`name, type, start/end_line, signature, parameters, return_type, class_name, package_name, is_entry`), entry_points, dependencies. Java'da Spring annotation'ları (`@RestController`, `@Service`, `@GetMapping`…) entry point olarak işaretlenir.
- `code_analyzer.py` (450 satır) — legacy regex tabanlı analizör (geriye uyumluluk; yeni projelerde kullanılmıyor).

### Route blueprint'leri (backend/routes/) — 11 adet

| Blueprint | Prefix | Satır | Sorumluluk |
|---|---|---|---|
| `project.py` | `/api/projects` | ~979 | Listeleme/upload/update/delete, **add-file** (zip/war/java/sql/doküman), git-info, import-git, progress |
| `analysis.py` | `/api/analysis` | ~2047 | Ağaç analizi, recursive AI özeti, bulk özet, hata yönetimi, global AI istatistikleri, görev iptali |
| `user.py` | `/api/users` | ~548 | Login/logout/session, marks, kullanıcı yönetimi, kişisel ayarlar, proje izinleri |
| `ai_settings.py` | `/api/ai-settings` | ~86 | Global AI ayarları + bağlantı testi |
| `diagram.py` | `/api/diagram` | ~190 | Cytoscape node/edge üretimi, callgraph, PNG export |
| `report.py` | `/api/report` | ~224 | AI özet kapsama raporu (dosya/fonksiyon bazlı, token tahmini) |
| `admin_audit.py` | `/api/admin` | ~88 | Audit log sorgulama (admin) |
| `chat.py` | `/api/chat` | ~406 | RAG destekli sohbet, SSE stream, kaynak (refs) üretimi |
| `rag.py` | `/api/rag` | ~157 | İndeks build/status, birleşik arama, admin rebuild-all |
| `project_files.py` | `/api/projects` | ~623 | Doküman chunk/embedding hattı, docs listele, rebuild-rag, dosya sunumu |
| `export_import.py` | `/api/projects` | ~514 | `.aikodanaliz` export/import |

> Tam endpoint dökümü: [API.md](API.md)

## Veri Modeli (SQLite, 15 tablo + 2 FTS5)

```
users ──┬── projects (name UNIQUE, admin_id)
        │        ├── source_files (content, language, added_files/** yolu)
        │        │      └── functions (class_name, package_name, ai_summary, updated_at)
        │        │             ├── function_calls (caller→callee)
        │        │             ├── entry_points
        │        │             └── function_embeddings (vektör JSON, PK=function_id)
        │        ├── user_marks, version_history
        │        ├── project_documents (extracted_text)
        │        │      └── doc_chunks (chunk_index, embedding, page_start/end)
        │        └── fts_functions / fts_documents (FTS5 sanal tabloları)
        ├── project_permissions (UNIQUE(project_id,user_id), read_only)
        ├── user_settings (theme, ai_api_url + ai_api_key override, preferences)
        ├── ai_settings (provider, api_url, api_key, temperature, top_p, max_tokens, timeout, embedding_model/api_url/api_key)
        └── audit_logs (action, resource, ip, created_at)
```

Önemli kural ve davranışlar:

- **WAL modu + foreign keys (ON DELETE CASCADE)** — proje silmede cascade temizlik.
- `functions.updated_at` migration ile eklendi; RAG incremental indeks bundan yararlanır.
- Eski DB'ler için `ALTER TABLE` migration'ları `database.py` içinde otomatik koşar.
- Embedding'ler `TEXT` (JSON dizi) olarak saklanır; vektör matematiği saf Python (numpy yok).

## Ana Veri Akışları

### 1. Proje yükleme → analiz
```
ZIP/WAR/Git URL → kaydet (uploads/project_<id>/) → source_files
→ Tree-sitter analizi (fonksiyonlar, entry point'ler, function_calls)
→ progress_tracker ile UI'a canlı ilerleme
→ (opsiyonel) bulk-ai-summary: bağımlılıkları özyinelemeli özetle → ai_summary
→ RAG build: FTS5 + embedding (yalnız özetli fonksiyonlar)
```

### 2. AI özeti (recursive)
```
Hedef fonksiyon → özetlenmemiş callee'ler derinlemesine özetlenir
→ prompt = kod + bağımlılık özetleri (CONTEXT_LIMIT_TOKENS)
→ OpenAI-uyumlu /v1/chat/completions (Türkçe sistem promptu)
→ think/reasoning temizliği → ai_summary + updated_at → audit
```

### 3. Sohbet (RAG)
```
Soru → RagIndex.search (0.6*embedding + 0.4*BM25, LIKE fallback)
     → doc_chunks semantik arama (skor > 0.30) + kullanıcı seçimi
→ context_block + Türkçe system prompt → SSE token stream
→ event:refs (fonksiyon/doküman kaynak linkleri, sayfa/satır konumları)
```
Ayrıntı: [RAG_AND_CHAT.md](RAG_AND_CHAT.md)

### 4. Export / Import
```
Export: metadata + functions + source_files + calls + embeddings + doc_chunks + files/**
        → <ad>_<ts>.aikodanaliz (ZIP)
Import: yeni proje (id yeniden eşlenir) → RAG FTS build kullanıcı tarafından tetiklenir
```
Ayrıntı: [EXPORT_IMPORT.md](EXPORT_IMPORT.md)

## Güvenlik ve Yetkilendirme

- **Roller:** `admin (100) > developer (50) > analyzer (10)` — `permission_manager.py`.
  Denetim `ROLE_PERMISSIONS` yetki anahtarları + proje bazlı `project_permissions` tablosu ile; sayısal hiyerarşi yalnız gösterim amaçlıdır.
  - admin: her şeye tam erişim; developer: kendi + kendisine tam yetkiyle paylaşılan projeler; **analyzer daima salt okuma** (izin kaydındaki `read_only=0` bile yazma vermez).
- **Session:** Flask cookie (7 gün, HttpOnly). JWT yok (todo).
- **Audit:** login/logout, proje görüntüleme/güncelleme/silme, dosya ekleme, chat mesajı, export/import, özet üretimi → `audit_logs` (GELIS6).
- **Bilinen riskler (dokümante edildi, API.md §son):** parolalar düz metin; `/api/analysis/*`, `/api/report`, `git-info`, `progress` uçları auth istemez; production'da reverse-proxy ile korunmalı.

## Performans Özellikleri

- Cytoscape diyagramında node limiti 30 + edge'ler yalnız mevcut node'lara (orphan edge hatası düzeltmesi).
- Accordion'larda bağımlılıklar lazy-render (browser memory 1.2GB → ~300MB).
- FTS5 araması O(log n) başlangıç; embedding kosinüsü saf Python — proje başına vektör sayısı fonksiyon sayısıyla sınırlı.
- Embedding yetenek tespiti cache'i (300 sn / 180 sn) ile ölü embedding sunucusu her istekte denenmez.
- Git clone `--depth 1` (5 dk timeout), AI timeout yapılandırılabilir (vars. 900 sn).
- Progress durumu bellek içidir (tek süreç); restart'ta açık görevler "expired" işaretlenir.

## Desteklenen Diller

| Dil | Parser | Entry point tespiti | Durum |
|---|---|---|---|
| Java | Tree-sitter | Spring annotation + main | ✅ |
| Python | Tree-sitter | main/run | ✅ |
| JavaScript / TypeScript | Tree-sitter | export/main | ✅ |
| PHP | Tree-sitter | - | ✅ |
| SQL | sqlparse | trigger = entry point | ✅ |
| HTML/XML/JSON/yml/config | dosya olarak listelenir, fonksiyon analizi yapılmaz | - | ⚠️ |
| Go/Rust/C/C++ | config SUPPORTED_LANGUAGES'ta listeli, grammar paketi yoksa atlanır | - | ⚠️ |

## Stack Özeti

| Katman | Teknoloji |
|---|---|
| Web UI | HTML5/CSS3/vanilla ES6 + Cytoscape.js |
| Masaüstü | PyQt6 (requests + SSE) |
| Backend | Flask 3.0, Werkzeug, Flask-CORS |
| Analiz | tree-sitter (java/js/ts/python/php), sqlparse |
| RAG | SQLite FTS5 + OpenAI-uyumlu /v1/embeddings (nomic-embed-text-v1.5) |
| AI | LMStudio / llama.cpp (OpenAI-compatible, lokal) |
| Veri | SQLite (WAL) |
| Test | unittest + coverage (tests/unit) |

## Mimari Notlar ve Bilinen Borç

1. `add-file` iki blueprint'te tanımlı; Flask ilk kaydı kullanır (etkin olan `project.py`).
2. `analysis.py` blueprint'inde yetki decorator'ı yok — RBAC genişletme adayı.
3. Progress/görev iptali bellek içi ve kozmetik; worker thread'i gerçekten durdurmuyor (cooperative cancellation todo).
4. `report.py → analysis.py` private import'u var (dairesel bağımlılığa dikkat).
5. PostgreSQL yalnız config'de yer tutucu.
6. `todo.md`'deki açık maddeler: GELIS9 (DALMap XML desteği), GELIS10 (güvenlik taraması).

---
**İlgili dokümanlar:** [README.md](README.md) · [API.md](API.md) · [RAG_AND_CHAT.md](RAG_AND_CHAT.md) · [CONFIGURATION.md](CONFIGURATION.md) · [EXPORT_IMPORT.md](EXPORT_IMPORT.md) · [DESKTOP_APP.md](DESKTOP_APP.md) · [ROLES_AND_PERMISSIONS.md](ROLES_AND_PERMISSIONS.md) · [DOCKER.md](DOCKER.md)
