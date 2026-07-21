# Gunicorn Configuration for Private Cloud Storage

bind = "0.0.0.0:5000"

# Sesi Pyrogram (SQLite) akan memicu error "database is locked" jika diakses bersamaan oleh banyak worker pada user yang sama.
workers = 1

# Menggunakan multiple threads agar bisa memproses banyak request
threads = 4

# Waktu timeout 
timeout = 120

worker_class = "gthread"
