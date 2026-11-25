# AIKodAnaliz - API Referansı

Bu doküman backend'deki **tüm REST endpoint'lerini** kapsar. Mimari genel bakış için [ARCHITECTURE.md](ARCHITECTURE.md), RAG/Sohbet detayları için [RAG_AND_CHAT.md](RAG_AND_CHAT.md), export/import biçimi için [EXPORT_IMPORT.md](EXPORT_IMPORT.md).

## Genel Kurallar

- **Temel adres:** `http://localhost:5000` (varsayılan). Tüm API yolları `/api/...` ile başlar.
- **Format:** İstek ve yanıtlar JSON'dur (dosya yükleme hariç: `multipart/form-data`).
- **Hata biçimi:** Hatalar genellikle `{"error": "..."}` şeklinde döner; durum kodu 4xx/5xx olur.
- **Kimlik doğrulama:** Flask **session cookie** tabanlıdır (JWT yok). `POST /api/users/login` sonrası tarayıcıya 7 günlük cookie set edilir (`SESSION_COOKIE_HTTPONLY`). Session alanları: `user_id`, `username`, `role`.
- **Roller:** `admin`, `developer`, `analyzer`. Yetki denetimi backend'de `permission_manager.py` decorator'ları ile yapılır:
  - `@check_permission(key)` — session yoksa **401**, rolde yetki yoksa **403**.
  - `@check_project_access('read'|'write')` — projeye erişim yoksa **403**; `write` istenip kullanıcı read-only ise **403** (`Read-only access...`).
  - Admin tüm projelere tam erişir; `analyzer` rolü izin kaydında `read_only=0` olsa bile **daima salt okumadır**.
  - Ayrıntı: [ROLES_AND_PERMISSIONS.md](ROLES_AND_PERMISSIONS.md)

---

## 1. Sistem (backend/app.py)

| Metod | Yol | Yetki | Açıklama |
|---|---|---|---|
| GET | `/` | yok | Ana SPA (frontend/index.html) |
| GET | `/api/health` | yok | Sağlık kontrolü |
| GET/POST | `/api/heartbeat` | yok | Uptime/heartbeat |
| GET | `/static/css/...`, `/static/js/...` | yok | Statik dosyalar |

## 2. Projeler (`/api/projects` — routes/project.py)

| Metod | Yol | Yetki | Açıklama |
|---|---|---|---|
| GET | `/api/projects/` | session | Kullanıcının görebildiği projeler (admin: tümü; developer: sahip olduğu + paylaşılan; analyzer: yalnız paylaşılan). Her projede AI/RAG analiz oran metrikleri yer alır (GELIS12). |
| GET | `/api/projects/<id>` | read | Proje detayı + istatistikler (audit: `project_view`) |
| PUT | `/api/projects/<id>` | write | Ad/açıklama güncelle (audit: `project_update`) |
| POST | `/api/projects/upload` | create_project | ZIP yükle, arşivle, otomatik analiz başlat |
| POST | `/api/projects/git-info` | **yok** | `{url}` → `{repo_name, branches[], default_branch[, warning]}` (`git ls-remote`, 30 sn timeout; erişilemezse varsayılan branch listesi + `warning` ile yine 200) |
| POST | `/api/projects/import-git` | create_project | `{url, name, branch='main', description}` → shallow clone (`--depth 1`, 300 sn timeout), `source_files` kaydı. **201:** `{project_id, task_id, name, files_processed, files_skipped}` |
| POST | `/api/projects/<id>/add-file` | write | Projeye sonradan dosya ekle (aşağıda) |
| GET | `/api/projects/<id>/files` | read | Dosya listesi (filtre parametreleri desteklenir) |
| GET | `/api/projects/<id>/files/<file_id>` | read | Tek dosya detayı (içerik dahil) |
| GET | `/api/projects/progress/<task_id>` | **yok** | Real-time progress (aşağıda) |
| DELETE | `/api/projects/<id>` | delete | Projeyi sil (cascade; audit: `project_delete`) |

