# AIKodAnaliz - Yapay Zeka Destekli Kod Analiz Aracı

Eski projeyi yeni teknolojiye dönüştürmek için kapsamlı dokümantasyon sağlayan web tabanlı kod analiz sistemi. Tree-sitter tabanlı hassas AST parsing ile kodunuzu derinlemesine analiz edin.

## ✨ Özellikler

### 📊 Kod Analizi
- ✅ **Çok Dil Desteği**: Java, Python, JavaScript, TypeScript, PHP (Tree-sitter AST parsing)
- ✅ **Otomatik Fonksiyon Tespiti**: Tüm fonksiyon, metod ve class tanımları
- ✅ **Qualified Name Matching**: `ClassName.methodName` ile hassas eşleştirme
- ✅ **Entry Point Tespiti**: Java `@Service`, `@Controller`, `@RestController` annotation desteği
- ✅ **Bağımlılık Analizi**: Fonksiyon çağrı grafı (3-tier resolution strategy)
- ✅ **Tekrar Analiz**: Projeleri yeniden analiz edebilme (re-analysis)

### 🤖 Yapay Zeka
- ✅ **LMStudio Entegrasyonu**: Lokal AI modeli desteği (localhost:1234)
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

### 🔧 Teknik Özellikler
- ✅ **Performans**: Browser memory 1.2GB → 300MB optimizasyonu
- ✅ **Proxy-Free**: Tüm network istekleri proxy kullanmaz
- ✅ **Multi-Platform**: Linux ve Windows startup scriptleri (`start.sh`, `start.bat`)
- ✅ **SQLite WAL Mode**: Concurrent read/write desteği
- ✅ **Tree-Sitter**: Regex yerine gerçek AST parsing

## 🚀 Kurulum

