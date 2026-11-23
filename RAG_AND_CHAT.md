# AIKodAnaliz - RAG ve AI Sohbet Rehberi

Bu doküman RAG (Retrieval-Augmented Generation) indeksinin nasıl çalıştığını, doküman desteğini ve AI sohbet özelliğinin kullanımını anlatır. Endpoint referansı: [API.md](API.md) §7–§9.

## 1. Genel Mimari

RAG iki katmanlı getirme (retrieval) kullanır (`backend/rag_index.py`):

| Katman | Teknoloji | Ne yapar |
|---|---|---|
| **Tam metin** | SQLite **FTS5** (`fts_functions` sanal tablosu) | Hızlı, BM25 sıralı anahtar kelime araması |
| **Semantik** (opsiyonel) | Embedding vektörleri (`function_embeddings`, `doc_chunks.embedding`) | OpenAI-uyumlu `/v1/embeddings` ile üretilen vektörler üzerinden kosinüs benzerliği |

- **Embedding modeli:** varsayılan `text-embedding-nomic-embed-text-v1.5` (768 boyut) — **Ayarlar → Embedding (RAG) bölümünden değiştirilebilir** (GELIS23). Model adı değiştiğinde eski modelle üretilmiş vektörler bir sonraki build'de incremental olarak otomatik yeniden üretilir.
- **Ayrı embedding sunucusu (opsiyonel):** `embedding_api_url` doluysa embedding istekleri ayrı bir OpenAI-compatible sunucuya gider; boşsa sohbet sunucusu kullanılır.
- **API anahtarları (GELIS23):** anahtar tanımlıysa istekler `Authorization: Bearer <key>` ile gönderilir. Kural: embedding ayrı sunucudaysa sohbet anahtarı o sunucuya **gönderilmez**; aynı sunucudaysa sohbet anahtarı otomatik kullanılır.
- **Embedding API adresi:** `ai_settings` tablosundaki `embedding_api_url` → `api_url` (5 sn cache), yoksa `LMSTUDIO_API_URL` env değeri (`http://localhost:1234/v1`).
- **Yetenek testi:** Ayarlar ekranındaki **🔌 Embedding Test Et** ucu (`POST /api/ai-settings/embedding/test`) model/URL/anahtar kombinasyonunu örnek vektörle doğrular (`{available, model, dim, latency_ms}`).
- **Embedding desteği yoksa:** `/v1/embeddings` çağrısı **400/404/405/501** dönerse model geçici "desteksiz" işaretlenir (180 sn; başarılı yanıt 300 sn önbelleğe alınır) ve sistem otomatik olarak **leksik fallback**'e düşer. Ayrı embedding sunucusu kurmanıza gerek yoktur.

### Fonksiyon araması skorlaması (`RagIndex.search`)

