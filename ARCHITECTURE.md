# AIKodAnaliz - Mimari Belgelendirme

## Sistem Genel Yapısı

```
┌─────────────────────────────────────────────────────────────┐
│                        Frontend (Web UI)                     │
│  HTML + CSS + JavaScript + Cytoscape.js (Interactive Graph)│
└────────────────────┬────────────────────────────────────────┘
                     │
                     ↓ HTTP/REST APIs
┌─────────────────────────────────────────────────────────────┐
│                   Backend (Flask Server)                     │
│  ├── Project Management (upload, delete, list)             │
│  ├── Code Analysis (detect functions, entry points)        │
│  ├── AI Integration (LMStudio HTTP API)                   │
│  ├── User Management (multi-user with permissions)        │
│  ├── Diagram Generation (node/edge data)                 │
│  └── Settings Management (AI params, DB config)           │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ↓ SQL Queries
┌─────────────────────────────────────────────────────────────┐
│               Database (SQLite / PostgreSQL)                │
│  ├── users, projects, source_files                        │
│  ├── functions, function_calls, entry_points             │
│  ├── user_marks (comments), version_history              │
│  └── ai_settings                                          │
└──────────────────────────────────────────────────────────────┘
```

## Bileşen Detayları

### Frontend (3 dosya)
- **index.html**: Ana arayüz
  - Proje listesi
  - Proje detayı (4 tab: Diyagram, Fonksiyonlar, İşaretler, Dosyalar)
  - Upload formu
  - Ayarlar paneli
  - Modal pencereler

- **css/style.css**: 1,200+ satır
  - Responsive tasarım
  - Dark/light uyumu
  - Grid layouts
  - Animasyonlar

- **js/main.js**: 400+ satır
  - API çağırıları (fetch)
  - Cytoscape.js entegrasyonu
  - Event handling
  - DOM manipülasyonu

### Backend (5 Route Blueprints + 3 Core Module)

**Core Modules:**
1. **app.py** - Flask uygulaması
   - 50 satır
   - Static file serving
   - Blueprint kayıtları
   - Health check endpoint

2. **database.py** - SQLite ORM-like
   - 200 satır
   - Schema initialization (11 table)
   - Query, insert, update methods
   - Row factory (dict conversion)

3. **lmstudio_client.py** - AI Integration
   - 150 satır
   - HTTP requests to LMStudio API
   - Prompt engineering
   - Error handling & timeouts
   - Token management

4. **analyzers/code_analyzer.py** - Multi-lang Parser
   - 450 satır
   - Python AST parsing
   - Regex-based parsing (Java/JS/PHP)
   - Entry point detection
   - Signature extraction
   - Parameter/return type analysis

**Route Blueprints:**
1. **routes/project.py** - 150 satır
   - `GET /api/projects` - List all
   - `GET /api/projects/<id>` - Get details
   - `POST /api/projects/upload` - ZIP upload & extract
   - `GET /api/projects/<id>/files` - List files
   - `DELETE /api/projects/<id>` - Delete

2. **routes/analysis.py** - 120 satır
   - `POST /api/analysis/project/<id>` - Full analysis
   - `POST /api/analysis/function/<id>/ai-summary` - AI summary
   - `GET /api/analysis/project/<id>/functions` - List functions
   - `GET /api/analysis/dependencies/<id>` - Function graph

3. **routes/user.py** - 100 satır
   - `POST /api/users/register` - Register user
   - `POST /api/users/marks` - Add comment/mark
   - `GET /api/users/marks/<project_id>` - Get marks
   - `PUT /api/users/marks/<id>/resolve` - Resolve (admin)

4. **routes/ai_settings.py** - 80 satır
   - `GET /api/ai-settings` - Get all settings
   - `PUT /api/ai-settings/<setting>` - Update setting
   - `POST /api/ai-settings/lmstudio/test` - Connection test

5. **routes/diagram.py** - 60 satır
   - `GET /api/diagram/project/<id>` - Graph data (nodes/edges)
   - `POST /api/diagram/export/png` - PNG export

### Database Schema (11 Tables)

```sql
users
  id, username, password, role, created_at

projects
  id, name, description, upload_date, last_updated, admin_id

source_files
  id, project_id, file_path, file_name, language, content, hash, created_at

functions
  id, project_id, file_id, function_name, function_type, start_line, end_line,
  signature, parameters, return_type, description, ai_summary, created_at

function_calls
  id, project_id, caller_function_id, callee_function_id, call_type, created_at

entry_points
  id, project_id, function_id, entry_type, description, created_at

user_marks
  id, project_id, function_id, user_id, mark_type, comment, status, 
  created_at, updated_at

version_history
  id, file_id, version, content, changes_summary, created_by, created_at

ai_settings
  id, setting_name, setting_value, data_type, updated_at
```

