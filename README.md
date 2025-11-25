# 🐾 PatiLog: Evcil Hayvan Sağlık Takip Sistemi

**PatiLog**, evcil hayvanlarınızın aşı takvimini, kilo değişimlerini ve genel sağlık durumlarını takip etmek için geliştirilmiş kişisel bir bulut uygulamasıdır.

Bu proje; Python (Streamlit), Google Sheets (Veritabanı) ve GitHub Actions (Otomatik Hatırlatıcılar) kullanılarak oluşturulmuştur.

---

# 🚨 ÖNEMLİ UYARI / DISCLAIMER 🚨

> **LÜTFEN OKUYUNUZ:**
>
> Bu GitHub deposundaki kodlar **AÇIK KAYNAK** (Open Source) olsa da, şu anda canlıda çalışan uygulama **KİŞİSEL KULLANIMIM İÇİNDİR.**
>
> Eğer bu sayfada veya Streamlit üzerinde çalışan bir "Demo" linki görüyorsanız, **LÜTFEN KENDİ EVCİL HAYVANLARINIZIN BİLGİLERİNİ GİRMEYİNİZ.**
> * Girdiğiniz veriler **benim** kişisel Google Sheet dosyama kaydedilecektir.
> * Verileriniz başkaları tarafından görülebilir.
> * Sistemden herhangi bir zamanda silinebilir.
>
> **Kendi PatiLog uygulamanızı kurmak ve sadece kendi verilerinizi güvenle saklamak için lütfen aşağıdaki "Kendi Versiyonunu Nasıl Kurarsın?" rehberini takip edin.**

---

## ✨ Özellikler

* **Mobil Uyumlu Arayüz:** Kart görünümü ile telefondan kolay takip.
* **Akıllı Hatırlatıcılar:** Aşı zamanı yaklaşan (7 gün ve altı) işlemler için otomatik Email bildirimi.
* **Kilo Takibi:** İnteraktif grafikler ile evcil hayvanınızın kilo geçmişi.
* **Dark Mode:** Göz yormayan modern tasarım.
* **Bulut Tabanlı:** Bilgisayarınıza hiçbir şey kurmanıza gerek yok.

---

## 🛠️ Kendi Versiyonunu Nasıl Kurarsın? (Adım Adım Rehber)

Bu uygulamayı kendi hayvanlarınız için kullanmak istiyorsanız, teknik bilginiz olmasa bile aşağıdaki adımları takip ederek 15 dakikada kurabilirsiniz.

### 1. Adım: Kodları Kopyalayın (Fork)
1.  Bu sayfanın sağ üst köşesindeki **"Fork"** butonuna tıklayın.
2.  "Create Fork" diyerek projeyi kendi GitHub hesabınıza kopyalayın.

### 2. Adım: Google Tarafı (Veritabanı Kurulumu)
1.  **[Google Cloud Console](https://console.cloud.google.com/)** adresine gidin.
2.  Yeni bir proje oluşturun (Adı: `PatiLog` olabilir).
3.  Arama çubuğuna yazıp şu iki servisi bulup **ENABLE** (Aktif Et) deyin:
    * `Google Sheets API`
    * `Google Drive API`
4.  Arama çubuğuna `Credentials` yazın -> **Create Credentials** -> **Service Account**.
    * Servis hesabına bir isim verin.
    * Role kısmında **"Editor"** seçeneğini seçin.
5.  Oluşturduğunuz servis hesabına tıklayın -> **KEYS** sekmesi -> **Add Key** -> **Create New Key (JSON)**.
    * Bilgisayarınıza bir dosya inecek. Bu dosya sizin **ANAHTARINIZDIR**. İçini not defteriyle açın ve kopyalayın.
6.  **Google Sheets**'e gidin, boş bir dosya açın (Adı: `PatiLog_DB`).
7.  İndirdiğiniz JSON dosyasının içinde `client_email` yazan adresi kopyalayın. Google Sheet dosyanızı bu email adresiyle **Paylaşın (Share)** (Editör olarak).

### 3. Adım: Uygulamayı Canlıya Alın (Streamlit)
1.  **[Streamlit Cloud](https://share.streamlit.io/)** adresine gidin ve GitHub hesabınızla giriş yapın.
2.  **"New App"** butonuna tıklayın.
3.  Repository kısmında az önce Fork ettiğiniz `PatiLog` projesini seçin.
4.  Aşağıda **"Advanced Settings"** butonuna tıklayın.
5.  **Secrets** kutusuna şunu yapıştırın:
    ```toml
    [gcp_service_account]
    type = "service_account"
    project_id = "JSON_DOSYASINDAKI_PROJECT_ID"
    private_key_id = "JSON_DOSYASINDAKI_PRIVATE_KEY_ID"
    private_key = "JSON_DOSYASINDAKI_PRIVATE_KEY_HEPSI"
    client_email = "JSON_DOSYASINDAKI_CLIENT_EMAIL"
    client_id = "JSON_DOSYASINDAKI_CLIENT_ID"
    auth_uri = "[https://accounts.google.com/o/oauth2/auth](https://accounts.google.com/o/oauth2/auth)"
    token_uri = "[https://oauth2.googleapis.com/token](https://oauth2.googleapis.com/token)"
    auth_provider_x509_cert_url = "[https://www.googleapis.com/oauth2/v1/certs](https://www.googleapis.com/oauth2/v1/certs)"
    client_x509_cert_url = "JSON_DOSYASINDAKI_URL"
    ```
    *(Not: Buradaki değerleri bilgisayarınıza inen JSON dosyasındaki karşılıkları ile değiştirin).*
6.  **Deploy!** butonuna basın. Uygulamanız hazır!

### 4. Adım: Email Bildirimlerini Açın (Otomasyon)
Uygulama kapalıyken bile email almak için:

1.  Google Hesabınızda **Güvenlik** -> **2 Adımlı Doğrulama** -> **Uygulama Şifreleri (App Passwords)** kısmına gidin. Yeni bir şifre oluşturup 16 haneli kodu kopyalayın.
2.  Kendi GitHub sayfanıza gidin (Fork ettiğiniz proje).
3.  **Settings** -> **Secrets and variables** -> **Actions** kısmına gidin.
4.  **New repository secret** diyerek şu 4 bilgiyi ekleyin:
    * `GCP_CREDENTIALS`: Bilgisayarınıza inen JSON dosyasının **tüm içeriği**.
    * `EMAIL_USER`: Gmail adresiniz.
    * `EMAIL_PASS`: Az önce aldığınız 16 haneli Google Uygulama Şifresi.
    * `EMAIL_TO`: Bildirim gidecek email adresi (veya adresleri, virgülle ayırın).
5.  GitHub'da **Actions** sekmesine gidin, sol taraftan "Daily Vaccine Check"i seçin ve "Enable Workflow" butonuna basın.

🎉 **Tebrikler! Artık tamamen size ait, ömür boyu ücretsiz bir Pati Takip sisteminiz var.**
