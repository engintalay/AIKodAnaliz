# AIKodAnaliz Yapılacaklar (TODO) Listesi

## 🛠️ Düzeltmeler (DZT)
- [✅] **DZT-1:** Genel hata düzeltmeleri - 1 
- [✅] **DZT-2:** Kullanıcı yetkilerinin düzeltilmesi. Geliştirici rolü ve Anazlici rollerindeki kısıtların uygulanması. 
- [✅] **DZT-3:** Ayarlarda kaydetme işleminden önce test yapılmalı. Ekrandaki bilgilerle eğer başarılı olursa kaydet yapılmalı. 
- [✅] **DZT-4:** Eğer AI Özet  Al düğmesine basılır ise ve mevcutta bir özet zaten mevcut ise değiştirilmek istenip istenmediği sorularak analiz oluşturulması sağlanmalıdır. 
- [❌] **DZT-5:** Projeye sonradan eklenen dosyaların düzgün bir şekilde görüntülenmesi, SQL ve kodların fonksiyonlar altına eklenmesi, documanlarında ise ayrı bir alanda gösterilmesi gerekmektei. Dokümanlar için vektörel arama yapılabilmesi ve sonuçların doküman özelinde gösterilmesinin sağlanmalıdır.
- [✅] **DZT-6:** Fonksiyonlar ayrı ayrı analiz ediliyor. Tüm classın tekrar analiz edilmesi gerekir mi? Class içindeki fonksiyonların toptan analizi bekli olabilir ama gereksiz gibi duruyor. 
- [❌] **DZT-7:** Export ederken fonksiyon bağları taşınmışyor. Tekrar analiz yap dendiğinde de AI yorumları siliniyor. 


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
- [✅] **GELIS15:** Tüm modeller için think'in kapatılması.
- [❌] **GELIS16:** Sohbet alan düzeltmeleri
- [✅] **GELIS17:** Tüm projeler üzerinden soru sorulabilen bir masa üstü uygulaması hazırlanması.
- [✅] **GELIS18:** Projelerin teker teker ya da topluca export edilebilmesi ve export edilen projenin import edilebilmesi sağlanmalı. Amaç burada daha önce analizi yapılmış bir projeyi başka bir yere taşıyabilmek. 


Referanslar
[❌] [✅]