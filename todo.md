# AIKodAnaliz Yapılacaklar (TODO) Listesi

## 🛠️ Düzeltmeler (DZT)
- [✅] **DZT-1:** Genel hata düzeltmeleri - 1 
- [✅] **DZT-2:** Kullanıcı yetkilerinin düzeltilmesi. Geliştirici rolü ve Anazlici rollerindeki kısıtların uygulanması. 
- [✅] **DZT-3:** Ayarlarda kaydetme işleminden önce test yapılmalı. Ekrandaki bilgilerle eğer başarılı olursa kaydet yapılmalı. 
- [✅] **DZT-4:** Eğer AI Özet  Al düğmesine basılır ise ve mevcutta bir özet zaten mevcut ise değiştirilmek istenip istenmediği sorularak analiz oluşturulması sağlanmalıdır. 
- [✅] **DZT-5:** Projeye sonradan eklenen dosyaların düzgün bir şekilde görüntülenmesi, SQL ve kodların fonksiyonlar altına eklenmesi, documanlarında ise ayrı bir alanda gösterilmesi gerekmektei. Dokümanlar için vektörel arama yapılabilmesi ve sonuçların doküman özelinde gösterilmesinin sağlanmalıdır.
- [✅] **DZT-6:** Fonksiyonlar ayrı ayrı analiz ediliyor. Tüm classın tekrar analiz edilmesi gerekir mi? Class içindeki fonksiyonların toptan analizi bekli olabilir ama gereksiz gibi duruyor. 
- [✅] **DZT-7:** Export ederken fonksiyon bağları taşınmışyor. Tekrar analiz yap dendiğinde de AI yorumları siliniyor. 
- [✅] **DZT-8:** Sohbet alanının daha okunaklı hale getirilmesi. AI cevabının formatlamasını düzeltilmesi. Paragraf paragraf gösterilmesinin sağlanması. Tüm ekranı kaplayacak şekilde seçeneklerin sunulması.

## ✨ Geliştirmeler (GELIS)
- [✅] **GELIS1:** Input box'ların düzeltilmesi. Görsel olarak daha uyumlu modern bir tarza çevrilmesi.
- [✅] **GELIS3:** Call graph çıkarma
- [✅] **GELIS5:** Proje açılınca detayları gösterilsin. Açıklama alanı güncellenbilsin. Proje bazında eksik rapor var ise topluca düzenlenebilsin. 
- [✅] **GELIS6:** Mevcut uygulama logunun dışında sunucu tarafında detaylı bir log dosyası tut her kullanıcı ne yapmış bileyim. Audit log gibi
- [✅] **GELIS7:** sadece kod alanını genişletme seçenği olsun.
- [✅] **GELIS4:** RAG index yapısı hazırlama
- [✅] **GELIS2:** AI Destekli Kod Analiz ve Sohbet Sistemi
  - **Genel Bakış:** Tüm projeler, seçili projeler veya seçili fonksiyonlar üzerinde çalışabilen AI ve RAG (Retrieval-Augmented Generation) destekli bir sohbet arayüzü istenmektedir. Sistem, proje kaynak kodlarını ve kod yorumlarını analiz ederek kullanıcıya açıklayıcı bilgiler sunabilmelidir.
  - **İşlevler:**
    - Kullanıcı proje hakkında doğal dil ile sorular sorabilmeli ve sistem ilgili kod parçalarını inceleyerek bağlama uygun cevaplar üretebilmeli.
    - Belirli bir işlemi gerçekleştirmek için projede hangi fonksiyon veya fonksiyonların kullanılabileceğini önerebilmeli.
    - Bir fonksiyonun çalışma akışını başlangıcından sonuna kadar analiz edebilmeli.
    - Bir fonksiyonun çağırdığı tüm alt fonksiyonları (call chain) tespit ederek bunların görevlerini açıklayabilmeli.
    - Fonksiyonlar arasındaki ilişkileri analiz ederek detaylı ve anlaşılır bir açıklama sunabilmeli.
    - Kod içindeki yorumları, fonksiyon isimlerini ve mantıksal akışı değerlendirerek fonksiyonların ne yaptığını detaylı şekilde açıklayabilmeli.
  - **Amaç:** Bu sayede kullanıcı, büyük ve karmaşık projelerde kodu manuel olarak incelemek zorunda kalmadan AI destekli analiz ve açıklamalar aracılığıyla sistemi daha hızlı anlayabilecektir.
