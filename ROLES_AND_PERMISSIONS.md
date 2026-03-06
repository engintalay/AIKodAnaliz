# 🔐 Rol ve Yetki Sistemi (RBAC)

## Genel Bakış

AIKodAnaliz'de 3 ana rol vardır ve her rol farklı izinler ile sunulan özellik setine erişir.

---

## 1. 👑 Admin (Yönetici)

### Yetkiler
- ✅ **Kullanıcı Yönetimi**: Tüm kullanıcıları oluştur, düzenle, sil
- ✅ **Rol Yönetimi**: Kullanıcıların rollerini değiştir
- ✅ **Proje Yönetimi**: Tüm projeleri görebilir, yönetebilir, silebilir
- ✅ **İzin Yönetimi**: Herhangi bir kullanıcıya herhangi bir projeye erişim verebilir
- ✅ **AI Özet Yönetimi**: Tüm fonksiyonları özetleyebilir
- ✅ **Sistem Ayarları**: LMStudio ve veritabanı ayarlarını yapılandırabiliir
- ✅ **Veri Dışa Aktarma**: Tüm projeleri ve verileri export edebilir

### Erişim
- Tüm projelere otomatik tam erişim
- Başka kullanıcılar veya rolleriyle herhangi bir ek yetki almaya ihtiyacı yok

---

## 2. 👨‍💻 Geliştirici (Developer)

### Yetkiler
- ✅ **Proje Oluşturma**: Yeni projeler ekleyebilir
- ✅ **Kendi Projelerini Yönetme**: 
  - Kendi yüklemiş olduğu projeleri silebilir
  - Dosya yükleyebilir
  - Projeyi yeniden analiz edebilir
- ✅ **İzin Yönetimi**: Kendi projelerine başka kullanıcılar ekleyebilir
  - Analizci rolüne salt okuma hakkı verebilir
  - Başka geliştirici rolüne kısıtlı erişim verebilir
- ✅ **AI Özet**: Kendi projelerinin fonksiyonlarını özetleyebilir
- ✅ **Analiz ve Diyagram**: Kendi projelerini analiz edebilir

### Kısıtlamalar
- ❌ **Başka Projelere Erişim**: Yalnızca kendisine açılmış projeleri görebilir
- ❌ **Kullanıcı Yönetimi**: Admin paneline erişemez
- ❌ **Sistem Yönetimi**: Sistem ayarlarını değiştiremez

### Erişim
- Yalnızca kendi oluşturduğu projeler
- Başka bir developer tarafından paylaştırılan projeler (eğer erişim verilmişse)
- **NOT**: Başka bir kullanıcıya yetki verdiği projelere erişimini kaybetmez (geri alınsa bile)

---

## 3. 🔍 Analizci (Analyzer)

### Yetkiler
- ✅ **Paylaşılan Projeleri Görüntüleme**: Kendisine erişim verilmiş projeleri görüntüleyebilir
- ✅ **Analiz Okuma**: Kod analizini, bağımlılıklarını ve diyagramları inceleyebilir
- ✅ **AI Özet Okuma**: Mevcut AI özetlerini okuyabilir

### Kısıtlamalar
- ❌ **Değişiklik Yapamaz**: Hiçbir veri değiştiremez (tamamen salt okuma)
- ❌ **Proje Oluşturamaz**: Yeni proje ekleyemez
- ❌ **Dosya Yüklemez**: Dosya yükleyemez
- ❌ **AI Özet Oluşturamaz**: Yeni özet oluşturamaz
- ❌ **Başka Projelere Erişim**: Yalnızca kendisine açılmış projeleri görebilir

### Erişim
- **Salt Okuma (Read-Only)**: Analizci rolünün bu kısıtlaması ASLA geçilemez
- **NOT**: Developer, analizci'ye "tam yetkili" izin verse bile, analizci yine salt okuma hakkına sahip olur

---

## 📋 İzin Yönetimi

### İzin Verme

**Geliştirici** başka kullanıcılara proje erişimi verebilir:

```
Proje: ProjectX
Kullanıcı: analyzer1
İzin Türü: 
  - Salt Okuma (✓) → Sadece görüntüleme
  - Tam Yetkili (başka dev'e) → Değişiklik yapabilir
```

