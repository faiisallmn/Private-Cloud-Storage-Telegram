import os
from datetime import timedelta
from dotenv import load_dotenv

load_dotenv()


class Config:
    # Konfigurasi utama aplikasi Flask.

    # set via ENV
    SECRET_KEY = os.environ.get('SECRET_KEY')
    if not SECRET_KEY:
        raise RuntimeError(
            'SECRET_KEY belum diset! '
            'Generate dengan: python -c "import secrets; print(secrets.token_hex(32))"'
        )
    MAX_CONTENT_LENGTH = 5 * 1024 * 1024 * 1024  # 5 GB

    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL', 'sqlite:///cloud_storage.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # set via ENV
    JWT_SECRET_KEY = os.environ.get('JWT_SECRET_KEY')
    if not JWT_SECRET_KEY:
        raise RuntimeError(
            'JWT_SECRET_KEY belum diset! '
            'Generate dengan: python -c "import secrets; print(secrets.token_hex(32))"'
        )
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=24)
    JWT_TOKEN_LOCATION = ['headers', 'query_string']
    JWT_QUERY_STRING_NAME = 'token'

    BOT_TOKEN = os.environ.get('BOT_TOKEN', '')

    CHUNK_SIZE_BYTES = int(os.environ.get('CHUNK_SIZE_BYTES', 1_800_000_000))

    UPLOAD_FOLDER = os.environ.get('UPLOAD_FOLDER', 'uploads')

    CORS_ORIGINS = os.environ.get('CORS_ORIGINS', 'http://localhost:5000')
