# Native Speech Generation untuk NVDA

**Author:** Muhammad Gagah [muha.aku@gmail.com](mailto:muha.aku@gmail.com)

Native Speech Generation adalah add-on NVDA yang mengintegrasikan **Google Gemini AI** untuk menghasilkan suara alami berkualitas tinggi langsung di dalam NVDA.
Add-on ini menyediakan antarmuka yang bersih, sepenuhnya aksesibel, dan dirancang untuk mengubah teks menjadi audio, baik dalam bentuk **narasi satu pembicara** maupun **dialog multi-pembicara**.

Fokus utama add-on ini adalah workflow yang mulus, kemudahan akses bagi pengguna screen reader, serta kontrol suara yang fleksibel untuk berbagai kebutuhan seperti narasi, dialog, dan produksi audio.

---

## Fitur

### Generasi Suara Berkualitas Tinggi

* Pilihan model:

  * **Gemini Flash** – Kualitas standar, cepat, latensi rendah.
  * **Gemini Pro** – Kualitas premium dengan suara lebih realistis (berbayar).

### Mode Single & Multi-Speaker

* **Single-speaker** untuk text-to-speech standar.
* **Multi-speaker (2 pembicara)** untuk dialog dengan dua suara berbeda.

### Kontrol Suara Lanjutan

* **Penamaan Speaker**
  Pada mode multi-speaker, Anda dapat memberi nama unik (misalnya *John*, *Mary*).
  AI akan secara otomatis memetakan suara berdasarkan nama speaker di teks.
* **Instruksi Gaya Bicara**
  Tambahkan prompt seperti *“Bicara dengan nada ceria”* atau *“Narasi dengan suara tenang”*.
* **Kontrol Temperatur**
  Mengatur variasi dan kreativitas suara:

  * Nilai rendah → lebih stabil dan konsisten.
  * Nilai tinggi → lebih ekspresif dan bervariasi.

### Antarmuka Aksesibel & Rapi

* Semua kontrol sepenuhnya mendukung screen reader.
* Pengaturan lanjutan disembunyikan dalam panel yang dapat dibuka/tutup agar antarmuka utama tetap sederhana.

### Workflow Mulus

* Audio diputar otomatis setelah proses generate selesai.
* Audio terakhir dapat diputar ulang atau disimpan sebagai file `.wav` berkualitas tinggi.
* Cocok untuk penggunaan berulang tanpa banyak langkah tambahan.

### Pemanggilan & Cache Suara Pintar

* Daftar suara diambil langsung dari Gemini API.
* Data suara di-cache selama **24 jam** untuk mempercepat startup dan mengurangi pemanggilan API.

---

## Persyaratan

* NVDA (versi terbaru direkomendasikan).
* Koneksi internet aktif.
* **Google Gemini API Key** yang valid.

---

## Instalasi