### Gereksinimler
- **Python 3.8+** (Test edildi: Python 3.14.3)
- **LMStudio** (http://localhost:1234) - Lokal AI modeli için
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

### Docker ile Kurulum

Docker kullanmayı tercih ediyorsanız, detaylı bilgi için [DOCKER.md](DOCKER.md) dosyasına bakın.

```bash
docker-compose up -d
```

### LMStudio Kurulumu

1. **LMStudio İndir**: https://lmstudio.ai
2. **Model Yükle**: Ayarlar → Models → İstediğiniz modeli indirin (örn: Mistral, Llama)
3. **Server Başlat**: Local Server → Start Server (Port: 1234)
4. **Test Et**: AIKodAnaliz'de Ayarlar → Bağlantı Test

**Sorun mu yaşıyorsunuz?** Proxy ayarlarınızı kontrol edin. Uygulama otomatik olarak proxy'yi bypass eder.

## 📁 Proje Yapısı

```
AIKodAnaliz/
├── backend/
│   ├── app.py                      # Flask ana uygulaması
│   ├── database.py                 # SQLite bağlantısı (WAL mode)
│   ├── lmstudio_client.py          # AI entegrasyonu (proxy-free)
│   ├── logger.py                   # Merkezi logging sistemi
│   ├── progress_tracker.py         # Real-time progress tracking
│   ├── analyzers/
│   │   ├── advanced_analyzer.py    # Tree-sitter AST parser
│   │   └── code_analyzer.py        # Legacy analyzer (deprecated)
│   └── routes/
│       ├── project.py              # Proje yönetimi (upload/import/delete)
│       ├── analysis.py             # Kod analizi (recursive AI summary)
│       ├── user.py                 # Kullanıcı ve işaretler
│       ├── ai_settings.py          # LMStudio ayarları
│       └── diagram.py              # Diyagram verileri (entry points)
├── frontend/
│   ├── index.html                  # Ana sayfa (modal, search, ESC support)
│   ├── css/
│   │   └── style.css               # Responsive design
│   └── js/
│       └── main.js                 # Frontend lojiği (lazy-load, git auto-fill)
├── config/
│   └── config.py                   # Konfigürasyon
├── database/
│   └── aikodanaliz.db              # SQLite database (auto-created)
├── uploads/                        # Yüklenen ZIP projeleri
├── tests/                          # Test dosyaları
├── start.sh                        # Linux/macOS başlatma scripti
├── start.bat                       # Windows başlatma scripti
├── requirements.txt                # Python dependencies
├── docker-compose.yml              # Docker konfigürasyonu
└── README.md                       # Bu dosya
```

## 🌐 API Endpoints

### Projeler
- `GET /api/projects` - Tüm projeleri listele
- `GET /api/projects/<id>` - Proje detayları
- `POST /api/projects/upload` - Proje yükle (ZIP)
- `POST /api/projects/import-git` - Git repository'den import
- `POST /api/projects/git-info` - Git URL'den branch listesi al (auto-fill için)
- `GET /api/projects/<id>/files` - Proje dosyaları
- `GET /api/projects/progress/<task_id>` - Real-time progress tracking
- `DELETE /api/projects/<id>` - Projeyi sil (cascade delete)

### Analiz
- `POST /api/analysis/project/<id>?task_id=<uuid>` - Projeyi analiz et (tekrar analiz destekler)
- `POST /api/analysis/function/<id>/ai-summary` - **Recursive AI özeti** (alt fonksiyonlar dahil)
- `GET /api/analysis/function/<id>` - Fonksiyon detayları (qualified name, source code, dependencies)
- `PUT /api/analysis/function/<id>/summary` - Manuel özet güncelle
- `GET /api/analysis/project/<id>/functions` - Proje fonksiyonları
- `GET /api/analysis/dependencies/<id>` - Fonksiyon bağlantıları
- `GET /api/analysis/test-connection` - LMStudio bağlantı testi

### Kullanıcılar & İşaretler
- `POST /api/users/register` - Yeni kullanıcı
- `POST /api/users/login` - Giriş yap
- `POST /api/users/marks` - İşaret ekle
- `GET /api/users/marks/<project_id>` - Proje işaretleri
- `PUT /api/users/marks/<id>/resolve` - İşareti çöz (Admin)

### AI Ayarları
- `GET /api/ai-settings` - Tüm ayarlar
- `PUT /api/ai-settings/<setting>` - Ayar güncelle (temperature, max_tokens, etc.)
- `POST /api/ai-settings/lmstudio/test` - Bağlantı testi

### Diyagram
- `GET /api/diagram/project/<id>` - Diyagram verileri (nodes/edges, entry points)
- `POST /api/diagram/export/png` - PNG olarak dışa aktar

## LMStudio Ayarı

1. LMStudio yükleyin: https://lmstudio.ai
2. Bir model yükleyin
3. Sunucu başlatın (varsayılan: http://localhost:1234)
4. Ayarlar sekmesinden **Sıcaklık**, **Top P**, **Max Tokens** vb. yapılandırın

## 💾 Veritabanı Şeması

- **users**: Kullanıcı hesapları (admin/viewer rolleri)
- **projects**: Projeler (upload_date, Git metadata)
- **source_files**: Kaynak kod dosyaları (language, content)
- **functions**: Analiz edilen fonksiyonlar (qualified_name, class_name, package_name, ai_summary)
- **function_calls**: Fonksiyon bağlantıları (caller → callee, call_type: qualified/unqualified)
- **entry_points**: Başlangıç noktaları (@Service, @Controller, main methods)
- **user_marks**: Kullanıcı işaretleri/yorumları
- **version_history**: Kod sürüm geçmişi
- **ai_settings**: LMStudio yapılandırması (temperature, max_tokens, timeout)

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
├─ [0%] LMStudio bağlantısı kontrol ediliyor...
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

## Geliştirilecek Özellikler

- 🚧 PostgreSQL tam desteği
- 🚧 Kullanıcı kimlik doğrulaması (JWT)
- 🚧 Kaynak kodu görüntüleyici (syntax highlighting)
- 🚧 Diff/Patch gösterimi
- 🚧 Daha gelişmiş kod analizi
- 🚧 API dokümantasyonu otomatik oluşturma
- 🚧 Multi-model LM desteği

## Sorunlar & Destek

Sorunlarla karşılaştığınızda;
1. LMStudio'un çalıştığını kontrol edin
2. Ayarlar > Bağlantı Test Et'i tıklayın
3. Hata mesajını kontrol edin

## Lisans

MIT License

---

**Geliştirici**: AI Kod Analiz Ekibi
**İlk Sürüm**: Mart 2026