### POST `/api/projects/<id>/add-file` (GELIS8)

`multipart/form-data`, tek `file` alanı. Uzantıya göre üç davranış:

1. **Arşiv `.zip / .war / .jar`:** Geçici dizine açılır (WAR içindeki gömülü JAR'lar da). İkili/binary uzantılar (jar, class, exe, dll, görseller, medya, fontlar…) atlanır; WAR için ayrıca metin beyaz listesi uygulanır (html, jsp, js, css, xml, sql, java, py, txt, md …). Kalanlar `source_files`'a eklenir.
2. **Doküman `.pdf / .docx / .doc / .txt / .md / .xlsx / .xls`:** `uploads/project_<id>/documents/` altına yazılır, `project_documents` satırı oluşturulur, chunk'lar üretilip `doc_chunks`'a yazılır ve arka planda embedding başlatılır (RAG'e dahil).
3. **Tek kod dosyası `.java / .sql / .py / .js / .ts / .php`:** Doğrudan `source_files`'a eklenir; yanıtta dönen `added_file_id` ile frontend ayrıca `analyze-single-file` çağırır.

Diğer uzantılar → **400** `Desteklenmeyen dosya tipi`.
**201:** `{project_id, task_id, file_name, files_processed, documents_added, files_skipped, added_file_id, message}`. Audit: `project_file_added`.

> ⚠️ **Not:** `routes/project_files.py` içinde aynı yolda çoklu-dosya destekli ikinci bir handler tanımlıdır ancak Flask ilk kaydı (project.py) kullandığı için **project.py davranışı geçerlidir**.

### GET `/api/projects/progress/<task_id>`

**200:** `{status: started|completed|failed, progress: 0-100, total, current_step, details[], metrics{...}, started_at, updated_at}`.
`metrics`: `total_functions, completed_functions, remaining_functions, active_thread, estimated_remaining_seconds, ai_calls, ai_prompt_tokens, ai_completion_tokens, ai_total_tokens, ai_total_duration_seconds, ai_avg_duration_seconds`.
Görev bellek-içidir; sunucu restart'ı veya süre aşımında `{status:'failed', task_exists:false}` döner (polling'i durdurmak için).

## 3. Analiz (`/api/analysis` — routes/analysis.py)

> Bu blueprint'teki route'larda **yetki decorator'ı yoktur** (session yalnız kullanıcı-AI-URL'i ve audit için okunur). Ağ erişimine açık kurulumlarda dikkat.

