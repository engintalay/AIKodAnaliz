# AIKodAnaliz — Geliştirme İş Akışı

Bu dosya, projedeki TODO maddelerinin nasıl geliştirileceğini tanımlar.
OpenCode bu kurallara uyar.

## Branch Politikası (TODO bazlı)

1. **Her TODO maddesi kendi branch'inde geliştirilir.**
   - Branch adı, TODO kimliğidir: `GELIS9`, `GELIS10`, `DZT-9`, `DZT-10`, ...
   - Örnek: GELIS9 işine başlarken `git switch GELIS9` (yoksa `git switch -c GELIS9 main`).
2. **Tüm kod yazma / düzeltme işi o branch'te yapılır.** `main` üzerinde doğrudan
   geliştirme yapılmaz.
3. Branch zaten varsa:
   - Önce `git switch <TODO-ID>` yapılır.
   - `main` ile fark varsa `git merge main` (veya rebase) ile güncellenir.
   - Çakışma varsa kullanıcıya bildirilir.
4. İş bitince branch'te commit edilir ve `origin`'e push edilir.

## Test ve Başarı Oranı Takibi

- Her anlamlı değişiklikten sonra ilgili testler çalıştırılır.
- Test sonucu (geçen/toplam, başarı oranı) commit mesajında veya iş özetinde raporlanır.
- Testler kırıksa merge talebi yapılmaz; önce düzeltilir.
- Mevcut test komutları:
  - `./venv/bin/python -m pytest tests/ -q` (veya projedeki test runner)
  - `node --check frontend/js/main.js`
  - `./venv/bin/python -m py_compile <değişen dosyalar>`

## Merge Kuralı

- **Kullanıcı açıkça onay vermeden `main`'e merge YAPILMAZ.**
- Kullanıcı "tamam, yeterince olgunlaştı, merge et" dediğinde:
  1. Branch'in testleri yeşil mi doğrulanır.
  2. `git switch main && git pull`
  3. `git merge <TODO-ID>`
  4. Çakışma/hata yoksa `git push origin main`
  5. Branch silinir (isteğe bağlı, kullanıcıya sorulur).
- Onay gelmeden sadece branch üzerinde çalışılır; `main`'e dokunulmaz.

## Commit Kuralları

- Commit mesajı TODO kimliğiyle başlar: `GELIS9: ...`, `DZT-9: ...`.
- Küçük ve anlamlı commit'ler tercih edilir.
- Commit öncesi `git status` kontrol edilir; ilgisiz dosyalar eklenmez.
