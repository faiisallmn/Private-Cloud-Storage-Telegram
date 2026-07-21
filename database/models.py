from datetime import datetime, timezone
from app import db
import bcrypt


class User(db.Model):
    # User untuk autentikasi dan kepemilikan file.

    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(256), nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    tg_api_id_enc = db.Column(db.String(512), nullable=True)
    tg_api_hash_enc = db.Column(db.String(512), nullable=True)
    tg_chat_id_enc = db.Column(db.String(512), nullable=True)

    files = db.relationship('FileMetadata', backref='owner', lazy='dynamic')
    folders = db.relationship('Folder', backref='owner', lazy='dynamic')

    def set_password(self, password: str) -> None:
        # Hash dan simpan password menggunakan bcrypt.
        self.password_hash = bcrypt.hashpw(
            password.encode('utf-8'),
            bcrypt.gensalt()
        ).decode('utf-8')

    def check_password(self, password: str) -> bool:
        # Verifikasi password terhadap hash yang tersimpan.
        return bcrypt.checkpw(
            password.encode('utf-8'),
            self.password_hash.encode('utf-8')
        )

    def __repr__(self):
        return f'<User {self.username}>'


class FileMetadata(db.Model):
    # Metadata file: enkripsi AES, chunking, dan referensi file_id Telegram.

    __tablename__ = 'file_metadata'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    filename = db.Column(db.String(255), nullable=False)
    original_filename = db.Column(db.String(255))
    file_size = db.Column(db.BigInteger)
    mime_type = db.Column(db.String(100))
    folder_path = db.Column(db.String(500), default='/')
    is_chunked = db.Column(db.Boolean, default=False)
    total_chunks = db.Column(db.Integer, default=1)
    sha256_hash = db.Column(db.String(64))
    aes_key_encrypted = db.Column(db.Text)
    aes_iv = db.Column(db.String(64))
    telegram_file_ids = db.Column(db.JSON)
    telegram_message_ids = db.Column(db.JSON)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    is_deleted = db.Column(db.Boolean, default=False)
    is_favorite = db.Column(db.Boolean, default=False)

    def __repr__(self):
        return f'<FileMetadata {self.original_filename}>'


class Folder(db.Model):
    # Folder virtual untuk mengorganisir file user.

    __tablename__ = 'folders'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    name = db.Column(db.String(255), nullable=False)
    parent_path = db.Column(db.String(500), default='/')
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    def __repr__(self):
        return f'<Folder {self.parent_path}{self.name}/>'


class RevokedToken(db.Model):
    # Persistent JWT blocklist — menggantikan in-memory set.

    __tablename__ = 'revoked_tokens'

    id = db.Column(db.Integer, primary_key=True)
    jti = db.Column(db.String(120), unique=True, nullable=False, index=True)
    revoked_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    def __repr__(self):
        return f'<RevokedToken jti={self.jti[:12]}... revoked_at={self.revoked_at}>'
