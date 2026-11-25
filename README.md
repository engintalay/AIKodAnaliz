# AIKodAnaliz - Yapay Zeka Destekli Kod Analiz Aracı

Eski projeyi yeni teknolojiye dönüştürmek için kapsamlı dokümantasyon sağlayan web tabanlı kod analiz sistemi. Tree-sitter tabanlı hassas AST parsing ile kodunuzu derinlemesine analiz edin. AI özetleri, RAG destekli sohbet ve doküman arama ile projelerinizi doğal dilde sorgulayın.

## 📚 Belgeler

| Doküman | İçerik |
|---|---|
| [ARCHITECTURE.md](ARCHITECTURE.md) | Sistem mimarisi, modüller, veri modeli, akışlar |
| [API.md](API.md) | **Tüm REST endpoint referansı** (yetkiler dahil) |
| [RAG_AND_CHAT.md](RAG_AND_CHAT.md) | RAG indeksi, doküman arama, AI sohbet rehberi |
| [CONFIGURATION.md](CONFIGURATION.md) | `.env` değişkenleri, AI provider kurulumu, production listesi |
| [EXPORT_IMPORT.md](EXPORT_IMPORT.md) | Proje taşıma (`.aikodanaliz` dosya biçimi) |
| [DESKTOP_APP.md](DESKTOP_APP.md) | PyQt6 masaüstü uygulaması |
| [ROLES_AND_PERMISSIONS.md](ROLES_AND_PERMISSIONS.md) | Rol ve yetki sistemi (RBAC) |
| [DOCKER.md](DOCKER.md) | Docker ile kurulum |
| [todo.md](todo.md) | Yapılacaklar / gelinen nokta |

## ✨ Özellikler

### 📊 Kod Analizi
- ✅ **Çok Dil Desteği**: Java, Python, JavaScript, TypeScript, PHP (Tree-sitter AST parsing)
- ✅ **Otomatik Fonksiyon Tespiti**: Tüm fonksiyon, metod ve class tanımları
- ✅ **Qualified Name Matching**: `ClassName.methodName` ile hassas eşleştirme
- ✅ **Entry Point Tespiti**: Java `@Service`, `@Controller`, `@RestController` annotation desteği
- ✅ **Bağımlılık Analizi**: Fonksiyon çağrı grafı (3-tier resolution strategy)
- ✅ **Tekrar Analiz**: Projeleri yeniden analiz edebilme (re-analysis)

### 🤖 Yapay Zeka
- ✅ **Lokal AI Provider Desteği**: LMStudio ve llama.cpp ile OpenAI-compatible entegrasyon
- ✅ **Recursive AI Summary**: Alt fonksiyonların özetleriyle context-aware analiz
- ✅ **Otomatik Bağımlılık Özeti**: Çağrılan fonksiyonlar önce özetlenir
- ✅ **Türkçe Özet**: Tamamen Türkçe AI yanıtları (300s timeout)
- ✅ **Progress Tracking**: AI özet üretimi sırasında gerçek zamanlı ilerleme takibi
- ✅ **Multi-Level Progress**: Alt fonksiyon özetleme adımları görünür

### 🔄 Proje Yönetimi
- ✅ **ZIP Upload**: Proje dosyalarını ZIP ile yükle
- ✅ **Git Import**: GitHub/GitLab repository'lerinden direkt import
- ✅ **Git Auto-Fill**: URL girilince branch'ler ve proje ismi otomatik doldurulur
- ✅ **Progress Tracking**: Gerçek zamanlı yükleme ve analiz ilerlemesi
- ✅ **Cascade Delete**: Proje silindiğinde tüm ilişkili veriler temizlenir

### 🎨 Kullanıcı Arayüzü
- ✅ **İnteraktif Diyagram**: Cytoscape.js ile fonksiyon bağlantı grafiği
- ✅ **Lazy Loading**: Accordion açıldığında bağımlılıklar yüklenir (memory optimization)
- ✅ **Kaynak Kod Arama**: Syntax highlighting ile arama (ESC ile kapat)
- ✅ **Modal Kısayolları**: ESC ile kapat, F11 tam ekran
- ✅ **Responsive Design**: Tüm ekran boyutlarında uyumlu

