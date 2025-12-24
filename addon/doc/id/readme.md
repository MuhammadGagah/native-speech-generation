# Native Speech Generation for NVDA

**Penulis:** Muhammad Gagah [muha.aku@gmail.com](mailto:muha.aku@gmail.com)

Native Speech Generation adalah add-on NVDA yang mengintegrasikan **Google Gemini AI** untuk menghasilkan ucapan berkualitas tinggi dan terdengar alami langsung di dalam NVDA.
Add-on ini menyediakan antarmuka yang bersih dan sepenuhnya dapat diakses untuk mengubah teks menjadi audio, mendukung **narasi pembicara tunggal** dan **dialog multi-pembicara yang dinamis**.

Add-on ini dirancang untuk alur kerja yang lancar, interaksi yang mengutamakan aksesibilitas, dan kontrol suara yang fleksibel, cocok untuk narasi, dialog, dan produksi konten audio.

---

## Fitur

### Pembuatan Ucapan Berkualitas Tinggi

* Pilih antara:
  * **Gemini Flash**: Kualitas standar, pembuatan cepat, latensi rendah.
  * **Gemini Pro**: Premium, suara lebih realistis (model berbayar).

### Mode Single & Multi-Speaker

* **Narasi pembicara tunggal** untuk text-to-speech standar.
* **Mode multi-pembicara (2 pembicara)** untuk dialog dengan suara yang berbeda.

### Kontrol Suara Tingkat Lanjut

* **Penamaan Pembicara**
  Tetapkan nama khusus (misalnya, *Budi*, *Siti*) dalam mode multi-pembicara.
  AI secara otomatis memetakan suara berdasarkan nama pembicara dalam naskah.
* **Instruksi Gaya**
  Berikan petunjuk seperti *“Bicaralah dengan nada ceria”* atau *“Ceritakan dengan tenang”* untuk memandu penyampaian.
* **Kontrol Temperatur**
  Sesuaikan variasi dan kreativitas output:
  * Nilai lebih rendah → ucapan lebih stabil dan dapat diprediksi.
  * Nilai lebih tinggi → ucapan lebih ekspresif dan bervariasi.

### Antarmuka Bersih & Dapat Diakses

* Sepenuhnya dapat diakses dengan pembaca layar.
* Opsi lanjutan ditempatkan di panel yang dapat disembunyikan agar dialog utama tetap sederhana dan fokus.

### Alur Kerja yang Mulus

* Audio diputar secara otomatis setelah dibuat.
* Audio yang dibuat dapat diputar ulang atau disimpan sebagai file `.wav` berkualitas tinggi.
* Dirancang untuk meminimalkan hambatan selama pembuatan dan pemutaran berulang.

### Pemuatan Suara Cerdas & Caching

* Suara yang tersedia diambil secara dinamis dari API Gemini.
* Data suara disimpan dalam cache selama **24 jam** untuk mengurangi panggilan API dan mempercepat waktu mulai.

### Bicara dengan AI (Percakapan Langsung)

* **Obrolan Suara Real-time**: Lakukan percakapan lisan yang alami dan latensi rendah dengan Gemini.
* **Grounding dengan Pencarian Google**: Mengaktifkan AI untuk mengakses informasi real-time dari web selama obrolan Anda.
* **Dapat Diinterupsi**: Anda dapat memotong pembicaraan AI kapan saja dengan berbicara atau menekan tombol "Hentikan Percakapan".
* **Dapat Disesuaikan**: Menggunakan suara dan instruksi gaya yang Anda pilih.

---

## Persyaratan

* NVDA (versi terbaru direkomendasikan).
* Koneksi internet aktif.
* **Kunci API Google Gemini** yang valid.

---

## Instalasi

