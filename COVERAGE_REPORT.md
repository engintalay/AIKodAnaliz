# Test Coverage Report

## Genel Bakış

Bu rapor, AIKodAnaliz projesinin backend kodunun unit test kapsamını gösterir.

**Son güncelleme:** 9 Mart 2026  
**Toplam Kapsam:** %29

## Modül Bazlı Kapsam

### ✅ Yüksek Kapsam (>80%)
- `backend/analyzers/code_analyzer.py` - **89%** 
  - Python, Java, JavaScript, TypeScript, PHP, SQL analiz mantığı
  - Test eksikleri: Bazı edge case'ler
  
- `backend/progress_tracker.py` - **89%**
  - Task izleme ve ilerleme raporlama
  - Test eksikleri: Cleanup ve ETA hesaplama edge case'leri
  
- `backend/logger.py` - **84%**
  - Loglama utility fonksiyonları
  - Test eksikleri: Error handler ve bazı wrapper fonksiyonlar

- `backend/app.py` - **83%**
  - Flask app initialization ve route tanımları
  - Test eksikleri: Template rendering ve error handler'lar

### ⚠️ Orta Kapsam (40-80%)
- `backend/database.py` - **67%**
  - SQLite database wrapper
  - Test eksikleri: Schema migration, batch operations, error handling
  
- `backend/analyzers/__init__.py` - **67%**
  - Analyzer modül init
  - Test eksikleri: Import error handling

- `backend/routes/project.py` - **41%**
  - Proje yükleme, Git clone, dosya işleme
  - Test eksikleri: Git import, nested JAR extraction, error paths

### ❌ Düşük Kapsam (<40%)
- `backend/permission_manager.py` - **35%**
  - Rol tabanlı yetkilendirme sistemi
  - **Öncelikli iyileştirme gerekiyor**
  
- `backend/routes/ai_settings.py` - **22%**
  - AI/LLM ayar yönetimi
  - **Öncelikli iyileştirme gerekiyor**
  
- `backend/routes/diagram.py` - **22%**
  - Diyagram oluşturma ve export
  - **Öncelikli iyileştirme gerekiyor**

- `backend/routes/user.py` - **15%**
  - Kullanıcı yönetimi (login, register, CRUD)
  - **Öncelikli iyileştirme gerekiyor**

- `backend/routes/report.py` - **11%**
  - Raporlama endpoint'leri
  - **Öncelikli iyileştirme gerekiyor**

- `backend/lmstudio_client.py` - **10%**
  - LMStudio API client
  - **Mock testler ile kapsanmalı**

- `backend/routes/analysis.py` - **8%**
  - Kod analiz ve AI summarization ana mantığı
  - **En kritik, öncelikli test eklemesi gerekiyor**

- `backend/analyzers/advanced_analyzer.py` - **8%**
  - Tree-sitter tabanlı gelişmiş analiz
  - **Integration testler ile kapsanmalı**

## Test Paketi İstatistikleri

**Toplam Test Sayısı:** 25  
**Test Dosyaları:** 6

- `test_code_analyzer.py` - 6 test (Python, Java, PHP, HTML, generic)
- `test_sql_analyzer.py` - 5 test (SQL procedure, function, view, trigger, dependencies)
- `test_progress_tracker.py` - 2 test
- `test_project_helpers.py` - 3 test
- `test_app_and_routes.py` - 6 test
- `test_permission_manager.py` - 3 test

## Öncelikli İyileştirme Planı

### Faz 1: Kritik Route'lar
1. **analysis.py** testleri ekle
   - AI analiz akışı mock testleri
   - Recursive summary testleri
   - Error handling testleri

2. **user.py** testleri ekle
   - Login/logout akışları
   - User CRUD işlemleri
   - Session yönetimi

### Faz 2: Orta Seviye Modüller
3. **permission_manager.py** testlerini genişlet
   - Tüm rol kombinasyonları
   - Project access kuralları
   - Grant/revoke işlemleri

4. **diagram.py** testleri ekle
   - Cytoscape graph oluşturma
   - PNG export

### Faz 3: Integration Testleri
5. **advanced_analyzer.py** integration testleri
   - Tree-sitter parser testleri
   - Gerçek kod örnekleriyle testler

6. **lmstudio_client.py** mock testleri
   - API call mocking
   - Retry mekanizması
   - Timeout handling

## Test Çalıştırma

### Tüm Testler
```bash
./venv/bin/python -m unittest discover -s tests/unit -p 'test_*.py'
```

### Coverage ile Testler
```bash
./venv/bin/coverage run -m unittest discover -s tests/unit -p 'test_*.py'
./venv/bin/coverage report -m
./venv/bin/coverage html  # HTML rapor oluşturur
```

### HTML Rapor Görüntüleme
```bash
open coverage_html/index.html  # macOS
xdg-open coverage_html/index.html  # Linux
```

## Katkıda Bulunma

Yeni test eklerken:
1. `tests/unit/` altına `test_*.py` formatında dosya oluşturun
2. `unittest.TestCase` sınıfından türetin
3. Mock'lama için `unittest.mock` kullanın
4. Test sonrası coverage raporunu güncelleyin

## Notlar

- Frontend (JavaScript) testleri henüz eklenmedi (Jest/Vitest ile eklenecek)
- CI/CD pipeline henüz yapılandırılmadı (GitHub Actions eklenecek)
- Integration testler minimal (gerçek DB + API testleri eklenecek)