- [✅] **GELIS8:** Mevcut bir projeye yeni bir dosya eklenmesine izin verilmeli. Eğer sql, java, zip, war dosyası ise aynı proje altına uygun bir klasör ile eklenmeli ve bu dosyalar analize dahil edilmesli. Eğer doc,docx, pdf vb. dokümanlar ise bunlar RAG analizine dahil edilmeli. 
- [❌] **GELIS9:** DALMap adı verilen dosyaların eklenmesine izin verilmeli. Bu dosyaların işlenmesi ve tablolar ile uygulamanın bağını sağlaması konusunda detaylı bilgi kullanıcıdan alınaran gerekli destek peojeye eklenmelidir. Detaylandırılan özellikler bu todo dosyası içerisine eklenmelidir. Genel olarak dalMap dosyaları sistem dalmap dosyası tipi ile yüklenebilmeli ayrı olarak işlenmelidir. Dosyanın genel yapısı xml yapısında olup, veri tababı tabloları ile uygulama içindeki sanal tablo tanımları ile ilişikleri yönetmektedir. 
- [❌] **GELIS10:** Güvenlik riskleri için tarama seçeneği ekle. Tek fonksiyon ya da tüm fonksiyonlar için güvenlik taraması yapabilsin.
- [✅] **GELIS11:** Projeler için RAG arama ekranı ve daha sonra bulunan sonuç/sonuçlar için AI soru sorulabileceği bir ekran yapılması.
- [✅] **GELIS12:** Projeler ekranında her projenin ne kadar RAG analizi yapıldığını, ve AI analiz oranını göster
- [✅] **GELIS13:** Proje yüklendikten sonra, Dosyalar bölümünde filtreleme olsun.
- [✅] **GELIS14:** Projeler ekranında Proje kutusuna basıncada proje açılsın, sadece aç düğmesinme basılmak zorunda kalmasın.
- [✅] **GELIS15:** Tüm modeller için think'in kapatılması. *(Not: fiilen çıktı temizliği olarak çalışıyor; modeli gerçekten kapatmak için DZT-15)*
- [✅] **GELIS16:** Sohbet alan düzeltmeleri
- [✅] **GELIS17:** Tüm projeler üzerinden soru sorulabilen bir masa üstü uygulaması hazırlanması.
- [✅] **GELIS18:** Projelerin teker teker ya da topluca export edilebilmesi ve export edilen projenin import edilebilmesi sağlanmalı. Amaç burada daha önce analizi yapılmış bir projeyi başka bir yere taşıyabilmek. *(Doğrulandı: tekli export + import web ve masaüstünde var; birden çok projeyi tek dosyada alan TOPLU export UI'ı yok - "ya da" okumasıyla kapandı, istenirse ayrıca planlanır)*
- [✅] **GELIS19:** llama.cpp için destek ekle. (Provider seçimi UI'da var, bağlantı testi, ayarlar katmanı, embedding-capability fallback, provider-nötr import katmanı tamamlandı - doğrulandı Kasım 2026)
- [✅] **GELIS20:** Sohbet alanında Kaynaklar arasındaki dokumanları mümkünse ilgili sayfalarını açacak şekilde linklerini güncelle.

## 🔌 AI Bağlantı Geliştirmeleri

- [✅] **GELIS23:** Embedding modelini sohbet modelinden ayırma + API Key desteği. Kapsam: `ai_settings`'e `api_key`/`embedding_model`/`embedding_api_url`/`embedding_api_key` anahtarları; `user_settings.ai_api_key` (kullanıcı bazlı anahtar; kullanıcı URL override'ında global anahtar asla gönderilmez); `Authorization: Bearer` header'ı client session'ında tek noktadan kurulur; `POST /api/ai-settings/embedding/test` yetenek ucu; Ayarlar ekranında API anahtarı + Embedding grubu (model/URL/anahtar + test, DZT-3 akışına entegre); env: `AI_API_KEY`, `EMBEDDING_*`; GET yanıtlarında anahtarlar maskelenir. Birim testler: `tests/unit/test_ai_auth_config.py` (17 test). Detay: CONFIGURATION.md, API.md §5, RAG_AND_CHAT.md §1
- [✅] **GELIS24:** LLM model ayarlarının zenginleştirilmesi. Kapsam: `user_settings.ai_model` (kullanıcı bazlı model; boşsa global `model_name`); `ai_settings`'e `model_name`/`context_limit` tohumlaması (yeni + mevcut DB migrasyonu); `GET/POST /api/ai-settings/models` (OpenAI `/v1/models` + LM Studio `/api/v0/models` + llama.cpp `/props` birleşimi; `context_length`, `max_output_tokens`, `suggested_max_tokens`, `state`, `quantization`, `defaults`; vLLM `max_input_tokens` desteği); `POST /api/ai-settings/generation/test` (gerçek sohbet tamamlama, `temperature=0`, `max_tokens=256`, geçersiz modelde tek yeniden deneme, reasoning-only yanıt kabulü); Ayarlar ekranında model **dropdown**'ı + "Modelleri Yükle"/"Yanıt Testi" + meta veri gösterimi; provider seçenekleri `lmstudio`/`llamacpp`/`vllm`/`openai` (vLLM/OpenAI'da yalnız `/v1/models`); kaydetme akışına uyarı niteliğinde yanıt testi entegrasyonu; global `model_name` yalnızca admin tarafından kaydedilir. Birim testler: `tests/unit/test_ai_model_selection.py` (21 test). Detay: CONFIGURATION.md, API.md §5, RAG_AND_CHAT.md §5
- [✅] **GELIS25:** LLM hata ayrıntısı + rate-limit bekleme. Kapsam: `backend/llm_errors.py` (`extract_error_detail`, `parse_retry_after`, `detect_rate_limit`, thread-safe `CooldownRegistry`); OpenAI/vLLM/LiteLLM/düz metin hata gövdelerinin ayrıştırılması; `Retry-After` (saniye/HTTP-date) ve gövde ipuçlarından bekleme süresi; ipucu yoksa `LLM_RATE_LIMIT_COOLDOWN` (60 sn), sonraki isteklerde üst sınır `LLM_RATE_LIMIT_MAX_WAIT` (120 sn); bekleme anahtarı sunucu URL'si (tüm kullanıcılar paylaşır); `lmstudio_client` içindeki tüm istek yollarına (model listesi, testler, analiz, chat/stream) entegrasyon; chat SSE'de `event:status` bekleme bildirimi ve `event:error` (`{error, retry_after_seconds}`) + `[DONE]`; arayüzde ayrıntılı hata ve "yaklaşık N sn sonra tekrar deneyin" ipucu. Birim testler: `tests/unit/test_llm_errors.py` (34 test). Detay: CONFIGURATION.md, API.md §5/§7, RAG_AND_CHAT.md §5

## 🔒 Güvenlik ve Kod Sağlığı (Dokümantasyon incelemesinde tespit edildi - Kasım 2026)

Kod incelemesi sırasında tespit edilen, dokümanlara işlenmiş gerçek sorunlar (detaylar: API.md "Bilinen Davranışlar", ARCHITECTURE.md "Bilinen Borç"):

- [❌] **DZT-9:** `GET /api/chat/project/<id>/search` bozuk: `_search_functions` tanımlı değil, `q` dolu her istek 500 veriyor. `RagIndex.search` veya `class.function` araması ile bağlanmalı (chat.py:399).
- [❌] **DZT-10:** `POST /api/projects/<id>/add-file` iki blueprint'te tanımlı (`project.py:349` ve `project_files.py:415`); Flask ilk kaydı kullandığı için `project_files.py` sürümü (çoklu dosya + otomatik Tree-sitter) ölü kod. Ya tek handler'da birleştirilmeli ya da diğeri silinmeli. Benzer ölü kod frontend'de de var: `main.js`'te `addFileToProject()` iki kez tanımlı (satır 316 ve 2751) - çalışan 2751'deki; 316'daki, erişilemeyen `project_files.py` yanıt şemasını bekleyen ölü koddur.
- [❌] **DZT-11:** Yetkisiz açık uçlar kapatılmalı: `GET /api/report` (tüm proje dökümü), tüm `/api/analysis/*`, tüm `/api/ai-settings/*` (ayar değiştirme dahil), tüm `/api/users/marks*` (`user_id` body'den geliyor, resolve admin değil), `POST /api/projects/git-info`, `GET /api/projects/progress/<task_id>`. En azından session + rol decorator'ları eklenmeli.
- [❌] **DZT-12:** Parolalar `users` tablosunda düz metin; Werkzeug `generate_password_hash` ile hash'lemeye geçilmeli (login/register/change-password + mevcut DB migrasyonu). Ayrıca `ADMIN_USERNAME/ADMIN_PASSWORD` env'leri okunuyor ama seed kodu (`database.py:315-334`) sabit değerler yazıyor - env okuyacak şekilde düzeltilmeli.
- [❌] **DZT-13:** `project.py` add-file doküman yolunda PDF/DOC için `extracted_text` placeholder ("PDF Document: ...") yazılıyor; chunk üretimi `project_files` yardımcıları ile telafi edilse de kayıttaki metin eksik kalıyor. `_extract_document_text` doğrudan çağrılmalı.
- [❌] **DZT-14:** `test_app_and_routes.py`'daki 3 upload testi başarısız: endpoint'lere `create_project` yetkisi eklendikten sonra testler oturum açmadan çağırıyor (401 != 400/201). Testlere login fixture'ı eklenmeli; şu an `Ran 25 tests, FAILED (failures=3)` (Kasım 2026 ölçümü, coverage %19).
- [❌] **DZT-15:** GELIS15 "think kapatma" fiilen çıktı filtreleme olarak çalışıyor (regex/stateful strip); modele think'i üretmemesi hiç söylenmiyor (`chat_template_kwargs`/`thinking_budget` gibi parametre gönderilmiyor) - token ve süre israfı devam ediyor. Provider parametreleriyle gerçek kapatma denenmeli, fallback olarak mevcut temizlik kalmalı.
- [✅] **DZT-16:** Sohbet RAG kalite teşhisi (Kasım 2026) düzeltmeleri: (1) arama artık **yalnız aktif embedding modelinin vektörlerini** kullanıyor — model karışımında (nomic + embeddinggemma) çapraz uzay kosinüs sessizce çöp skor üretiyordu; (2) vektor skoru **mean-center** ediliyor — anizotropi tabanı (~0.5+) birebir isim eşleşmelerini eziyordu; (3) FTS **AND→OR fallback** — doğal dil sorgularında AND 0 döndürüp semantik katmanı tek başına bırakıyordu; (4) bm25 normalizasyonu en iyi eşleşmeye göre [0,1]; (5) "input too large" 500'lerinde **kısaltarak yeniden deneme** (küçük `--batch-size`lı llama.cpp'de 1084/1084 embedding sessizce başarısızdı); (6) build worker **başarı/başarısız ayrımı** sayıyor ("1030/1030" yalanı bitti). Testler: `tests/unit/test_rag_hybrid.py`. Kalıcı çözüm için embedding sunucusunda `--batch-size ≥512` önerilir; model değiştirdikten sonra projeler için "İndeks Oluştur" yenilenmeli.
- [❌] **GELIS21:** Görev iptali kozmetik: `task/cancel` sadece tracker durumunu çeviriyor, worker thread çalışmaya devam ediyor. Analiz/özet döngülerine cooperative cancellation kontrolü eklenmeli; progress durumunun bellek-içi olması da değerlendirilmeli (restart'ta kayboluyor).
- [❌] **GELIS22:** Import sonrası FTS/embedding indeksi otomatik kurulmuyor; `export_import.py` import ettigi `RagIndex`'i çağırarak build'i kendisi tetiklemeli (şu an kullanıcıdan elle "RAG build" bekleniyor - EXPORT_IMPORT.md §3).