1. `function_ids` açıkça verilirse arama atlanır, seçim birebir döner (skor 1.0) — sohbet "seçili fonksiyonlar" kapsamı bunu kullanır.
2. Embedding katmanı: **yalnızca aktif embedding modeliyle üretilmiş vektörler** kıyaslamaya alınır (`model_name` filtresi — farklı modellerin vektörleri karşılaştırılamaz). Kosinüs benzerliği, sorgu ortalaması çıkarılarak **mean-center** edilir: anizotropik embedding uzayında ilgisiz çiftlerin yüksek taban skoru (~0.5+) böylece sıfıra iner.
3. FTS5 katmanı: kullanıcı sorgusu güvenli MATCH ifadesine çevrilir (altyazılı token'lar, tırnaklı ifade desteklenir, en fazla 10 terim). Önce **AND** ile kesin arama denenir; sonuç boşsa **OR** fallback denenir (doğal dil sorgularında AND genelde 0 döner; bm25 nadir terimi yine de üste taşır). BM25 skoru, o sorgudaki **en iyi eşleşmeye göre [0,1]** aralığına normalize edilir.
4. **Hibrit skor:** `score = 0.6 × embedding(ortalanmış) + 0.4 × bm25_norm`
5. İki katman da boş dönerse **LIKE fallback** (skor sabit 0.1).

> Sunucu limiti: `/v1/embeddings` **500 + "input … too large"** dönerse (örn. llama.cpp `--batch-size` küçükse) metin otomatik olarak kısaltılıp (yarıya, en az 200 krç) **2 kez yeniden denenir** — uzun özetler böylece düşük batch'li sunucuda da vektörleştirilebilir. Kaliteden ödünmemek için embedding sunucusunda batch boyutunu ≥512 tutmak önerilir (DZT-16).

### İndeks kapsamı

- FTS5 indeks alanları: fonksiyon adı, sınıf, paket, **AI özeti**, dosya adı. → Anlamlı sonuç için önce AI özetlerinin üretilmesi (`bulk-ai-summary`) önerilir.
- Embedding'ler **yalnızca `ai_summary` dolu** fonksiyonlar için üretilir; özet metni `qualified_name + signature + summary` ilk 2000 karakteri vektörleştirilir.

## 2. İndeks Oluşturma / Yönetim

| İşlem | Nasıl |
|---|---|
| Proje indeksi kur | `POST /api/rag/project/<id>/build` — Body: `{embeddings?, fts?, force_rebuild?}` (hep vars. true/true/false). FTS senkron, embedding **arka plan thread'inde** koşar. Aynı proje için ikinci build sessizce atlanır. |
| Durum izle | `GET /api/rag/project/<id>/status` → `{status, done/total, indexed, total_functions, fts_indexed}` |
| Zorla tam yeniden kurulum | Aynı build ucu, `{"force_rebuild": true}` → `embedding_mode: "full"` |
| Tüm sistem | `POST /api/rag/admin/rebuild-all` (**admin**) — FTS tüm tabloyu yeniden kurar, her proje için **incremental** embedding başlatır |

**Incremental davranış:** Yalnız eksik embedding'ler, `model_name` değişmiş satırlar ve özeti `updated_at`'ı indeksleme tarihinden yeni olan fonksiyonlar yeniden vektörleştirilir.

> 💡 AI özetleri toplu üretildikten sonra (`bulk-ai-summary`) build tetiklenirse indeks en verimli hale gelir.

## 3. Projeye Doküman Ekleme (GELIS8)

`POST /api/projects/<id>/add-file` ile eklenen dosyalar türlerine göre ikiye ayrılır:

- **Kod / arşiv (zip, war, jar):** analiz hattına gider → `source_files` + Tree-sitter fonksiyon analizi.
- **Doküman:** RAG hattına gider → `uploads/project_<id>/documents/` altına kopyalanır, `project_documents` satırı + chunk'lar (`doc_chunks`) üretilir, arka planda chunk embedding'leri hesaplanır.

### Desteklenen doküman türleri ve okuyucular

| Tür | Okuyucu | Not |
|---|---|---|
| `pdf` | `pypdf` | Sayfa sayfa okunur; chunk'larda `page_start/page_end` metadata'sı tutulur |
| `docx` | `python-docx` | Eski `.doc` için metin çıkarma sınırlıdır |
| `xlsx` | `openpyxl` | Sayfa (sheet) adları `[Sayfa] <ad>` satırıyla korunur |
| `xls` | `xlrd` | |
| `txt`, `md` | Düz UTF-8 | |

**Chunk'lama:** ~800 karakter, 100 karakter örtüşme. PDF'te chunk'lar sayfa sınırına duyarlıdır.

### Doküman RAG yönetimi

- Liste: `GET /api/projects/<id>/docs` → dosya başına `chunk_count`, `embedded_count`.
- Yeniden kurma (dosya güncellendiğinde): `POST /api/projects/<id>/docs/rebuild-rag` (**write** yetkisi) — diskteki dosyadan chunk + embedding'leri sıfırdan üretir.
- Orijinal dosyayı indir: `GET /api/projects/<id>/docs/file/<filename>`.

## 4. RAG Arama Ekranı (GELIS11)

`GET /api/rag/project/<id>/search?q=...` fonksiyon ve doküman sonuçlarını **birleştirip tek listede** döner:

- Fonksiyonlar: hibrit skor, top 15.
- Dokümanlar: embedding sonuçlarından **skor ≥ 0.15** olanlar + leksik fallback sonuçları; `(dosya, chunk)` bazında dedupe, alıntı 260 karaktere kırpılır, top 8.
- Birleşik liste skora göre sıralanır → **top 20**; yanıtta `best_score` / `confidence` alanı en yüksek skoru verir (UI güven göstergesi).
- Doküman sonucu `result_type: "document"`, fonksiyon sonucu `result_type: "function"` taşır.

Bulunan sonuç(lar) için ardından sohbet ekranından AI'a soru sorulabilir (aşağıda).

## 5. AI Sohbet

Web arayüzünde proje detayındaki **Sohbet** sekmesi, masaüstü uygulamasında ana sohbet alanı aynı backend ucunu kullanır: `POST /api/chat/project/<id>` (SSE stream).

### Bağlam (context) kurulumu

Her soruda otomatik olarak:

1. **Fonksiyonlar:** Hibrit RAG araması (vars. top 10). Kullanıcı elle fonksiyon seçerse (`context_function_ids`) arama atlanır, yalnız seçilenler bağlam olur.
2. **Dokümanlar:** `doc_chunks` semantik araması; **yalnız skor > 0.30** olanlar bağlama girer. Hiç semantik hit yoksa leksik fallback'ten 3 sonuç denenir. Kullanıcının elle seçtiği doküman parçaları (`context_documents`, en fazla 12) her zaman önce eklenir. Doküman bloğuna en fazla 3 parça alınır.
3. System prompt yanıtın **Türkçe** ve Markdown formatında olmasını zorunlu kılar.

Kullanıcının `user_settings.ai_api_url` override'ı varsa sohbet onun gösterdiği sunucuya gider; aksi halde global AI ayarları kullanılır.

### Model seçimi (GELIS24)

Sohbet modeli şu sırayla çözülür: **`user_settings.ai_model`** (kullanıcı bazlı) → **`ai_settings.model_name`** (global) → `LMSTUDIO_DEFAULT_MODEL` env değeri. Kullanıcı Ayarlar ekranındaki **Model** alanından seçim yapar; alan hem datalist'ten seçime hem elle yazmaya izin verir.

- **Modelleri Yükle:** `POST /api/ai-settings/models` çağrısıyla model listesi ve meta verisi getirilir. API anahtarı girildikten sonra (veya kayıtlı anahtar varsa) otomatik de tetiklenir.
- **Meta veri:** `context_length`, `max_output_tokens`, `suggested_max_tokens`, `state`, `quantization` ve üretim varsayılanları gösterilir; `suggested_max_tokens` değeri `max_tokens` alanının üst sınırı olarak uygulanır.
- **Yanıt Testi:** `POST /api/ai-settings/generation/test` gerçek bir sohbet tamamlama isteği atar (`temperature=0`, `max_tokens=32`). Bağlantı testinden farklı olarak modelin fiilen yanıt ürettiğini doğrular; geçersiz model hatasında ilk mevcut modelle bir kez yeniden dener.
- **Kaydetme:** Ayarlar kaydedilirken bağlantı testine ek olarak model seçiliyse kısa yanıt testi de çalışır; başarısızsa kayıt engellenir.

### Yanıt akışı (SSE)

- İlk olay `event:refs`: yanıtın dayandığı kaynaklar (JSON).
- Ardından token'lar `data:` satırlarıyla akar; bitiş `[DONE]`.
- Modelin `think` / reasoning-kanal çıktıları sunucuda akıştan temizlenir (GELIS15) — kullanıcı yalnız nihai cevabı görür.

### Kaynak gösterimi (GELIS20)

`refs` listesindeki her kaynak tıklanabilirdir:

| Kaynak | Konet etiketi | Link |
|---|---|---|
| Fonksiyon | `paket.class.fonksiyon` + dosya | Fonksiyon detayına gider |
| PDF | `sayfa X` veya `sayfa X-Y` | `docs/file/<ad>#page=N` ile ilgili sayfaya |
| txt/md/doc | `satır X-Y` (chunk konumu tahmini) | Dosya indirme/link |
| Excel | `sayfa <sheet adı>` | Dosya linki |

### Sohbet ipuçları

- **"Tüm projeler" soruları:** Proje seçilmeden sorulan sorularda masaüstü uygulaması her projede paralel RAG araması yapıp en yüksek skorlu projeyi otomatik seçer (bkz. [DESKTOP_APP.md](DESKTOP_APP.md)).
- Kaliteli sohbet = kaliteli indeks: önce analiz + `bulk-ai-summary`, sonra RAG build.
- Sohbet salt okuma izniyle de kullanılabilir (yetki: projeye `read` erişimi).

## 6. İlgili Veritabanı Tabloları

| Tablo | İçerik |
|---|---|
| `fts_functions` (FTS5) | Fonksiyon tam metin indeksi |
| `fts_documents` (FTS5) | Doküman tam metin indeksi |
| `function_embeddings` | Fonksiyon başına tek vektör (JSON, 768 boyut), `model_name`, `indexed_at` |
| `project_documents` | Eklenen doküman kaydı + `extracted_text` |
| `doc_chunks` | Doküman parçaları: `chunk_index`, `content`, `embedding`, `page_start/page_end`; `UNIQUE(project_id, file_name, chunk_index)` |