## Veri Akışı

### Proje Yükleme
```
ZIP Dosyası
    ↓
API: /api/projects/upload
    ↓
Extract files → Database'e kaydet
    ↓
Auto-analyze (detect functions)
    ↓
Store in functions table
```

### Kod Analizi
```
Source file
    ↓
CodeAnalyzer (language-specific)
    ↓
Extract: functions, signatures, parameters, entry_points
    ↓
Store in database
    ↓
Optional: AI summary for each function
```

### Diyagram Oluşturma
```
Functions from DB
    ↓
Function calls (relationships)
    ↓
Build nodes & edges JSON
    ↓
Cytoscape.js render
    ↓
Interactive graph (zoom, pan, click)
```

### AI Analizi
```
Function code + signature
    ↓
Generate prompt
    ↓
LMStudio HTTP request
    ↓
Parse response
    ↓
Store summary in DB
```

## Desteklenen Diller

| Dil | Parser | Özet | Durum |
|-----|--------|------|-------|
| Java | Regex | ✓ | ✅ |
| Python | AST | ✓ | ✅ |
| JavaScript | Regex | ✓ | ✅ |
| TypeScript | Regex | ✓ | ✅ |
| PHP | Regex | ✓ | ✅ |
| C/C++ | Generic | ✓ | ⚠️ |
| Go | Generic | ✓ | ⚠️ |
| HTML/CSS | Basic | - | ⚠️ |

✅ = Fully supported
⚠️ = Basic support via generic parser

## Performans Özellikleri

- **Context Limit**: 4000 tokens (AI prompt'ında)
- **Max Tokens**: 1000 (AI yanıt)
- **Timeout**: 30 saniye (LMStudio API)
- **Max Project Size**: 100 MB
- **Database**: SQLite (single-file, no server needed)

## Güvenlik

### Kullanıcı Rolleri
- **Admin**: Full access (create, read, update, delete, approve marks)
- **Viewer**: Read-only (view analysis, add marks/comments)

### Data Validation
- ZIP file extension check
- SQL injection protection (parameterized queries)
- File path traversal prevention
- API input validation

## Kurulum & Başlangıç

```bash
# 1. Bağımlılıkları yükle
pip install -r requirements.txt

# 2. LMStudio başlat (http://localhost:1234)
# Download: https://lmstudio.ai

# 3. Flask uygulamasını başlat
python backend/app.py

# 4. Veya başlangıç scripti kullan
./start.sh

# 5. Tarayıcıda aç
# http://localhost:5000
```

## Test Komutları

```bash
# Kod analiz testleri
python3 run_tests.py

# API testi (curl örneği)
curl http://localhost:5000/api/projects
curl http://localhost:5000/api/health

# LMStudio bağlantı testi
curl http://localhost:1234/v1/models
```

## Geliştirilecek Özellikleri

- [ ] PostgreSQL tam desteği
- [ ] JWT authentication
- [ ] Advanced syntax highlighting (Prism.js)
- [ ] Diff view (code changes)
- [ ] Batch analysis
- [ ] Export formats (PDF, docs, JSON)
- [ ] Search indexing
- [ ] Caching layer (Redis)
- [ ] Webhook integrations

## Dosya Boyutları

```
Frontend:
  - index.html: 8 KB
  - css/style.css: 12 KB
  - js/main.js: 18 KB
  Total: 38 KB

Backend:
  - Python: 1,500 lines total
  - app.py: 50 lines
  - database.py: 200 lines
  - lmstudio_client.py: 150 lines
  - code_analyzer.py: 450 lines
  - routes: 520 lines total

Database: Initial empty: 100 KB (grows with projects)
```

## Stack Özeti

| Katman | Teknoloji | Versiyon |
|--------|-----------|----------|
| Frontend | HTML5/CSS3/JavaScript ES6 | Latest |
| UI Graph | Cytoscape.js | Latest |
| Backend | Flask | 3.0.0 |
| Database | SQLite 3 | Built-in |
| AI | LMStudio (API) | Local |
| Python | Python | 3.8+ |
| Styling | CSS Grid/Flexbox | CSS3 |
| Communication | REST API | JSONover HTTP |

---

**Versiyon**: 1.0.0
**Tarih**: Mart 2026
**Durum**: β (Beta)
