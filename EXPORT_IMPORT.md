# AIKodAnaliz - Proje Export / Import (GELIS18)

Amaç: Daha önce analiz edilmiş (AI özetleri, çağrı grafı ve RAG indeksi çıkarılmış) bir projeyi **tamamıyla** başka bir kurulumuza taşımak — yeniden analiz/özet üretimi harcamadan.

## 1. Export

- **UI:** Web'de proje detayında, masaüstü uygulamasında sidebar altında **📤 Dışa Aktar**.
- **API:** `POST /api/projects/<id>/export` (yetki: projeye `read`)
- **Sonuç:** ZIP tabanlı dosya, adı `<proje_adı>_<YYYYmmdd_HHMMSS>.aikodanaliz`.

### `.aikodanaliz` dosya içeriği (ZIP)

| Dosya | İçerik |
|---|---|
| `metadata.json` | Proje adı, açıklama, tarihler, `export_version` |
| `source_files.json` | Dosya kayıtları + **içerikleri** |
| `functions.json` | Fonksiyonlar (imza, sınıf/paket, satır aralıkları, **AI özetleri dahil**) |
| `function_calls.json` | Çağrı grafı kenarları |
| `embeddings.json` | `function_embeddings` — fonksiyon vektörleri |
| `doc_chunks.json` | Doküman chunk'ları (içerik + vektör + sayfa aralıkları) |
| `doc_embeddings.json` | (Varsa eski `doc_embeddings` tablosu — legacy uyumluluk) |
| `files/**` | `uploads/project_<id>` altındaki fiziksel dosyaların kopyası (dokümanlar dahil) |

**Hariç tutulanlar (tasarımsal):** kullanıcılar, proje izinleri, audit logları, `user_marks`, kişisel ayarlar. Proje taşındığında **yeni ortamın kullanıcılarına ayrıca izin verilmelidir**.

## 2. Import

- **UI:** Web'de projeler ekranında, masaüstü uygulamasında **📥 İçe Aktar** (`*.aikodanaliz` seçilir).
- **API:** `POST /api/projects/import` (multipart `file`; yetki: `create_project` → admin/developer)
- **Sonuç (201):** `{project_id, name, message}`

### Davranış kuralları

1. `metadata.json` yoksa → **400** `Geçersiz export dosyası`.
2. Proje, **importu yapan kullanıcıya ait yeni bir proje** olarak oluşturulur.
3. Aynı adda proje zaten varsa yeni proje `"<ad> (imported <zaman damgası>)"` adını alır — mevcut proje asla ezilmez.
4. Kayıtlar id yeniden-eşleme ile taşınır: `source_files` → `functions` → `function_calls` (dosyası eşlenemeyen fonksiyonlar ve ucu bulunamayan çağrılar atlanır), ardından `function_embeddings` (`INSERT OR REPLACE`) ve `doc_chunks`.
5. Fiziksel dosyalar `uploads/project_<yeni_id>` altına kopyalanır.

## 3. Import Sonrası Zorunlu Adım: FTS İndeksi

Embedding vektörleri dosyayla birlikte gelir, **ancak FTS5 tam metin indeksi ve `doc_chunks` tam metin kaydı import sırasında yeniden kurulmaz** (kod FTS rebuild'i çağırmıyor). Import sonrası:

```
POST /api/rag/project/<yeni_id>/build     # FTS'i kurar; embeddings zaten geldiği için {"embeddings": false} verilebilir
```

Bunu yapmazsanız RAG arama yarı semantik çalışır (LIKE fallback devreye girer). Admin olarak tüm sistem için: `POST /api/rag/admin/rebuild-all`.

## 4. Sık Sorunanlar

- **Farklı şema sürümü mü?** Import, tablo kolonlarını `PRAGMA table_info` ile kontrol edip toleranslı yazar; eski export'lar çoğunlukla sorunsuz alınır.
- **AI özetleri kaybolur mu?** Hayır — `functions.json` içindeki `ai_summary` alanıyla birlikte gelir; tekrar AI özet üretimi gerekmez.
- **İzinler neden gelmiyor?** Güvenlik gereği kullanıcı/izin verisi taşınmaz; hedef ortamda `POST /api/users/projects/<id>/permissions/grant` ile verin (bkz. [ROLES_AND_PERMISSIONS.md](ROLES_AND_PERMISSIONS.md)).
