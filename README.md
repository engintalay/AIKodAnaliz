# AIKodAnaliz - Yapay Zeka Destekli Kod Analiz Aracı

Eski projeyi yeni teknolojiye dönüştürmek için kapsamlı dokümantasyon sağlayan web tabanlı kod analiz sistemi.

## Özellikler

✅ **Çok Dil Desteği**: Java, Python, JavaScript, TypeScript, PHP, CSS, HTML ve daha fazlası
✅ **Otomatik Kod Analizi**: Giriş-çıkış noktaları ve fonksiyon tespiti
✅ **İnteraktif Diyagram**: Fonksiyon bağlantılarının görsel gösterimi (Cytoscape.js)
✅ **Yapay Zeka Analizi**: LMStudio ile lokal AI desteği
✅ **Çok Kullanıcılı**: Admin + Viewer - İşaret ve yorum sistemi
✅ **Veritabanı**: SQLite (PostgreSQL desteği yakında)
✅ **Arama & Filtrele**: Fonksiyon adı ve açıklamalarında arama
✅ **Versiyon Kontrol**: Kod değişiklikleri takibi
✅ **PNG Export**: Diyagramları PNG olarak indirme

## Kurulum

### Gereksinimler
- Python 3.8+
- LMStudio (http://localhost:1234)
- SQLite 3

### Adım 1: Yükleme

```bash
cd /home/engin/projects/AIKodAnaliz
pip install -r requirements.txt
```

### Adım 2: Başlangıç

```bash
python backend/app.py
```

Tarayıcıda açın: `http://localhost:5000`

## Proje Yapısı

```
AIKodAnaliz/
├── backend/
│   ├── app.py                 # Flask ana uygulaması
│   ├── database.py            # SQLite bağlantısı
│   ├── lmstudio_client.py     # AI entegrasyonu
│   ├── analyzers/
│   │   └── code_analyzer.py   # Kod analiz motoru
│   └── routes/
│       ├── project.py         # Proje yönetimi
│       ├── analysis.py        # Kod analizi
│       ├── user.py            # Kullanıcı ve işaretler
│       ├── ai_settings.py     # LMStudio ayarları
│       └── diagram.py         # Diyagram verileri
├── frontend/
│   ├── index.html             # Ana sayfa
│   ├── css/
│   │   └── style.css          # Stillendirme
│   └── js/
│       └── main.js            # Frontend lojiği
├── database/
│   └── aikodanaliz.db         # SQLite veritabanı
├── uploads/                   # Yüklenen proje dosyaları
└── config/
    └── config.py              # Konfigürasyon
```

## API Endpoints

### Projeler
- `GET /api/projects` - Tüm projeleri listele
- `GET /api/projects/<id>` - Proje detayları
- `POST /api/projects/upload` - Proje yükle
- `GET /api/projects/<id>/files` - Proje dosyaları
- `DELETE /api/projects/<id>` - Projeyi sil

### Analiz
- `POST /api/analysis/project/<id>` - Projeyi analiz et
- `POST /api/analysis/function/<id>/ai-summary` - AI tarafından fonksiyon özeti
- `GET /api/analysis/project/<id>/functions` - Tüm fonksiyonlar
- `GET /api/analysis/dependencies/<id>` - Fonksiyon bağlantıları

### Kullanıcılar & İşaretler
- `POST /api/users/register` - Yeni kullanıcı
- `POST /api/users/marks` - İşaret ekle
- `GET /api/users/marks/<project_id>` - Proje işaretleri
- `PUT /api/users/marks/<id>/resolve` - İşareti çöz (Admin)

### AI Ayarları
- `GET /api/ai-settings` - Tüm ayarlar
- `PUT /api/ai-settings/<setting>` - Ayar güncelle
- `POST /api/ai-settings/lmstudio/test` - Bağlantı testi

### Diyagram
- `GET /api/diagram/project/<id>` - Diyagram verileri (nodes/edges)
- `POST /api/diagram/export/png` - PNG olarak dışa aktar

## LMStudio Ayarı

1. LMStudio yükleyin: https://lmstudio.ai
2. Bir model yükleyin
3. Sunucu başlatın (varsayılan: http://localhost:1234)
4. Ayarlar sekmesinden **Sıcaklık**, **Top P**, **Max Tokens** vb. yapılandırın

## Veritabanı Şeması

- **users**: Kullanıcı hesapları
- **projects**: Projeler
- **source_files**: Kaynak kod dosyaları
- **functions**: Analiz edilen fonksiyonlar
- **function_calls**: Fonksiyon bağlantıları
- **entry_points**: Başlangıç noktaları
- **user_marks**: Kullanıcı işaretleri/yorumları
- **version_history**: Kod sürüm geçmişi
- **ai_settings**: AI ayarları

## Kullanım Örneği

1. **Proje Yükle**: ZIP dosyasını seçip yükle
2. **Otomatik Analiz**: Sistem kodu analiz eder ve fonksiyonları tespit eder
3. **Diyagram Görüntüle**: Fonksiyonlar arası bağlantıları grafiksel olarak gör
4. **AI Özeti**: Her fonksiyon için yapay zeka tarafından özet al
5. **İşaretler Ekle**: Anlamadığınız yerlere işaret koyun
6. **Admin Takibi**: Admin soruları göz önüne alır ve güncellemeler yapar

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