### 🤖 AI Sohbet & RAG (GELIS2/4/11/15/16/20)
- ✅ **Sohbet Sekmesi**: Proje kaynak kodu + AI özetleri + dokümanlar üzerinde doğal dil soruları
- ✅ **Hibrit RAG Arama**: FTS5 BM25 + embedding kosinüs benzerliği (0.6/0.4), LIKE fallback
- ✅ **Seçili Bağlam**: Soruya fonksiyon ve doküman parçası seçerek kapsam daraltma
- ✅ **Kaynak Gösterimi**: Yanıttaki kaynaklar tıklanabilir (PDF'te ilgili sayfaya link)
- ✅ **SSE Stream**: Yanıt token token akar; `think`/reasoning artıkları temizlenir
- ✅ **RAG Ekranı**: Proje genelinde fonksiyon + doküman arama, skor/güven göstergesi

### 📄 Doküman Desteği (GELIS5/8)
- ✅ **PDF, DOCX, DOC, TXT, MD, XLSX, XLS** projeye eklenir, chunk'lanır, RAG'e girer
- ✅ **Kod/Arşiv Ekleme**: Sonradan eklenen java/sql/py/js/ts/php + zip/war/jar arşivleri analize dahil
- ✅ **Chunk Yönetimi**: Doküman başına chunk/embedding sayısı, tek tuşla RAG yeniden kurma

### 🔐 Güvenlik & Yönetim (DZT-2, GELIS6)
- ✅ **RBAC**: admin / developer / analyzer rolleri + proje bazlı izin verme-geri alma
- ✅ **Audit Log**: Login, proje, dosya, sohbet, export gibi tüm işlemlerin kaydı + admin filtre ekranı
- ✅ **Kullanıcı Yönetimi**: Admin paneli, parola değiştirme, kullanıcı bazlı AI sunucu adresi

### 📦 Taşınabilirlik (GELIS18)
- ✅ **Export/Import**: Analiz + özetler + RAG indeksi + dosyalar `.aikodanaliz` dosyasında
- ✅ Tek tıkla dışa/içe aktarma (web ve masaüstü)

### 🖥️ Masaüstü Uygulaması (GELIS17)
- ✅ **PyQt6 istemcisi**: Tüm projeler üzerinden otomatik yönlendirmeli sohbet
- ✅ Proje seçilmeden soru sorun → en ilgili proje otomatik bulunur

### 🔧 Teknik Özellikler
- ✅ **Performans**: Browser memory 1.2GB → 300MB optimizasyonu
- ✅ **Proxy-Free**: Tüm network istekleri proxy kullanmaz
- ✅ **Multi-Platform**: Linux ve Windows startup scriptleri (`start.sh`, `start.bat`)
- ✅ **SQLite WAL Mode**: Concurrent read/write desteği
- ✅ **Tree-Sitter**: Regex yerine gerçek AST parsing

## 🚀 Kurulum

### Gereksinimler
- **Python 3.8+** (Test edildi: Python 3.14.3)
- **Lokal AI Provider** - LMStudio veya llama.cpp tabanli OpenAI-compatible sunucu
- **Git** (Git repository import için - opsiyonel)
- **SQLite 3** (Python ile birlikte gelir)

### Hızlı Başlangıç

#### Linux / macOS

```bash
# Repository'yi klonla
cd /home/engin/projects/AIKodAnaliz

# Virtual environment oluştur (önerilen)
python3 -m venv venv
source venv/bin/activate

# Bağımlılıkları yükle
pip install -r requirements.txt

# Uygulamayı başlat
./start.sh
```

#### Windows

```cmd
# Virtual environment oluştur
python -m venv venv
venv\Scripts\activate

# Bağımlılıkları yükle
pip install -r requirements.txt

# Uygulamayı başlat
start.bat
```

Tarayıcıda açın: **http://localhost:5000**

#### Masaüstü Uygulaması (Opsiyonel)

Backend çalışırken masaüstü istemcisini başlatın (ayrıntılar: [DESKTOP_APP.md](DESKTOP_APP.md)):

```bash
./start_desktop.sh        # Linux/macOS
start_desktop.bat         # Windows
```

### Docker ile Kurulum

Docker kullanmayı tercih ediyorsanız, detaylı bilgi için [DOCKER.md](DOCKER.md) dosyasına bakın.

```bash
docker-compose up -d
```

### AI Provider Kurulumu

1. **Provider Seçin**: LMStudio veya llama.cpp kullanın
2. **Model Hazırlayın**: Sohbet modeli yükleyin veya başlatın
3. **OpenAI-compatible Server Başlatın**: Varsayılan örnek adres `http://localhost:1234/v1`
4. **Test Et**: AIKodAnaliz'de Ayarlar → Bağlantı Test

Örnekler:
- **LMStudio**: https://lmstudio.ai üzerinden model indirip Local Server başlatın
- **llama.cpp**: OpenAI-compatible server modunda çalıştırın ve API URL'ini ayarlara girin

**Sorun mu yaşıyorsunuz?** Proxy ayarlarınızı kontrol edin. Uygulama otomatik olarak proxy'yi bypass eder.

## 📁 Proje Yapısı

```
AIKodAnaliz/
├── backend/
│   ├── app.py                      # Flask ana uygulaması (11 blueprint)
│   ├── database.py                 # SQLite şeması (15 tablo + FTS5), migration, seed
│   ├── lmstudio_client.py          # OpenAI-compatible AI istemcisi (proxy-free)
│   ├── ai_client.py                # Provider-nötr dışa aktarım
│   ├── rag_index.py                # RAG: FTS5 + embedding hibrit arama
│   ├── permission_manager.py       # RBAC decorator'ları, proje izinleri
│   ├── progress_tracker.py         # Real-time progress tracking
│   ├── logger.py                   # Merkezi logging + audit log
│   ├── analyzers/
│   │   ├── advanced_analyzer.py    # Tree-sitter AST parser (+ sqlparse)
│   │   └── code_analyzer.py        # Legacy analyzer (deprecated)
│   └── routes/
│       ├── project.py              # Proje yönetimi (upload/import/add-file/git)
│       ├── project_files.py        # Doküman chunk/RAG hattı, docs uçları
│       ├── analysis.py             # Analiz + recursive/bulk AI özeti
│       ├── chat.py                 # RAG destekli sohbet (SSE)
│       ├── rag.py                  # İndeks build/status/arama
│       ├── user.py                 # Kullanıcı, marks, ayarlar, izinler
│       ├── ai_settings.py          # AI provider ayarları
│       ├── diagram.py              # Diyagram verileri (entry points)
│       ├── report.py               # AI özet kapsama raporu
│       ├── admin_audit.py          # Audit log sorguları (admin)
│       └── export_import.py        # .aikodanaliz export/import
├── desktop_app/                    # PyQt6 masaüstü istemcisi (python -m desktop_app)
├── frontend/
│   ├── index.html                  # Ana sayfa (modallar, arama, ESC)
│   ├── css/style.css               # Responsive tasarım
│   ├── js/
│   │   ├── main.js                 # Ana frontend mantığı (lazy-load, chat, RAG)
│   │   └── admin-functions.js      # Admin paneli (kullanıcı, audit, ayarlar)
│   └── lib/cytoscape.umd.js        # Grafik kütüphanesi
├── config/config.py                # Merkezi konfigürasyon (.env)
├── database/aikodanaliz.db         # SQLite (auto-created, WAL)
├── uploads/                        # Yüklenen projeler + documents/
├── tests/unit/                     # Unit testler (unittest + coverage)
├── start.sh / start.bat            # Backend başlatıcı (Linux / Windows)
├── start_desktop.sh / .bat / .cmd  # Masaüstü istemcisi başlatıcı
├── requirements.txt                # Python bağımlılıkları
├── .env.example                    # Yapılandırma şablonu → CONFIGURATION.md
├── docker-compose.yml, Dockerfile  # Docker → DOCKER.md
└── README.md                       # Bu dosya (+ API.md, ARCHITECTURE.md, ...)
```

## 🌐 API Endpoints

**Tam referans (tüm uçlar, parametreler, yetkiler): [API.md](API.md).** Özet gruplar:

- `/api/projects` — listele/upload/update/delete, ZIP+Git import, **add-file** (kod/arşiv/doküman), progress, **export/import**
- `/api/analysis` — analiz, recursive/bulk AI özeti, hatalı özet yönetimi, istatistikler
- `/api/chat` — RAG destekli sohbet (**SSE stream**, kaynak refs'leri ile)
- `/api/rag` — indeks build/status, birleşik fonksiyon+doküman araması
- `/api/users` — login/session, marks, kullanıcı yönetimi, ayarlar, **proje izinleri**
- `/api/ai-settings` — provider ayarları + bağlantı testi
- `/api/diagram` — diyagram/callgraph verileri, PNG export
- `/api/report` — AI özet kapsama raporu
- `/api/admin/audit-logs` — denetim kayıtları (admin)

> ⚠️ Kimlik doğrulama session cookie iledir; bazı uçlar auth gerektirmez — production notları için API.md "Bilinen Davranışlar" bölümüne bakın.

## AI Provider Ayarı

1. Ayarlar ekranında provider seçin: `LMStudio` veya `llama.cpp`
2. Bir sohbet modeli hazırlayın
3. Sunucu URL'sini girin (örnek: `http://localhost:1234/v1`)
4. Bağlantıyı test edin ve ardından **Sıcaklık**, **Top P**, **Max Tokens** vb. yapılandırın

Tüm env değişkenleri, öncelik sırası ve production kontrol listesi: [CONFIGURATION.md](CONFIGURATION.md)

## 💾 Veritabanı Şeması

**15 tablo + 2 FTS5 sanal tablosu** (ayrıntılı ER şeması: [ARCHITECTURE.md](ARCHITECTURE.md)):

- **users**: Kullanıcı hesapları (admin/developer/analyzer rolleri)
- **projects**: Projeler (upload_date, Git metadata, sahip)
- **source_files**: Kaynak kod dosyaları (language, content; `added_files/**` sonradan eklenenler)
- **functions**: Analiz edilen fonksiyonlar (qualified name bileşenleri: class_name/package_name, ai_summary, updated_at)
- **function_calls**: Fonksiyon bağlantıları (caller → callee, call_type)
- **entry_points**: Başlangıç noktaları (@Service, @Controller, main, SQL trigger)
- **user_marks**: Kullanıcı işaretleri/yorumları
- **version_history**: Kod sürüm geçmişi
- **ai_settings**: Global AI provider yapılandırması (provider, api_url, api_key, temperature, top_p, max_tokens, timeout + embedding_model/embedding_api_url/embedding_api_key)
- **project_permissions**: Proje bazlı erişim izinleri (read_only bayrağı)
- **user_settings**: Kullanıcı tercihleri (tema, **ai_api_url + ai_api_key override**)
- **audit_logs**: Denetim kayıtları (action, resource, ip)
- **function_embeddings**: Fonksiyon vektörleri (JSON, nomic-embed 768 boyut)
- **project_documents**: Eklenen dokümanlar (pdf/docx/xlsx/txt/md, extracted_text)
- **doc_chunks**: Doküman parçaları (embedding, sayfa aralığı)
- **fts_functions / fts_documents**: FTS5 tam metin indeksleri

### SQLite Optimizasyonları
- **WAL Mode**: Concurrent read/write desteği
- **Foreign Keys**: Cascade delete ile veri bütünlüğü
- **Indexed Columns**: Hızlı sorgular için indexler

## 💡 Kullanım Kılavuzu

### 1️⃣ Proje Yükleme

**Yöntem A: ZIP Upload**
1. Ana sayfada "Proje Yükle" sekmesine git
2. ZIP dosyasını seç
3. Proje adı ve açıklama gir
4. "Yükle ve Analiz Et" butonuna tıkla
5. Progress bar'dan ilerlemeyi takip et

**Yöntem B: Git Import** 🆕
1. "Git'ten İçe Aktar" sekmesine geç
2. Repository URL gir (örn: `https://github.com/user/repo`)
3. Sistem otomatik olarak:
   - Branch listesini çeker
   - Proje ismini doldurur
4. Branch seç ve "Clone ve Analiz Et" tıkla

### 2️⃣ Kod İnceleme

1. **Fonksiyon Listesi**: Tüm tespit edilen fonksiyonlar alphabetic sırada
2. **Accordion Lazy-Loading**: Bağımlılıklar accordion açılınca yüklenir (memory optimization)
3. **Entry Points**: @Service, @Controller, main metotları entry point olarak işaretlenir
4. **Qualified Names**: `ClassName.methodName` formatında görüntüleme

### 3️⃣ AI Analizi 🤖

**Recursive AI Summary Nasıl Çalışır:**
```
User: "🤖 AI Özeti Al" butonuna basar

Progress Tracking:
├─ [0%] AI sunucu bağlantısı kontrol ediliyor...
├─ [10%] ✓ Bağlantı başarılı
├─ [15%] Toplam 3 fonksiyon özetlenecek
│
├─ Alt fonksiyonları kontrol et:
│  ├─ [25%] 🔄 DatabaseHelper.save() (seviye 1)
│  │   └─ [35%] ✓ Tamamlandı: DatabaseHelper.save (245 karakter)
│  ├─ [45%] 🔄 Validator.check() (seviye 1)
│  │   └─ [55%] ✓ Tamamlandı: Validator.check (189 karakter)
│  └─ [65%] ✓ Atlandı (özet var): Logger.log
│
├─ [75%] 🤖 AI özeti üretiliyor: TakipServisGirisi.execute (2 bağımlılık)
└─ [100%] ✓ Tamamlandı: TakipServisGirisi.execute (512 karakter)
```

**Özellikler:**
- ✅ **Real-time Progress**: Her adım ekranda görünür
- ✅ **Dependency Tree**: Alt fonksiyonlar seviye bazında izlenir
- ✅ **Context-Aware**: AI alt fonksiyon özetlerini bilir
- ✅ **Smart Caching**: Zaten özeti olan fonksiyonlar atlanır

**Sonuç:** AI artık alt fonksiyonların görevlerini bildiği için tahmin yapmaz!

### 4️⃣ Kaynak Kod Arama 🔍

1. Fonksiyon detayında "Kaynak Kod" bölümüne git
2. Arama kutusuna kelime gir
3. 🔍 Ara veya **Enter** tuşuna bas
4. Eşleşmeler sarı renkte highlight edilir
5. **ESC** ile modalı kapat

### 5️⃣ Diyagram Görüntüleme

- **Entry Points**: Yeşil renkle vurgulanır
- **Fonksiyon Çağrıları**: Oklar ile gösterilir
- **Interactive**: Node'lara tıklayarak detay görüntüle
- **Lazy Load**: İlk 30 fonksiyon (performance optimization)

### 6️⃣ AI Sohbet ve RAG 💬

1. Proje detayında **Sohbet** sekmesine girin
2. Sorunuzu yazın — sistem ilgili fonksiyon ve doküman parçalarını otomatik bağlar
3. İsterseniz mesajdan önce **fonksiyon/doküman seçerek** kapsamı daraltın
4. Yanıt akarken alttaki **kaynak linklerinden** ilgili fonksiyona/PDF sayfasına gidin
5. **RAG Arama** ekranından "bul → sor" akışı: sonuç seç, sonra AI'a sor (ayrıntı: [RAG_AND_CHAT.md](RAG_AND_CHAT.md))

> En iyi sonuç için: analiz → toplu AI özeti → RAG indeksini kur (build).

### 7️⃣ Doküman Ekleme 📄

**Dosyalar → Dosya Ekle** ile PDF/DOCX/XLSX/TXT/MD ekleyin → otomatik chunk'lanıp RAG'e girer; kod/zip/war eklerseniz analize dahil edilir. (GELIS8)

### 8️⃣ Proje Taşıma (Export/Import) 📦

Proje detayında **📤 Dışa Aktar** → `.aikodanaliz` dosyası; hedef kurulumda **📥 İçe Aktar**. AI özetleri ve RAG vektörleri de taşınır; FTS indeksi için import sonrası "RAG build" başlatmayı unutmayın. (Detay: [EXPORT_IMPORT.md](EXPORT_IMPORT.md))

## Geliştirilecek Özellikler

Güncel yol haritası [todo.md](todo.md) dosyasındadır. Öne çıkanlar:

- 🚧 **GELIS9**: DALMap (XML) dosya desteği — tablo↔uyumluluk bağı çözümlemesi
- 🚧 **GELIS10**: Güvenlik riski taraması (fonksiyon/genel)
- 🚧 PostgreSQL tam desteği
- 🚧 Kullanıcı kimlik doğrulaması (JWT) + parola hash'leme
- 🚧 Diff/Patch gösterimi
- 🚧 CI (GitHub Actions) — test + coverage otomasyonu

## 🧪 Test ve Kalite Güvencesi

### Unit Test Paketi

Proje **25 unit test** içerir. Güncel durum (Kasım 2026): 22 test geçiyor; `test_app_and_routes.py` içindeki **3 upload testi RBAC geçişi sonrası güncellenmediği için başarısız** (oturumsuz istek 401 alıyor — bkz. [todo.md](todo.md) DZT-14). Toplam coverage **~%19**; chat/RAG/export gibi yeni modüller henüz testsiz.

#### Test Çalıştırma

```bash
# Tüm testleri çalıştır
./venv/bin/python -m unittest discover -s tests/unit -p 'test_*.py'

# Verbose mod
./venv/bin/python -m unittest discover -s tests/unit -p 'test_*.py' -v

# Belirli bir test dosyası
./venv/bin/python -m unittest tests.unit.test_code_analyzer
```

#### Test Coverage Raporu

```bash
# Coverage ile testleri çalıştır
./venv/bin/coverage run -m unittest discover -s tests/unit -p 'test_*.py'

# Terminal'de rapor göster
./venv/bin/coverage report -m

# HTML rapor oluştur
./venv/bin/coverage html
open coverage_html/index.html  # Tarayıcıda aç
```

#### Test Modülleri

| Test Dosyası | Test Sayısı | Kapsanan Alan |
|-------------|-------------|---------------|
| `test_code_analyzer.py` | 6 | Python, Java, PHP, HTML, generic parsing |
| `test_sql_analyzer.py` | 5 | SQL procedure, function, view, trigger |
| `test_progress_tracker.py` | 2 | Task tracking, lifecycle |
| `test_project_helpers.py` | 3 | Language detection, binary files |
| `test_app_and_routes.py` | 6 | Flask endpoints, upload validation |
| `test_permission_manager.py` | 3 | Role-based access control |

#### Coverage Özeti (Kasım 2026 ölçümü)

**Yüksek Kapsam (>70%)**
- ✅ `code_analyzer.py` - %89
- ✅ `app.py` - %83
- ✅ `progress_tracker.py` - %75

**Orta Kapsam (40-70%)**
- ⚠️ `database.py` - %54
- ⚠️ `logger.py` - %59
- ⚠️ `permission_manager.py` - %44

**Düşük Kapsam (<25%)** - Öncelikli İyileştirme Gerekiyor
- ❌ `routes/project.py` - %13
- ❌ `routes/user.py` - %15
- ❌ `lmstudio_client.py` - %9
- ❌ `rag_index.py` - %10
- ❌ `routes/chat.py`, `routes/export_import.py`, `routes/analysis.py` - <%10

**Toplam: %19** — yeni modüller (chat, RAG, export/import, audit) neredeyse hiç test edilmedi; `test_app_and_routes.py`'daki 3 upload testi auth eklendikten sonra güncellenmediği için başarısız (todo.md DZT-14).

📊 **Eski detaylı rapor (Mart 2026, %29 dönemi):** [COVERAGE_REPORT.md](COVERAGE_REPORT.md)

### Sürekli Entegrasyon (CI)

🚧 GitHub Actions workflow henüz eklenmedi. Planlanıyor:
- Her commit'te otomatik test çalıştırma
- Coverage raporu PR'lara otomatik yorum
- Lint ve type checking (mypy, flake8)

## Sorunlar & Destek

Sorunlarla karşılaştığınızda;
1. AI provider sunucusunun çalıştığını kontrol edin
2. Ayarlar > Bağlantı Test Et'i tıklayın
3. Hata mesajını kontrol edin

## Lisans

MIT License

---

**Geliştirici**: AI Kod Analiz Ekibi
**İlk Sürüm**: Mart 2026 · **Son güncelleme**: Kasım 2026