1. Unduh add-on versi terbaru dari halaman
   **Releases:**
   [https://github.com/MuhammadGagah/native-speech-generation/releases](https://github.com/MuhammadGagah/native-speech-generation/releases)
2. Instal seperti add-on NVDA pada umumnya.
3. Restart NVDA setelah instalasi selesai.

---

## Pengaturan API Key (Wajib)

1. Buat API key melalui **Google AI Studio**:
   [https://aistudio.google.com/apikey](https://aistudio.google.com/apikey)
2. Buka NVDA lalu masuk ke:
   **Menu NVDA → Tools → Native Speech Generation**
3. Klik tombol **“API Key Settings”**.
4. NVDA Settings akan terbuka langsung pada kategori *Native Speech Generation*.
5. Tempelkan **Gemini API Key** Anda pada kolom *GEMINI API Key*.
6. Klik **OK** untuk menyimpan.

---

## Cara Menggunakan Add-on

Buka dialog Native Speech Generation dengan:

* **NVDA+Control+Shift+G**, atau
* **Menu NVDA → Tools → Native Speech Generation**

### Elemen Antarmuka Utama

* **Text to convert**
  Area teks utama untuk mengetik atau menempelkan teks.
* **Style instructions (opsional)**
  Digunakan untuk mengatur gaya dan ekspresi suara.
* **Select Model**

  * Flash (Kualitas Standar)
  * Pro (Kualitas Tinggi)
* **Speaker Mode**

  * Single-speaker
  * Multi-speaker (2)

---

## Menghasilkan Suara

### Mode Single-Speaker

1. Pilih **Single-speaker**.
2. Pilih suara dari dropdown *Select Voice*.
3. Masukkan teks.
4. Tambahkan instruksi gaya (opsional).
5. Klik **Generate Speech**.
6. Audio akan diputar otomatis setelah selesai.

---

### Mode Multi-Speaker

1. Pilih **Multi-speaker (2)**.
2. Untuk setiap speaker:

   * Isi **Speaker Name** dengan nama unik.
   * Pilih **Voice** yang berbeda.
3. Format teks dengan nama speaker di awal baris diikuti tanda titik dua.

**Contoh:**

```
Alice: Hai Bob, apa kabar hari ini?
Bob: Baik sekali, Alice. Cuacanya cerah!
```

4. Klik **Generate Speech**.
   AI akan membaca dialog dan mencocokkan suara berdasarkan nama speaker.

---

## Pengaturan Lanjutan

* Aktifkan **Advanced Settings (Temperature)** untuk menampilkan slider.
* **Rentang Temperature**:

  * `0.0` → Paling stabil dan deterministik.
  * `1.0` → Nilai default (seimbang).
  * `2.0` → Paling kreatif dan bervariasi.

---

## Fungsi Tombol

* **Generate Speech** – Memulai proses generasi suara.
* **Play** – Memutar ulang audio terakhir.
* **Save Audio** – Menyimpan audio terakhir ke file `.wav`.
* **API Key Settings** – Membuka pengaturan add-on di NVDA Settings.
* **View voices in AI Studio** – Membuka Google AI Studio di browser.
* **Close** – Menutup dialog (atau tekan `Escape`).

---

## Input Gesture

Dapat diubah melalui:
**Menu NVDA → Preferences → Input Gestures → Native Speech Generation**

Gesture bawaan:

* **NVDA+Control+Shift+G** – Membuka dialog Native Speech Generation.

---

## Panduan Pengembangan & Kontribusi

Jika Anda ingin mengembangkan atau memodifikasi add-on ini, ikuti langkah berikut.

### Persiapan Lingkungan

* **Python 32-bit (disarankan 3.11.9)**
  [https://www.python.org/downloads/release/python-3119/](https://www.python.org/downloads/release/python-3119/)
* **SCons 4.9.1 atau lebih baru**

  ```
  pip install scons
  ```
* **GNU Gettext Tools** (opsional, direkomendasikan untuk lokalisasi)

  * Biasanya sudah tersedia di Linux/Cygwin.
  * Windows: [https://gnuwin32.sourceforge.net/downlinks/gettext.php](https://gnuwin32.sourceforge.net/downlinks/gettext.php)
* **Markdown 3.8 atau lebih baru**

  ```
  pip install markdown
  ```

### Dependensi Tambahan

Install library Gemini langsung ke folder library add-on:

```
python.exe -m pip install google-genai --target "D:/myAdd-on/Native-Speech-Generation/addon/globalPlugins/lib"
```

Sesuaikan path dengan lokasi source add-on Anda.

Kemudian salin dari instalasi Python Anda ke:

```
addon/globalPlugins/lib
```

* Folder `zoneinfo`
* File `secrets.py`

---

## Kontribusi

Masukan, ide, dan laporan bug sangat diterima.

* Buat **Issue** untuk bug atau permintaan fitur.
* Kirim **Pull Request** untuk kontribusi kode.

**Kontak**

* Email: `muha.aku@gmail.com`
* GitHub: [https://github.com/MuhammadGagah](https://github.com/MuhammadGagah)
