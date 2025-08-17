# Native Speech Generation for NVDA

**Author:** Muhammad Gagah <muha.aku@gmail.com>  

Add-on ini menghadirkan integrasi **Google Gemini AI** langsung di NVDA untuk menghasilkan suara alami berkualitas tinggi.  
Dengan antarmuka sederhana dan ramah pengguna, Anda dapat mengubah teks menjadi audio natural, baik untuk narasi tunggal maupun dialog multi-speaker.

---

## Fitur Utama

- **Suara Berkualitas Tinggi**  
  Pilih antara **Gemini Flash** (standar, cepat) atau **Gemini Pro** (premium, realistis).

- **Mode Narasi & Dialog**  
  - Narator tunggal.  
  - Dialog dinamis dengan 2 speaker berbeda.

- **Kontrol Suara Lanjutan**  
  - **Penamaan Speaker** → Assign nama unik seperti "John", "Mary".  
  - **Instruksi Gaya Bicara** → Misalnya: *"Bicara dengan nada ceria"*.  
  - **Kontrol Temperatur** → Atur variasi/keacakan output suara.

- **Antarmuka Aksesibel & Rapi**  
  Semua kontrol mendukung screen reader. Pengaturan lanjutan disembunyikan dalam panel khusus agar tetap simpel.

- **Workflow Mulus**  
  - Otomatis diputar setelah generate.  
  - Bisa di-*replay* atau disimpan ke `.wav`.  
  - Cache suara dari API selama 24 jam → startup lebih cepat.

---

## Download

Anda dapat mengunduh file add-on terbaru dari halaman [Releases]([https://github.com/muhammadGagah/native-speech-nvda/releases](https://github.com/MuhammadGagah/native-speech-generation/releases/)).  
Install seperti add-on NVDA biasa, lalu restart NVDA.

---

## Cara Mengembangkan Add-on

Jika ingin ikut mengembangkan add-on ini, Anda perlu menyiapkan beberapa tools dan dependensi:

### 1. Persiapan Lingkungan

- **Python 32-bit (3.11.9 disarankan)**  
  [Download di sini](https://www.python.org/downloads/release/python-3119/)

- **Scons 4.9.1 atau lebih baru**  
  Install via `pip install scons`.

- **GNU Gettext Tools** *(opsional tapi disarankan)*  
  Untuk mendukung lokalisasi add-on.  
  - Linux/Cygwin biasanya sudah terpasang.  
  - Untuk Windows: [Unduh di sini](https://gnuwin32.sourceforge.net/downlinks/gettext.php).

- **Markdown 3.8 atau lebih baru**  
  Jika ingin mengonversi dokumentasi `.md` ke HTML.  
  Install via `pip install markdown`.

### 2. Library & Dependensi Tambahan

Setelah Python & dependensi di atas siap, install library **google-genai**:  

```bash
python.exe -m pip install google-genai --target "D:/myAdd-on/Native-Speech-Generation/addon/globalPlugins/lib"
````

> Sesuaikan path dengan folder source code add-on Anda.

Kemudian, **copy**:

* Folder `zoneinfo`
* File `secrets.py`

dari instalasi Python Anda ke folder:

```
/addon/globalPlugins/lib
```

---

## Saran & Kontribusi

Kami sangat terbuka untuk ide, perbaikan, maupun laporan bug.

* Buat **Issue** jika menemukan masalah.
* Ajukan **Pull Request** untuk kontribusi kode.

📧 Kontak: `muha.aku@gmail.com`
🐙 GitHub: [muhammadGagah](https://github.com/muhammadGagah)

---

Terima kasih !
