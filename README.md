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
   TELEGRAM_API_ID=masukkan_api_id_anda
   TELEGRAM_API_HASH=masukkan_api_hash_anda
   BOT_TOKEN=masukkan_bot_token_anda
   STORAGE_CHAT_ID=masukkan_chat_id_storage_anda
   SECRET_KEY=isi_dengan_string_acak_panjang
   JWT_SECRET_KEY=isi_dengan_string_acak_panjang
   ```
   > **Catatan:** `STORAGE_CHAT_ID` adalah ID unik dari Channel/Grup tempat file akan disembunyikan. Mulailah bot Anda dan tambahkan bot sebagai admin di grup/channel tersebut.

4. **Jalankan Aplikasi**
   Setelah semua setup selesai, jalankan server Flask:
   ```bash
   python app.py
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
