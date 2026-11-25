# AIKodAnaliz - Masaüstü Uygulaması (GELIS17)

Tüm projeler üzerinden soru sorulabilen, backend'e bağlanan **PyQt6** tabanlı masaüstü istemcisi. Web arayüzünün tamamının kopyası değildir; amaç çoklu proje sohbeti + proje yönetim kısayollarıdır.

## 1. Çalıştırma

Önce backend çalışıyor olmalı (`./start.sh` veya `start.bat`, varsayılan `http://localhost:5000`).

| Platform | Komut |
|---|---|
| Linux / macOS | `./start_desktop.sh` (venv kurar/günceller, `--pull/-p` ile git pull + bağımlılık güncelleme) |
| Windows | `start_desktop.bat` veya `start_desktop.cmd` (içerikleri birebir aynıdır) |
| Her ortam | `python -m desktop_app` veya `python desktop_app/main.py` |

**Gereksinimler:** Python 3.8+, `PyQt6>=6.6.0`, `requests`, `markdown` (hepsi kök `requirements.txt` içinde).

## 2. Sunucu Adresi ve Giriş

- Uygulama açılışta backend adresini env'den çözer: `FLASK_HOST` (vars. `localhost`) + `FLASK_PORT` (vars. `5000`) → `http://host:port`. `.env` varsa `start_desktop.sh` bunu yükler.
- **Giriş ekranındaki "Sunucu Adresi" alanı** ile her zaman override edilebilir (uzaktaki bir sunucuya bağlanabilirsiniz).
- Giriş, web ile aynı hesaplarla yapılır (`POST /api/users/login`, session cookie tabanlı). Login başarısız olursa uygulama kapanır.

## 3. Arayüz

Çerçevesiz (frameless) pencere, sürüklenebilir üst başlık çubuğu:

```
┌────────────────────────────────────────────────┐
│  TitleBar: logo · bağlantı durumu · kullanıcı  │
├──────────────┬─────────────────────────────────┤
│  Sidebar     │  Chat Area (Markdown render)    │
│  · Proje     │  · mesaj balonları              │
│    listesi   │  · kaynak (refs) bağlantıları   │
│    (+filtre) │                                 │
│  · Sunucu    ├─────────────────────────────────┤
│    bilgisi   │  Input: mesaj kutusu            │
│  · 📤 / 📥   │  · ⤢ Sohbeti Genişlet / 🖥 Tam  │
│    export/   │    Ekran (sidebar gizlenir)     │
│    import    │  · ➤ Gönder · 🗑 Temizle        │
└──────────────┴─────────────────────────────────┘
```

- **Proje seçmeden soru sorma (otomatik yönlendirme):** Proje seçili değilse soru, erişilebilir tüm projelerde paralel RAG aramasıyla taranır (`ProjectRouterThread`); en yüksek skorlu proje otomatik seçilir ve cevap ondan üretilir.
- **Proje seçiliyse** sohbet o projenin bağlamıyla çalışır (seçili fonksiyon/doküman bağlamı desteklenir).
- Yanıtlar SSE ile akarak gelir; `think`/reasoning artıkları temizlenir, Markdown (kod blokları, tablolar) render edilir.
- **Temalar:** Uygulama tek bir koyu tema kullanır; renkler `desktop_app/theme_config.py` düzenlenerek değiştirilebilir (ışık/koyu geçiş düğmesi yoktur — light tema yalnızca web arayüzündedir).

## 4. Export / Import

Sidebar altındaki 📤/📥 düğmeleri backend export/import uçlarını kullanır; dosya uzantısı `*.aikodanaliz`. Biçim ve **import sonrası RAG build gerekliliği** için bkz. [EXPORT_IMPORT.md](EXPORT_IMPORT.md).

## 5. Kod Yapısı

| Dosya | Görev |
|---|---|
| `main.py` | Giriş noktası; env'den sunucu adresi, login diyaloğu |
| `login_dialog.py` | Sunucu adresi + kullanıcı adı/parola, drag-edilebilir pencere |
| `api_client.py` | Backend REST/SSE istemcisi (login, projeler, RAG arama, chat_stream, export/import) |
| `workers.py` | QThread'ler: `ProjectRouterThread`, `ChatStreamThread`, `ProjectListThread` |
| `main_window.py` | Ana pencere: sidebar + sohbet + input |
| `chat_widgets.py` | Mesaj balonları, Markdown→HTML, meta-artık temizliği |
| `export_import_ui.py` | Export/Import diyaloğu ve thread'leri |
| `theme_config.py` / `styles.py` | Renk paleti ve QSS stilleri |

## 6. Sorun Giderme

| Belirti | Çözüm |
|---|---|
| "Sunucuya bağlanılamadı" | Backend kapalı/yanlış port; login ekranındaki Sunucu Adresi'ni kontrol edin |
| Liste boş | Hesabınızın projelere erişimi yok (analyzer yalnızca paylaşılan projeleri görür) |
| Sohbet çok yavaş | Lokal AI provider yanıt süresi; `timeout`/`api_url` ayarlarını kontrol edin (bkz. [CONFIGURATION.md](CONFIGURATION.md)) |
| Windows'ta GUI açılmıyor | `venv` içinden `pip install -r requirements.txt` — PyQt6 eksik olabilir |
