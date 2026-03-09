# AIKodAnaliz Yapılacaklar (TODO) Listesi

## 🛠️ Düzeltmeler (DZT)
- [✅] **DZT-1:** Genel hata düzeltmeleri - 1 
- [✅] **DZT-2:** Kullanıcı yetkilerinin düzeltilmesi. Geliştirici rolü ve Anazlici rollerindeki kısıtların uygulanması. 


## ✨ Geliştirmeler (GELIS)
- [✅] **GELIS1:** Input box'ların düzeltilmesi. Görsel olarak daha uyumlu modern bir tarza çevrilmesi.

- [❌] **GELIS2:** AI Destekli Kod Analiz ve Sohbet Sistemi
  - **Genel Bakış:** Tüm projeler, seçili projeler veya seçili fonksiyonlar üzerinde çalışabilen AI ve RAG (Retrieval-Augmented Generation) destekli bir sohbet arayüzü istenmektedir. Sistem, proje kaynak kodlarını ve kod yorumlarını analiz ederek kullanıcıya açıklayıcı bilgiler sunabilmelidir.
  - **İşlevler:**
    - Kullanıcı proje hakkında doğal dil ile sorular sorabilmeli ve sistem ilgili kod parçalarını inceleyerek bağlama uygun cevaplar üretebilmeli.
    - Belirli bir işlemi gerçekleştirmek için projede hangi fonksiyon veya fonksiyonların kullanılabileceğini önerebilmeli.
    - Bir fonksiyonun çalışma akışını başlangıcından sonuna kadar analiz edebilmeli.
    - Bir fonksiyonun çağırdığı tüm alt fonksiyonları (call chain) tespit ederek bunların görevlerini açıklayabilmeli.
    - Fonksiyonlar arasındaki ilişkileri analiz ederek detaylı ve anlaşılır bir açıklama sunabilmeli.
    - Kod içindeki yorumları, fonksiyon isimlerini ve mantıksal akışı değerlendirerek fonksiyonların ne yaptığını detaylı şekilde açıklayabilmeli.
  - **Amaç:** Bu sayede kullanıcı, büyük ve karmaşık projelerde kodu manuel olarak incelemek zorunda kalmadan AI destekli analiz ve açıklamalar aracılığıyla sistemi daha hızlı anlayabilecektir.

- [✅] **GELIS3:** Call graph çıkarma
- [❌] **GELIS4:** RAG index yapısı hazırlama
- [✅] **GELIS5:** Proje açılınca detayları gösterilsin. Açıklama alanı güncellenbilsin. Proje bazında eksik rapor var ise topluca düzenlenebilsin. 
- [✅] **GELIS6:** Mevcut uygulama logunun dışında sunucu tarafında detaylı bir log dosyası tut her kullanıcı ne yapmış bileyim. Audit log gibi
- [✅] **GELIS7:** sadece kod alanını genişletme seçenği olsun.