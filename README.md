# Private Cloud Storage (via Telegram MTProto)

Private Cloud Storage adalah aplikasi manajemen file berbasis web yang menjadikan Telegram sebagai media penyimpanan *cloud* tanpa batas berkat protokol MTProto. Dilengkapi dengan antarmuka yang modern menggunakan Tailwind CSS, perlindungan integritas file, enkripsi kelas militer (AES-256-CBC), serta fitur-fitur yang memudahkan manajemen file pribadi.

## ✨ Fitur Utama
- **Unlimited Storage**: Memanfaatkan Telegram untuk penyimpanan file gratis tanpa batas kapasitas.
- **Dukungan File Besar (Up to 2GB)**: Secara otomatis mendukung upload/download file hingga 2GB berkat *native* MTProto (Pyrogram) tanpa memerlukan Local Bot API Server / Docker.
- **Enkripsi AES-256-CBC**: Setiap file dienkripsi secara independen di sisi server (dengan *key* dan IV unik) sebelum dikirim ke server Telegram, memastikan tidak ada pihak ketiga yang dapat membaca isinya.
- **Integritas SHA-256**: Mencegah dan mendeteksi kerusakan file melalui perhitungan hash kriptografis SHA-256.
- **Modern Dashboard**: Antarmuka web ringan yang dinamis menggunakan *Vanilla Javascript* dan modern *Tailwind CSS*. 
- **Folder & Organisasi**: Mendukung pembuatan folder, navigasi *breadcrumb*, serta penandaan file Favorit dan riwayat Baru-baru Ini.

## 🛠 Prasyarat Sistem
- **Python 3.9** atau lebih baru
- Kredensial API Telegram (`API_ID` & `API_HASH` dari my.telegram.org)
- Bot Token Telegram (didapatkan dari **@BotFather**)
- Channel / Group Telegram Privat (sebagai *Storage*)

## 🚀 Cara Instalasi

1. **Clone dan Setup Virtual Environment**
   Buka terminal di dalam folder proyek Anda, lalu jalankan:
   ```bash
   python -m venv .venv
   ```
   Aktivasi virtual environment:
   - Windows: `.venv\Scripts\activate`
   - Mac/Linux: `source .venv/bin/activate`

2. **Instal Dependensi**
   Pastikan Anda menginstal seluruh pustaka yang diperlukan:
   ```bash
   pip install -r requirements.txt
   ```

3. **Konfigurasi Environment Variable**
   Ubah nama file `.env.example` menjadi `.env` dan isi kredensial berikut:
   ```env
   BOT_TOKEN=masukkan_bot_token_anda
   SECRET_KEY=isi_dengan_string_acak_panjang
   JWT_SECRET_KEY=isi_dengan_string_acak_panjang
   ```
   > **Catatan:** Untuk konfigurasi Telegram yang spesifik seperti `TELEGRAM_API_ID`, `TELEGRAM_API_HASH`, dan `STORAGE_CHAT_ID`, Anda tidak perlu lagi mengisinya di `.env`. Aplikasi ini mendukung sistem *multi-user*, di mana setiap pendaftar akan menginput kredensial Telegram masing-masing di form **Register** melalui antarmuka web. Kredensial akan dienkripsi secara aman di database.

4. **Jalankan Aplikasi**
   Terdapat beberapa cara untuk menjalankan server, pilih sesuai dengan lingkungan Anda:
   
   **A. Mode Development (Testing UI Dasar)**
   ```bash
   python app.py
   ```

   **B. Mode Production di Windows (Sangat Disarankan untuk Testing Anda Sekarang)**
   ```bash
   waitress-serve --port=5000 --threads=4 --call app:create_app
   ```

   tunning waitress ( windows )
   ```bash
   waitress-serve --port=5000 --threads=4 --recv-bytes=1048576 --inbuf-overflow=104857600 --call app:create_app
   ```

   **C. Mode Production di Linux VPS (Gunicorn)**
   ```bash
   gunicorn -c gunicorn.conf.py "app:create_app()"
   ```

5. **Akses Dashboard**
   Buka browser dan navigasikan ke: [http://localhost:5000](http://localhost:5000)
   
## 📂 Arsitektur Kode
- `app.py`: Titik masuk utama aplikasi.
- `app/__init__.py`: Factory aplikasi Flask dan konfigurasi dasar.
- `storage/telegram.py`: Otak utama yang mengendalikan interaksi unggah dan unduh ke Telegram via Pyrogram.
- `crypto/aes.py`: Logika enkripsi kelas militer (AES-256).
- `database/models.py`: Skema basis data (SQLite) untuk user, riwayat, dan relasi folder.
- `static/` & `templates/`: Sisi antarmuka (Front-End) berbasis Tailwind CSS.

## 🔒 Keamanan
- Semua kata sandi pengguna di-*hash* menggunakan `bcrypt`.
- Autentikasi sesi dienkripsi dengan JSON Web Tokens (`JWT`).
- Master-key AES di-enkripsi di level basis data, dan kunci unik per file diamankan sedemikian rupa sehingga pembobolan Telegram semata tidak akan membocorkan data pengguna.