1. Unduh paket add-on terbaru dari
   **Halaman Rilis:**
   [https://github.com/MuhammadGagah/native-speech-generation/releases](https://github.com/MuhammadGagah/native-speech-generation/releases)
2. Instal seperti add-on NVDA standar lainnya.
3. Mulai ulang NVDA saat diminta.

---

## Pengaturan Kunci API (Wajib)

1. Buat kunci API dari **Google AI Studio**:
   [https://aistudio.google.com/apikey](https://aistudio.google.com/apikey)
2. Buka NVDA dan pergi ke:
   **Menu NVDA → Alat → Native Speech Generation**
3. Klik **“Pengaturan Kunci API”**.
4. Ini membuka Pengaturan NVDA langsung di kategori *Native Speech Generation*.
5. Tempelkan **Kunci API Gemini** Anda ke dalam kolom *Kunci API Gemini*.
6. Klik **OK** untuk menyimpan.

---

## Cara Menggunakan

Buka dialog menggunakan:

* **NVDA+Control+Shift+G**, atau
* **Menu NVDA → Alat → Native Speech Generation**

### Elemen Antarmuka Utama

* **Teks untuk dikonversi**
  Masukkan atau tempel teks yang ingin Anda ubah menjadi ucapan.
* **Instruksi gaya (opsional)**
  Berikan panduan untuk nada, emosi, atau penyampaian.
* **Pilih Model**
  * Flash (Kualitas Standar)
  * Pro (Kualitas Tinggi)
* **Mode Pembicara**
  * Pembicara tunggal
  * Multi-pembicara (2)

---

## Menghasilkan Ucapan

### Mode Pembicara Tunggal

1. Pilih **Pembicara tunggal**.
2. Pilih suara dari menu dropdown *Pilih Suara*.
3. Masukkan teks Anda.
4. (Opsional) tambahkan instruksi gaya.
5. Klik **Hasilkan Ucapan**.
6. Audio akan diputar secara otomatis setelah pembuatan selesai.

---

### Mode Multi-Pembicara

1. Pilih **Multi-pembicara (2)**.
2. Untuk setiap pembicara:
   * Masukkan **Nama Pembicara** yang unik.
   * Pilih **Suara** yang berbeda.
3. Format teks sehingga setiap baris dimulai dengan nama pembicara diikuti oleh tanda titik dua.

**Contoh:**

```
Alice: Hai Bob, apa kabar hari ini?
Bob: Aku baik-baik saja, Alice! Cuacanya luar biasa.
```

4. Klik **Hasilkan Ucapan**.
   Suara akan ditetapkan secara otomatis berdasarkan nama pembicara.

---

## Bicara dengan AI (Mode Langsung)

Rasakan percakapan suara dua arah yang alami dengan Gemini.

1. Konfigurasikan **Suara** dan **Instruksi Gaya** yang diinginkan di dialog utama.
   *(Catatan: Bicara dengan AI saat ini hanya mendukung mode Pembicara Tunggal)*
2. Klik **Bicara dengan AI**.
3. Di jendela baru:
   * **Mulai Percakapan**: Memulai sesi. Bicaralah ke mikrofon Anda.
   * **Hentikan Percakapan**: Mengakhiri sesi.
   * **Grounding dengan Google Search**: Centang kotak ini untuk mengizinkan Gemini menelusuri web guna mencari jawaban (misalnya, berita terkini, cuaca).
     * *Catatan: Kotak centang ini disembunyikan saat percakapan sedang aktif. Hentikan percakapan untuk mengubahnya.*
   * **Tombol Mikrofon**: Bisukan/Bunyikan mikrofon Anda.
   * **Volume**: Sesuaikan volume pemutaran AI.

---

## Pengaturan Lanjutan

* Aktifkan **Pengaturan Lanjutan (Suhu)** untuk menampilkan slider.
* **Rentang Temperatur**:
  * `0.0` → Paling deterministik dan stabil.
  * `1.0` → Keseimbangan default.
  * `2.0` → Paling kreatif dan bervariasi.

---

## Tinjauan Tombol

* **Hasilkan Ucapan** - Mulai pembuatan ucapan.
* **Putar** - Memutar ulang audio yang terakhir dibuat.
* **Bicara dengan AI** - Buka antarmuka percakapan suara real-time.
* **Simpan Audio** - Simpan audio terakhir sebagai file `.wav`.
* **Pengaturan Kunci API** - Buka konfigurasi add-on di Pengaturan NVDA.
* **Lihat suara di AI Studio** - Membuka Google AI Studio di browser.
* **Tutup** - Tutup dialog (atau tekan `Escape`).

---

## Gestur Input

Dapat disesuaikan melalui:
**Menu NVDA → Preferensi → Gestur Input → Native Speech Generation**

Gestur default:

* **NVDA+Control+Shift+G** – Buka dialog Native Speech Generation.

---

## Panduan Pengembangan & Kontribusi

Jika Anda ingin mengembangkan atau memodifikasi add-on ini, ikuti langkah-langkah di bawah ini.

### Pengaturan Lingkungan

* **Python 32-bit (direkomendasikan 3.11.9)**
  [https://www.python.org/downloads/release/python-3119/](https://www.python.org/downloads/release/python-3119/)
* **SCons 4.9.1 atau lebih baru**

  ```
  pip install scons
  ```
* **Alat GNU Gettext** (opsional, disarankan untuk lokalisasi)
  * Biasanya sudah terinstal di Linux/Cygwin.
  * Windows: [https://gnuwin32.sourceforge.net/downlinks/gettext.php](https://gnuwin32.sourceforge.net/downlinks/gettext.php)
* **Markdown 3.8+** (untuk konversi dokumentasi)

  ```
  pip install markdown
  ```

### Ketergantungan Tambahan

Instal Gemini SDK dan pyaudio langsung ke jalur pustaka add-on:

```
python.exe -m pip install google-genai pyaudio --target "D:/myAdd-on/Native-Speech-Generation/addon/globalPlugins/NativeSpeechGeneration/lib"
```

Sesuaikan jalur dengan direktori sumber add-on lokal Anda.

Kemudian salin file berikut dari instalasi Python Anda ke dalam:

```
addon/globalPlugins/NativeSpeechGeneration/lib
```

* folder `zoneinfo`
* file `secrets.py`

---

## Berkontribusi

Kontribusi, saran, dan laporan bug sangat kami harapkan.

* Buka **Issue** untuk bug atau permintaan fitur.
* Kirim **Pull Request** untuk kontribusi kode.

**Kontak**

* Email: `muha.aku@gmail.com`
* GitHub: [https://github.com/MuhammadGagah](https://github.com/MuhammadGagah)