| Metod | Yol | Açıklama |
|---|---|---|
| GET | `/api/analysis/test-connection` | AI provider bağlantı testi |
| POST | `/api/analysis/project/<id>` | Tüm projeyi analiz et (yeni analiz/tekrar analiz). Query: `task_id` (ops.) |
| POST | `/api/analysis/project/<id>/analyze-single-file/<file_id>` | Tek dosyayı yeniden analiz et (o dosyanın eski fonksiyonları silinir). Desteklenmeyen dil → **422** |
| POST | `/api/analysis/file/<file_id>` | Dosya bazlı analiz |
| POST | `/api/analysis/function/<fid>/ai-summary` | Recursive AI özeti (bağımlılıklar önce özetlenir). Audit: `ai_summary_generated` |
| POST | `/api/analysis/project/<id>/bulk-ai-summary` | Özetli/önetsiz tüm fonksiyonları toplu özetle (aşağıda) |
| GET | `/api/analysis/function/<fid>` | Fonksiyon detayı (qualified name, kaynak, bağımlılıklar) |
| PUT | `/api/analysis/function/<fid>/summary` | Manuel özet güncelle |
| GET | `/api/analysis/project/<id>/functions` | Projenin fonksiyon listesi |
| GET | `/api/analysis/dependencies/<project_id>` | Fonksiyon çağrı bağlantıları |
| GET | `/api/analysis/errors` | Hatalı özetler (`ai_summary LIKE 'Error:%'`). Query: `project_id` (ops.) |
| POST | `/api/analysis/errors/clear` | `{function_ids[] | project_id | ∅}` → hatalı özetleri NULL'lar. `{success, cleared}` |
| POST | `/api/analysis/errors/reanalyze` | Hatalı özetleri **senkron** yeniden üretir (istem AI boyunca bloke olur). `{success, total, reanalyzed, failed, task_id}` |
| GET | `/api/analysis/global-ai-stats` | Bellek-içi toplam AI metrikleri (restart'ta sıfırlanır) |
| GET | `/api/analysis/active-tasks` | Devam eden progress görevleri |
| GET | `/api/analysis/recent-files` | Son geçerli özet üretilen fonksiyonlar. Query: `limit` (vars. 20) |
| POST | `/api/analysis/task/<task_id>/cancel` | Görevi iptal işaretle (aşağıdaki uyarıya bakın) |

**bulk-ai-summary:** Query `task_id` **zorunlu** (yoksa 400). Body (ops.): `extra_criteria`, `extra_question`. AI bağlı değilse **503**. Daemon thread başlatır → **202** `{message, task_id}`. Hedefler: `ai_summary` boş / `⚠️` / `Error:` ile başlayanlar. Audit: `bulk_ai_summary_started`.

> ⚠️ **İptal kozmetiktir:** `cancel` yalnız tracker durumunu `failed/İptal edildi` yapar; çalışan worker thread durmaz.

## 4. Kullanıcılar, Ayarlar ve İzinler (`/api/users` — routes/user.py)

### Oturum

| Metod | Yol | Yetki | Not |
|---|---|---|---|
| POST | `/api/users/login` | yok | `{username, password}` → session + `{user{id,username,role}}`. Pasif hesap → 403. Audit: `login`. ⚠️ Parola DB'de düz metin saklanır |
| POST | `/api/users/logout` | session | Session temizle; audit `logout` |
| GET | `/api/users/current` | session | `{id, username, role, full_name, email}` |
| POST | `/api/users/register` | admin | Yeni kullanıcı (rol default `analyzer`); çakışma → 409 |

### Profil / Kişisel ayarlar

| Metod | Yol | Açıklama |
|---|---|---|
| GET | `/api/users/settings` | `{id, username, role, full_name, email, theme, notifications_enabled, items_per_page, default_filter, ai_api_url, ai_api_key (maskeli) + ai_api_key_set, ai_model, preferences}` |
| PUT | `/api/users/settings` | Verilen alanları günceller. `ai_api_url`: **kullanıcı bazlı AI sunucu URL override'ı** (boş string → NULL). `ai_api_key`: kullanıcı bazlı anahtar — boş string → silinir, maskeli değer (`••••…`) → değişmez. `ai_model`: kullanıcı bazlı model seçimi (boş string → NULL, global `model_name` kullanılır). Kullanıcı URL override'ı varsa chat isteklerinde yalnız bu anahtar kullanılır (global anahtar sızmaz) |
| PUT | `/api/users/change-password` | `{current_password, new_password}`; yeni parola ≥ 4 krn, eskisiyle aynı olamaz |

### Kullanıcı yönetimi (yalnız **admin** — `manage_users`)

| Metod | Yol |
|---|---|
| GET | `/api/users/admin/all` |
| POST | `/api/users/admin/create` |
| GET | `/api/users/admin/<user_id>` |
| PUT | `/api/users/admin/<user_id>` |
| DELETE | `/api/users/admin/<user_id>/delete` (son admin silinemez; silmede marks/permissions/settings de silinir) |
| GET | `/api/users/list` (admin + developer) |

### Proje izinleri

| Metod | Yol | Yetki | Not |
|---|---|---|---|
| GET | `/api/users/projects/<pid>/permissions` | admin veya sahip developer | `[{id, username, role, read_only, is_owner}]` |
| POST | `/api/users/projects/<pid>/permissions/grant` | admin veya sahip developer | `{user_id, permission_level='read', read_only=true}`. **analyzer hedefse `read_only=true` zorunlu kılınır.** Başka projeye izin verilemez → 400 |
| POST | `/api/users/projects/<pid>/permissions/revoke` | admin veya sahip developer | `{user_id}` → izin satırı silinir |

### İşaretler (marks)

| Metod | Yol | Not |
|---|---|---|
| POST | `/api/users/marks` | Body: `{project_id, function_id, user_id, mark_type, comment}` |
| GET | `/api/users/marks/<project_id>` | Projenin işaretleri (kullanıcı adı + fonksiyonla join'li) |
| PUT | `/api/users/marks/<mark_id>/resolve` | Body: `{status}` → işaret durumu güncellenir |

> ⚠️ Bu üç uçta **yetki kontrolü yoktur**: `user_id` body'den alınır (kimlik taklidi mümkün) ve resolve admin gerektirmez. RBAC genişletmesi önerilir (todo).

## 5. AI Ayarları (`/api/ai-settings` — routes/ai_settings.py)

> ⚠️ Bu uçlarda **yetki decorator'ı yoktur** (auth gerektirmez); UI bunu admin panelinde gösterse de API seviyesinde korumasızdır.

| Metod | Yol | Açıklama |
|---|---|---|
| GET | `/api/ai-settings/` | Tüm ayarlar (`provider`, `api_url`, `model_name`, `context_limit`, `temperature`, `top_p`, `max_tokens`, `timeout`, `embedding_model`, `embedding_api_url`, …). **Gizli anahtarlar maskeli döner**: `api_key`/`embedding_api_key` → `••••<son4>` + `*_set` bayrağı |
| PUT | `/api/ai-settings/<setting_name>` | Tek ayar güncelle. Gizli anahtarlarda özel semantik (aşağıda) |
| POST | `/api/ai-settings/provider/test` | Aktif provider bağlantı testi. Body (ops.): `{api_url?, provider?, api_key?}` — `api_url` farklı bir sunucu ise kayıtlı anahtar o sunucuya gönderilmez; `api_key` yalnız testte kullanılır |
| GET/POST | `/api/ai-settings/models` | **Model listesi + meta veri (GELIS24).** GET kayıtlı ayarları kullanır; POST ops. `{api_url?, provider?, api_key?}` override'ı alır (kalıcı değil). **200:** `{models: [{id, context_length, max_output_tokens, suggested_max_tokens, state, type, quantization, publisher, arch, defaults}], api_url, provider, error}`. Meta veri kaynakları: OpenAI `/v1/models`, LM Studio `/api/v0/models`, llama.cpp `/props` |
| POST | `/api/ai-settings/generation/test` | **Gerçek yanıt testi (GELIS24).** Body (ops.): `{api_url?, provider?, api_key?, model?, max_tokens?}` (`max_tokens` varsayılanı **256**). Küçük bir prompt ile `temperature=0` sohbet tamamlama isteği atar; geçersiz model hatasında ilk mevcut modelle bir kez yeniden dener. Reasoning modelleri bütçeyi `reasoning_content`'te harcayıp boş `content` döndürebilir; bu durumda reasoning metni geçerli yanıt sayılır (`reasoning_only: true`). **200:** `{status: ok|error, model, reply?, reasoning_only?, latency_ms, prompt_tokens?, completion_tokens?, total_tokens?, status_code?, error?}` |
| POST | `/api/ai-settings/embedding/test` | **Embedding yetenek testi (GELIS23).** Body (ops.): `{embedding_model?, embedding_api_url?, embedding_api_key?, api_key?}` (maskeli değerler yok sayılır). **200:** `{available, model, api_url, dim?, latency_ms, status_code?, error?}` |
| POST | `/api/ai-settings/lmstudio/test` | Geriye uyumluluk: eski test route'u |

**Gizli anahtar PUT semantiği (`api_key`, `embedding_api_key`):** `value` yok/`null`/maskeli yansıma (`••••…`)/boş string → **değer değiştirilmez**; `{"value": "", "clear": true}` → anahtar silinir; dolu değer → kaydedilir. Diğer ayarlarda boş string anlamlıdır (örn. `embedding_api_url: ""` = sohbet sunucusunu kullan).

Provider değeri `lmstudio`, `llamacpp`, `vllm` veya `openai` olabilir; hepsi OpenAI-compatible çalışır. Provider görünen adı ve meta veri kaynağını belirler: `lmstudio`/`llamacpp` için `/api/v0/models` ve `/props` zenginleştirmeleri denenir; `vllm`/`openai` için yalnız `/v1/models` kullanılır. Ayarlar `ai_settings` tablosundan çözülür (5 sn cache), yoksa env default'larına düşer. Anahtar dolduysa tüm AI isteklerine `Authorization: Bearer <key>` eklenir. Bkz. [CONFIGURATION.md](CONFIGURATION.md).

**Rate limit ve hata ayrıntısı (GELIS25):** LLM yanıtı hata döndürdüğünde kullanıcıya yalnız `HTTP <kod>` değil, gövdeden ayrıştırılan okunabilir ayrıntı gösterilir (OpenAI `error.message`, vLLM/FastAPI `detail`, LiteLLM `error`, düz metin). Hata rate-limit/kota kaynaklıysa bekleme süresi `Retry-After` başlığından (saniye veya HTTP-date) veya gövdedeki `try again in 20s` / `retry_after` ipuçlarından okunur; ipucu yoksa `LLM_RATE_LIMIT_COOLDOWN` (vars. 60 sn) kullanılır. Bekleme kaydı süreç genelinde ve thread-safe'dir, anahtarı sunucu URL'sidir; aynı sunucuya giden tüm kullanıcılar beklemesi paylaşır. Sonraki istekler en fazla `LLM_RATE_LIMIT_MAX_WAIT` (vars. 120 sn) bekletilir; daha uzun beklemede istek hiç gönderilmez ve kalan süre bildirilir. Bu uçların hata yanıtları `retry_after_seconds` alanı içerir. Bkz. [CONFIGURATION.md](CONFIGURATION.md).

**Model seçimi (GELIS24):** Etkin model önce `user_settings.ai_model` (kullanıcı bazlı), boşsa `ai_settings.model_name` (global) değerinden çözülür. Model listesi ve meta verisi (`context_length`, `max_output_tokens`, `suggested_max_tokens`, üretim varsayılanları) `/api/ai-settings/models` ile alınır; `suggested_max_tokens` sağlayıcı çıktı limiti biliniyorsa o, değilse `min(context_length, 4096)` olur. Ayarlar ekranında model alanı bir **dropdown**'dur: "Modelleri Yükle" listeyi doldurur, kayıtlı model listede yoksa `(kayıtlı)` seçeneği olarak korunur. "Yanıt Testi" gerçek bir tamamlama isteğini çalıştırır. Kaydetme akışı bağlantı testine ek olarak model seçiliyse kısa bir yanıt testi de yapar; yanıt testi **uyarı niteliğindedir** (başarısız olsa da seçim kaydedilir). Global `model_name` yalnızca admin tarafından kaydedilir; normal kullanıcı yalnızca kendi `ai_model` değerini değiştirir.

## 6. Diyagram (`/api/diagram` — routes/diagram.py)

| Metod | Yol | Açıklama |
|---|---|---|
| GET | `/api/diagram/project/<id>/` | Cytoscape nodes/edges (entry point işaretli; yalnız mevcut node'lara bağlı edge'ler gönderilir) |
| GET | `/api/diagram/function/<fid>/callgraph` | Tek fonksiyonun çağrı grafı |
| POST | `/api/diagram/export/png` | PNG dışa aktarma |

## 7. Sohbet (`/api/chat` — routes/chat.py)

Ayrıntılı çalışma prensibi: [RAG_AND_CHAT.md](RAG_AND_CHAT.md).

### POST `/api/chat/project/<project_id>` — sohbet (SSE stream)

- **Yetki:** `check_project_access('read')`
- **Body:**
  - `message` *(zorunlu)* — boşsa 400
  - `history` — `[{role: user|assistant, content}]` (son konuşma turları)
  - `context_function_ids` — `int[]`; verilirse RAG araması atlanır, **birebir bu fonksiyonlar** bağlam olur (skor 1.0)
  - `context_documents` — `[{file_name, chunk_index}]`; seçili doküman parçaları önce eklenir (en fazla 12)
  - `max_tokens` — opsiyonel
- **Yanıt:** `text/event-stream`:
  1. İlk olay `event:refs` → JSON: kaynak listesi (`{id, name, file}` fonksiyonlar; `{type:'document', name, file, chunk_index, location, page_start}` dokümanlar — `location` PDF'te `sayfa X[-Y]`, metinde `satır X-Y`, xlsx'te `sayfa <ad>`).
  2. Rate limit beklemesi gerekiyorsa `event:status` → JSON `{message}` (örn. "Rate limit: yaklaşık 30 saniye bekleniyor..."). Bekleme `LLM_RATE_LIMIT_MAX_WAIT` süresini aşarsa istek gönderilmez.
  3. Token olayları `data:<token>\n\n` (newline `\n` olarak kaçışlı).
  4. Bitiş `data:[DONE]`.
  5. Hata `event:error` → JSON `{error, retry_after_seconds?}` + `data:[DONE]`. `error` gövdesi LLM'den gelen ayrıntılı mesajı taşır; `retry_after_seconds` yalnız rate-limit durumunda dolar.
- Modelin `think`/reasoning kanal çıktıları sunucuda temizlenir (GELIS15). Kullanıcının `ai_api_url` override'ı varsa o sunucuya gidilir. Audit: `chat_message_sent` (mesajın ilk 100 karakteri).

### GET `/api/chat/project/<project_id>/search?q=...`

Sohbet otomatik tamamlama: `class.function` + dosya, en fazla 15 sonuç.
> ⚠️ **Bilinen hata:** Bu route içerde tanımsız `_search_functions` çağırıyor; `q` dolu istekler 500 döndürür. (Kod düzeltilene kadar kullanmayın; alternatif: `GET /api/rag/project/<id>/search`.)

## 8. RAG (`/api/rag` — routes/rag.py)

| Metod | Yol | Yetki | Açıklama |
|---|---|---|---|
| GET | `/api/rag/project/<id>/search?q=` | read | Hibrit arama (fonksiyon + doküman, top 20). **200:** `{results[], best_score, confidence}`; her sonuçta `result_type: function|document` |
| POST | `/api/rag/project/<id>/build` | read | İndeks kur. Body (ops.): `{embeddings: true, fts: true, force_rebuild: false}`. Embedding arka planda → **202** `{fts_indexed, embeddings:'arka planda çalışıyor'|'atlandı', embedding_mode:'full'|'incremental'}` |
| GET | `/api/rag/project/<id>/status` | read | `{status: idle|running|done|error, total, done, elapsed?, error?, indexed, total_functions, fts_indexed}` |
| POST | `/api/rag/admin/rebuild-all` | **admin** | Tüm projelerin FTS + embedding indekslerini yenile → **202** `{fts_total, projects}` |

Skorlama katmanları ve eşikler RAG_AND_CHAT.md'de.

## 9. Proje Dosyaları ve Dokümanlar (`/api/projects` — routes/project_files.py)

| Metod | Yol | Yetki | Açıklama |
|---|---|---|---|
| GET | `/api/projects/<id>/docs` | read | Doküman listesi: `[{file_name, chunk_count, embedded_count, added_at}]` |
| POST | `/api/projects/<id>/docs/rebuild-rag` | **write** | Kayıtlı dokümanları diskten yeniden okuyup chunk + embedding'leri sıfırdan kurar. `{documents_processed, chunks_created, documents_skipped, total_documents}`. Audit: `project_documents_rag_rebuilt` |
| GET | `/api/projects/<id>/docs/file/<filename>` | read | Dokümanın orijinal dosyasını indir (frontend chat kaynak linkleri PDF için `#page=N` anchor'ı ekler) |

Desteklenen doküman türleri: `pdf, docx, doc, txt, md, xlsx, xls` (okuyucular: pypdf, python-docx, openpyxl, xlrd).

## 10. Export / Import (`/api/projects` — routes/export_import.py)

| Metod | Yol | Yetki | Açıklama |
|---|---|---|---|
| POST | `/api/projects/<id>/export` | read | ZIP tabanlı `.aikodanaliz` dosyası indirir (`<ad>_<zaman>.aikodanaliz`). Audit: `project_exported` |
| POST | `/api/projects/import` | create_project | `multipart` `file` (`.aikodanaliz`) → **201** `{project_id, name, message}`. Ad çakışırsa `"<ad> (imported <ts>)"`. Audit: `project_imported` |

İçerik, hariç tutulanlar ve **import sonrası RAG rebuild gerekliliği** için: [EXPORT_IMPORT.md](EXPORT_IMPORT.md).

## 11. Rapor (`/api/report` — routes/report.py)

| Metod | Yol | Yetki | Açıklama |
|---|---|---|---|
| GET | `/api/report` | **yok** ⚠️ | Tüm projelerin AI özeti kapsam raporu: `{statistics{total, with_summary, without_summary, coverage}, projects[{..., files{...functions[], missing_functions[]}}]}`. Fonksiyon başına `qualified_name`, `has_summary`, `ai_estimated_input_tokens`, `ai_code_mode(full|trimmed|class-compact)` |

> ⚠️ Bu uç şu an kimlik doğrulama gerektirmez ve tüm projelerin dökümünü verir; ağa açık kurulumda risklidir.

## 12. Admin / Denetim Kayıtları (`/api/admin` — routes/admin_audit.py)

Her iki uç da **admin** gerektirir (değilse 403).

| Metod | Yol | Açıklama |
|---|---|---|
| GET | `/api/admin/audit-logs` | Filtreler (query): `limit` (vars. 200, maks. 1000), `offset`, `action` (LIKE), `username` (LIKE), `from`, `to` (tarih). **200:** `{total, limit, offset, logs[]}` (id DESC) |
| GET | `/api/admin/audit-logs/actions` | Filtre kutuları için distinct action adları (alfabetik) |

**Yazılan action adları:** `login`, `logout`, `project_view`, `project_update`, `project_delete`, `project_file_added`, `project_documents_rag_rebuilt`, `chat_message_sent`, `project_exported`, `project_imported`, `ai_summary_generated`, `bulk_ai_summary_started`.
Log satırı: `{user_id, username, action, resource_type, resource_id, details, ip_address, created_at}` (GELIS6).

---

## Bilinen Davranışlar ve Uyarılar (özet)

1. `POST /api/projects/<id>/add-file` iki kez tanımlı; **geçerli olan `project.py`** sürümüdür (tek dosya alanı, otomatik Tree-sitter tetiklemez).
2. `GET /api/chat/project/<id>/search` şu an **bozuk** (tanımsız fonksiyon çağrısı → 500).
3. Görev **iptali** yalnız tracker etiketini değiştirir; worker durmaz. Progress durumu bellek-içidir (restart'ta kaybolur).
4. Yetki istemeyen uçlar: `GET /api/report`, tüm `/api/analysis/*`, tüm `/api/ai-settings/*`, tüm `/api/users/marks*`, `POST /api/projects/git-info`, `GET /api/projects/progress/<task_id>`.
5. Parolalar `users` tablosunda **düz metin**; production'da hash'e geçilmeli (todo).
6. Import sonrası FTS/embedding indeksleri **otomatik kurulmaz** → `POST /api/rag/project/<id>/build` çağırın.