### Önemli kurallar

1. **Analizci Kullanıcılara İzin**
   - İzin düzeyi ne olursa olsun, **analizci daima salt okuma**
   - "Tam yetkili" seçeneği seçilse bile, stil okuyabilir

2. **Developer Kullanıcılara İzin**
   - "Salt Okuma" → Salt görüntüleyebilir
   - "Tam Yetkili" → Dosya yükleyebilir, özet oluşturabilir (kendi projesi gibi)

3. **Admin'in Yetneği**
   - Herhangi bir kullanıcıya herhangi bir izni verebilir
   - Analizci için de kurallar geçerli

---

## 🔄 İzin Hiyerarşisi

```
Admin (100) 
├─ Tüm özelliklere tam erişim
│
Developer (50)
├─ Kendi projelerinde tam kontrol
├─ Başka projelerde yalnızca paylaşılmışsa erişim
│
Analizci (10)
└─ Yalnızca paylaşılmış projeleri salt okuma olarak görüntüleme
```

---

## 🎯 Tipik Kullanım Senaryoları

### Senaryo 1: Proje Geliştirici + Analizci Ekibi

1. **Developer** → Proje oluşturur
2. **Developer** → Analizci1, Analizci2'ye "Salt Okuma" izni verir
3. **Analizci'ler** → Projeyi analiz eder, yorumlar ve raporlar yaratır
4. **Result**: Analizci'ler değişiklik yapamaz, Developer tam kontrol altında

### Senaryo 2: Birden Fazla Geliştirici İşbirliği

1. **Developer1** → Proje oluşturur
2. **Developer1** → Developer2'ye "Tam Yetkili" izni verir
3. **Developer2** → Dosya yükleyebilir, özet oluşturabilir
4. **Result**: Her ikisi de projenin sahibiymiş gibi çalışır

### Senaryo 3: Admin Gözetimi

1. **Admin** → Tüm projeleri görüntüleyebilir
2. **Admin** → Gerekirse tüm izinleri yapılandırabilir
3. **Admin** → Herhangi bir kullanıcıyı silebilir veya devre dışı bırakabilir

---

## 🔑 Sistem Özellikleri

### Veri Güvenliği
- ✅ Salt okuma kullanıcılar hiçbir zaman veri değiştiremez
- ✅ Rol ve izin kontrolü backend'te yapılır (frontend'de sınırlı kontrol)
- ✅ Her işlem log kaydı tutulur

### Performans
- ✅ Projeler sadece erişim yetkisi olan kullanıcılar tarafından yüklenir
- ✅ Admin paneli sadece admin kullanıcılara sunulur
- ✅ İzin kontrolü veritabanı sorgusunda yapılır

### Esneklik
- ✅ Dinamik olarak izinler değiştirilebilir
- ✅ Mehrere roller kombinasyonları desteklenir
- ✅ Liman kalkımaz derektör kontrolü

---

## ❌ Yaygın Hatalar

1. **Analizci'ye "Tam Yetkili" İzin Vermek**
   - ❌ HATA: Analizci yine salt okuma olur
   - ✅ DOĞRU: Değişiklik yetkisi için developer rolü gerekli

2. **Admin İzin Vermesine İhtiyaç Yok**
   - ✅ DOĞRU: Admin otomatik tüm projelere erişebilir
   - ❌ HATA: Admin'in açıkça izin verilmesi gerekmez

3. **Kendi Projesine Yetki Vermek**
   - ✅ DOĞRU: Developer değişiklik yapabilir
   - ❌ HATA: Developer'in kendi projesine açıkça izin verilmesi gerekmez

---

## 📝 Ek Bilgiler

- **Demo Kullanıcılar**:
  - admin / admin123 (👑 Admin)
  - developer / dev123 (👨‍💻 Developer)
  - analyzer / analyzer123 (🔍 Analizci)

- **Veritabanı Tabloları**:
  - `users` - Kullanıcı bilgileri ve roller
  - `project_permissions` - Proje-level izinleri
  - `user_settings` - Kullanıcı tercihleri
