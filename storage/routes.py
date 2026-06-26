import io
import json
import logging
import hashlib

from flask import Blueprint, request, jsonify, current_app, send_file, Response
from flask_jwt_extended import jwt_required, get_jwt_identity

from app import db
from database.models import FileMetadata, Folder
from crypto.aes import AESCipher, encrypt_key, decrypt_key
from storage.chunking import FileChunker
from storage.telegram import TelegramStorage, TelegramUploadError

storage_bp = Blueprint('storage', __name__, url_prefix='/api/files')
logger = logging.getLogger(__name__)


def _get_telegram_client() -> TelegramStorage:
    return current_app.telegram_storage


@storage_bp.route('/upload', methods=['POST'])
@jwt_required()
def upload_file():
    # Upload file dengan enkripsi AES-256 dan simpan ke Telegram.
    #
    # Form-data: file (required), folder_path (optional, default "/")
    user_id = int(get_jwt_identity())

    if 'file' not in request.files:
        return jsonify({'error': 'Tidak ada file dalam request'}), 400

    uploaded_file = request.files['file']

    if uploaded_file.filename == '' or uploaded_file.filename is None:
        return jsonify({'error': 'Nama file kosong'}), 400

    folder_path = request.form.get('folder_path', '/').strip()

    # Normalisasi path dan cegah path traversal (/../../../etc/passwd)
    import posixpath
    folder_path = posixpath.normpath(folder_path)
    if '..' in folder_path.split('/'):
        return jsonify({'error': 'Path tidak valid'}), 400
    if not folder_path.startswith('/'):
        folder_path = '/' + folder_path
    if folder_path != '/' and not folder_path.endswith('/'):
        folder_path += '/'

    try:
        file_bytes = uploaded_file.read()
    except Exception as e:
        logger.error('Gagal membaca file: %s', e)
        return jsonify({'error': f'Gagal membaca file: {str(e)}'}), 500

    file_size = len(file_bytes)
    original_filename = uploaded_file.filename
    mime_type = uploaded_file.content_type or 'application/octet-stream'

    if file_size == 0:
        return jsonify({'error': 'File kosong (0 bytes)'}), 400

    max_size = current_app.config.get('MAX_CONTENT_LENGTH')
    if max_size and file_size > max_size:
        return jsonify({
            'error': f'File terlalu besar. Maksimal {max_size / (1024**3):.1f} GB'
        }), 413

    logger.info(
        'Upload dimulai — user=%d, file=%s, size=%.2f MB',
        user_id, original_filename, file_size / (1024 * 1024)
    )

    # SHA-256 dihitung sebelum enkripsi agar hash merepresentasikan file asli bukan ciphertext
    cipher = AESCipher()
    hasher = hashlib.sha256()
    hasher.update(file_bytes)
    sha256_hash = hasher.hexdigest()

    logger.debug('SHA-256: %s', sha256_hash)

    try:
        tg = _get_telegram_client()
    except Exception as e:
        logger.error('Gagal inisialisasi Telegram client: %s', e)
        return jsonify({'error': 'Konfigurasi Telegram tidak valid'}), 500

    chunk_size_mb_str = request.form.get('chunk_size_mb')
    if chunk_size_mb_str and chunk_size_mb_str.isdigit():
        chunk_size_mb = int(chunk_size_mb_str)
        chunk_size_mb = min(max(chunk_size_mb, 1), 1800) # Batas 1-1800 MB
        chunk_size = chunk_size_mb * 1024 * 1024
    else:
        chunk_size = current_app.config.get('CHUNK_SIZE_BYTES', 1_800_000_000)
        
    chunker = FileChunker(chunk_size=chunk_size)
    master_key = current_app.config['SECRET_KEY']

    if not chunker.should_chunk(file_size):
        # File kecil (≤ 1.8 GB): single upload
        try:
            aes_key = cipher.generate_key()
            aes_iv = cipher.generate_iv()
            encrypted_bytes = cipher.encrypt_file(file_bytes, aes_key, aes_iv)
        except Exception as e:
            logger.error('Enkripsi gagal: %s', e)
            return jsonify({'error': f'Enkripsi gagal: {str(e)}'}), 500

        try:
            file_id, message_id = tg.upload_file(encrypted_bytes, original_filename)
        except TelegramUploadError as e:
            logger.error('Upload Telegram gagal: %s', e)
            return jsonify({'error': f'Upload ke Telegram gagal: {str(e)}'}), 500

        aes_key_encrypted = encrypt_key(aes_key, master_key)

        try:
            file_record = FileMetadata(
                user_id=user_id,
                filename=original_filename,
                original_filename=original_filename,
                file_size=file_size,
                mime_type=mime_type,
                folder_path=folder_path,
                is_chunked=False,
                total_chunks=1,
                sha256_hash=sha256_hash,
                aes_key_encrypted=aes_key_encrypted,
                aes_iv=aes_iv.hex(),
                telegram_file_ids=[file_id],
                telegram_message_ids=[message_id],
            )
            db.session.add(file_record)
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            logger.error('Gagal simpan metadata: %s', e)
            return jsonify({'error': f'Gagal menyimpan metadata: {str(e)}'}), 500

        logger.info(
            'Upload berhasil (single) — db_id=%d, file=%s',
            file_record.id, original_filename
        )

    else:
        # File besar (> 1.8 GB): chunked upload, setiap chunk key & IV berbeda
        raw_chunks = chunker.split_file(file_bytes)
        total_chunks = len(raw_chunks)

        logger.info(
            'File di-chunk — %d chunks, chunk_size=%.2f MB',
            total_chunks, chunk_size / (1024 * 1024)
        )

        try:
            encrypted_chunk_list = chunker.encrypt_chunks(raw_chunks)
        except Exception as e:
            logger.error('Enkripsi chunk gagal: %s', e)
            return jsonify({'error': f'Enkripsi chunk gagal: {str(e)}'}), 500

        telegram_file_ids = []
        telegram_message_ids = []
        chunk_keys_data = []

        for chunk_info in encrypted_chunk_list:
            idx = chunk_info['chunk_index']
            try:
                file_id, message_id = tg.upload_chunk(
                    chunk_bytes=chunk_info['encrypted_bytes'],
                    chunk_index=idx,
                    original_filename=original_filename,
                )
                telegram_file_ids.append(file_id)
                telegram_message_ids.append(message_id)

                chunk_key_bytes = bytes.fromhex(chunk_info['key_hex'])
                chunk_keys_data.append({
                    'chunk_index': idx,
                    'key_encrypted': encrypt_key(chunk_key_bytes, master_key),
                    'iv_hex': chunk_info['iv_hex'],
                    'sha256': chunk_info['sha256_hash'],
                    'original_size': chunk_info['original_size'],
                })

                logger.info('Chunk %d/%d uploaded — file_id=%s...', idx + 1, total_chunks, file_id[:20])

            except TelegramUploadError as e:
                logger.error('Upload chunk %d gagal: %s', idx, e)
                return jsonify({
                    'error': f'Upload chunk {idx} ke Telegram gagal: {str(e)}',
                    'uploaded_chunks': len(telegram_file_ids),
                    'total_chunks': total_chunks,
                }), 500

        try:
            file_record = FileMetadata(
                user_id=user_id,
                filename=original_filename,
                original_filename=original_filename,
                file_size=file_size,
                mime_type=mime_type,
                folder_path=folder_path,
                is_chunked=True,
                total_chunks=total_chunks,
                sha256_hash=sha256_hash,
                aes_key_encrypted=json.dumps(chunk_keys_data),
                aes_iv=None,
                telegram_file_ids=telegram_file_ids,
                telegram_message_ids=telegram_message_ids,
            )
            db.session.add(file_record)
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            logger.error('Gagal simpan metadata chunked: %s', e)
            return jsonify({'error': f'Gagal menyimpan metadata: {str(e)}'}), 500

        logger.info(
            'Upload berhasil (chunked) — db_id=%d, file=%s, chunks=%d',
            file_record.id, original_filename, total_chunks
        )

    return jsonify({
        'message': 'Upload berhasil',
        'file_id': file_record.id,
        'filename': original_filename,
        'file_size': file_size,
        'sha256': sha256_hash,
        'is_chunked': file_record.is_chunked,
        'total_chunks': file_record.total_chunks,
    }), 201


@storage_bp.route('/download/<int:file_id>', methods=['GET'])
@jwt_required()
def download_file(file_id):
    # Download file: dekripsi AES-256 + verifikasi integritas SHA-256.
    user_id = int(get_jwt_identity())

    file_record = FileMetadata.query.filter_by(
        id=file_id, is_deleted=False
    ).first()

    if not file_record:
        return jsonify({'error': 'File tidak ditemukan'}), 404

    if file_record.user_id != user_id:
        return jsonify({'error': 'Anda tidak memiliki akses ke file ini'}), 403

    logger.info(
        'Download dimulai — user=%d, file=%s, chunked=%s',
        user_id, file_record.original_filename, file_record.is_chunked
    )

    try:
        tg = _get_telegram_client()
    except Exception as e:
        logger.error('Gagal inisialisasi Telegram client: %s', e)
        return jsonify({'error': 'Konfigurasi Telegram tidak valid'}), 500

    cipher = AESCipher()
    master_key = current_app.config['SECRET_KEY']

    def generate():
        # Generator yang meng-yield data terdekripsi dari Telegram.
        downloaded = 0
        total = file_record.file_size

        if not file_record.is_chunked:
            telegram_file_id = file_record.telegram_file_ids[0]
            try:
                aes_key = decrypt_key(file_record.aes_key_encrypted, master_key)
                aes_iv = bytes.fromhex(file_record.aes_iv)

                stream = tg.download_file_stream(telegram_file_id)
                for plaintext_chunk in cipher.stream_decrypt_file(stream, aes_key, aes_iv):
                    downloaded += len(plaintext_chunk)
                    pct = int((downloaded / total) * 100) if total else 0
                    logger.info(
                        'Download progress %s: %d%% (%.1f / %.1f MB)',
                        file_record.original_filename, pct,
                        downloaded / (1024*1024), total / (1024*1024)
                    )
                    yield plaintext_chunk

            except TelegramUploadError as e:
                logger.error('Download stream Telegram gagal: %s', e)
                raise
            except Exception as e:
                logger.error('Dekripsi stream gagal: %s', e)
                raise
        else:
            chunk_keys_data = json.loads(file_record.aes_key_encrypted)
            chunk_keys_data.sort(key=lambda c: c['chunk_index'])
            telegram_ids = file_record.telegram_file_ids

            if len(telegram_ids) != file_record.total_chunks:
                logger.error('Jumlah chunk di Telegram tidak sesuai metadata')
                raise ValueError('Inkonsistensi metadata chunk')

            for i, chunk_meta in enumerate(chunk_keys_data):
                idx = chunk_meta['chunk_index']
                try:
                    chunk_key = decrypt_key(chunk_meta['key_encrypted'], master_key)
                    chunk_iv = bytes.fromhex(chunk_meta['iv_hex'])

                    stream = tg.download_file_stream(telegram_ids[idx])
                    for plaintext_chunk in cipher.stream_decrypt_file(stream, chunk_key, chunk_iv):
                        downloaded += len(plaintext_chunk)
                        yield plaintext_chunk

                    pct = int((downloaded / total) * 100) if total else 0
                    logger.info(
                        'Chunk %d/%d selesai — total progress %d%% (%.1f / %.1f MB)',
                        idx + 1, file_record.total_chunks, pct,
                        downloaded / (1024*1024), total / (1024*1024)
                    )
                except Exception as e:
                    logger.error('Streaming chunk %d gagal: %s', idx, e)
                    raise

        logger.info('Download selesai — %s (%.1f MB)', file_record.original_filename, downloaded / (1024*1024))

    # Kirimkan header response SEGERA agar browser langsung menampilkan popup download.
    # Data akan mengalir secara bertahap melalui generator di atas.
    from flask import Response, stream_with_context
    headers = {
        'Content-Disposition': f'attachment; filename="{file_record.original_filename}"',
        'Content-Length': str(file_record.file_size),
        'X-Accel-Buffering': 'no',
        'Cache-Control': 'no-cache',
    }

    return Response(
        stream_with_context(generate()),
        headers=headers,
        mimetype=file_record.mime_type or 'application/octet-stream',
        direct_passthrough=True,
    )


@storage_bp.route('/list', methods=['GET'])
@jwt_required()
def list_files():
    # List file dan folder milik user di folder tertentu. Query param: folder (default "/").
    user_id = int(get_jwt_identity())
    folder_path = request.args.get('folder', '/').strip()

    import posixpath
    folder_path = posixpath.normpath(folder_path)
    if not folder_path.startswith('/'):
        folder_path = '/' + folder_path
    if folder_path != '/' and not folder_path.endswith('/'):
        folder_path += '/'

    files = FileMetadata.query.filter_by(
        user_id=user_id,
        folder_path=folder_path,
        is_deleted=False,
    ).order_by(FileMetadata.created_at.desc()).all()

    folders = Folder.query.filter_by(
        user_id=user_id,
        parent_path=folder_path,
    ).order_by(Folder.name.asc()).all()

    files_data = [{
        'id': f.id,
        'filename': f.original_filename,
        'file_size': f.file_size,
        'mime_type': f.mime_type,
        'is_chunked': f.is_chunked,
        'total_chunks': f.total_chunks,
        'sha256': f.sha256_hash,
        'is_favorite': f.is_favorite,
        'created_at': f.created_at.isoformat() if f.created_at else None,
    } for f in files]

    folders_data = [{
        'id': fld.id,
        'name': fld.name,
        'path': f'{fld.parent_path}{fld.name}/' if fld.parent_path == '/' else f'{fld.parent_path}/{fld.name}/',
        'created_at': fld.created_at.isoformat() if fld.created_at else None,
    } for fld in folders]

    return jsonify({
        'folder_path': folder_path,
        'files': files_data,
        'folders': folders_data,
        'total_files': len(files_data),
        'total_folders': len(folders_data),
    }), 200


@storage_bp.route('/<int:file_id>', methods=['DELETE'])
@jwt_required()
def delete_file(file_id):
    # Soft delete file (set is_deleted=True). File tetap ada di Telegram.
    user_id = int(get_jwt_identity())

    file_record = FileMetadata.query.filter_by(
        id=file_id, is_deleted=False
    ).first()

    if not file_record:
        return jsonify({'error': 'File tidak ditemukan'}), 404

    if file_record.user_id != user_id:
        return jsonify({'error': 'Anda tidak memiliki akses ke file ini'}), 403

    try:
        tg = _get_telegram_client()
        if file_record.telegram_message_ids:
            for msg_id in file_record.telegram_message_ids:
                try:
                    tg.delete_file(msg_id)
                except Exception as e:
                    logger.warning('Gagal menghapus pesan Telegram %s: %s', msg_id, e)
                    
        file_record.is_deleted = True
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        logger.error('Gagal delete file: %s', e)
        return jsonify({'error': f'Gagal menghapus file: {str(e)}'}), 500

    logger.info('File soft-deleted — id=%d, file=%s', file_id, file_record.original_filename)

    return jsonify({
        'message': f'File "{file_record.original_filename}" berhasil dihapus',
    }), 200


@storage_bp.route('/recent', methods=['GET'])
@jwt_required()
def recent_files():
    # Daftar 20 file terbaru milik user, dari semua folder.
    user_id = int(get_jwt_identity())
    files = FileMetadata.query.filter_by(
        user_id=user_id, is_deleted=False
    ).order_by(FileMetadata.created_at.desc()).limit(20).all()

    results = [{
        'id': f.id,
        'filename': f.original_filename,
        'file_size': f.file_size,
        'mime_type': f.mime_type,
        'folder_path': f.folder_path,
        'is_chunked': f.is_chunked,
        'is_favorite': f.is_favorite,
        'sha256': f.sha256_hash,
        'created_at': f.created_at.isoformat() if f.created_at else None,
    } for f in files]

    return jsonify({'files': results, 'total': len(results)}), 200


@storage_bp.route('/favorites', methods=['GET'])
@jwt_required()
def favorite_files():
    # Daftar file favorit milik user.
    user_id = int(get_jwt_identity())
    files = FileMetadata.query.filter_by(
        user_id=user_id, is_deleted=False, is_favorite=True
    ).order_by(FileMetadata.created_at.desc()).all()

    results = [{
        'id': f.id,
        'filename': f.original_filename,
        'file_size': f.file_size,
        'mime_type': f.mime_type,
        'folder_path': f.folder_path,
        'is_chunked': f.is_chunked,
        'is_favorite': f.is_favorite,
        'sha256': f.sha256_hash,
        'created_at': f.created_at.isoformat() if f.created_at else None,
    } for f in files]

    return jsonify({'files': results, 'total': len(results)}), 200


@storage_bp.route('/<int:file_id>/favorite', methods=['PUT'])
@jwt_required()
def toggle_favorite(file_id):
    # Toggle status favorit sebuah file.
    user_id = int(get_jwt_identity())
    file_record = FileMetadata.query.filter_by(
        id=file_id, user_id=user_id, is_deleted=False
    ).first()

    if not file_record:
        return jsonify({'error': 'File tidak ditemukan'}), 404

    try:
        file_record.is_favorite = not file_record.is_favorite
        db.session.commit()
        return jsonify({
            'message': 'Favorit diperbarui',
            'is_favorite': file_record.is_favorite
        }), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@storage_bp.route('/folders/all', methods=['GET'])
@jwt_required()
def get_all_folders():
    # Dapatkan daftar semua folder milik user.
    user_id = int(get_jwt_identity())
    folders = Folder.query.filter_by(user_id=user_id).order_by(Folder.parent_path, Folder.name).all()
    
    results = []
    for f in folders:
        full_path = f'{f.parent_path}{f.name}/' if f.parent_path == '/' else f'{f.parent_path}/{f.name}/'
        results.append({
            'id': f.id,
            'name': f.name,
            'path': full_path
        })
    return jsonify({'folders': results}), 200


@storage_bp.route('/folders', methods=['POST'])
@jwt_required()
def create_folder():
    # Buat folder virtual baru. Body: {name, parent_path (optional, default "/")}.
    user_id = int(get_jwt_identity())
    data = request.get_json(silent=True)

    if not data:
        return jsonify({'error': 'Request body harus berupa JSON'}), 400

    name = data.get('name', '').strip()
    parent_path = data.get('parent_path', '/').strip()

    if not name:
        return jsonify({'error': 'Nama folder wajib diisi'}), 400

    forbidden = ['/', '\\', '..', '\0']
    if any(c in name for c in forbidden):
        return jsonify({'error': 'Nama folder mengandung karakter tidak valid'}), 400

    if not parent_path.startswith('/'):
        parent_path = '/' + parent_path

    existing = Folder.query.filter_by(
        user_id=user_id,
        name=name,
        parent_path=parent_path,
    ).first()

    if existing:
        return jsonify({'error': f'Folder "{name}" sudah ada di {parent_path}'}), 409

    try:
        folder = Folder(
            user_id=user_id,
            name=name,
            parent_path=parent_path,
        )
        db.session.add(folder)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        logger.error('Gagal buat folder: %s', e)
        return jsonify({'error': f'Gagal membuat folder: {str(e)}'}), 500

    full_path = f'{parent_path}{name}/' if parent_path == '/' else f'{parent_path}/{name}/'
    logger.info('Folder dibuat — user=%d, path=%s', user_id, full_path)

    return jsonify({
        'message': f'Folder "{name}" berhasil dibuat',
        'folder': {
            'id': folder.id,
            'name': folder.name,
            'path': full_path,
            'created_at': folder.created_at.isoformat() if folder.created_at else None,
        },
    }), 201


@storage_bp.route('/search', methods=['GET'])
@jwt_required()
def search_files():
    # Cari file berdasarkan nama (case-insensitive, partial match). Query param: q (required).
    user_id = int(get_jwt_identity())
    query = request.args.get('q', '').strip()

    if not query:
        return jsonify({'error': 'Parameter pencarian "q" wajib diisi'}), 400

    # Escape wildcard LIKE agar user tidak bisa input '%' untuk match semua file
    # atau '_' sebagai single-char wildcard — keduanya bocorkan nama file orang lain
    safe_query = (
        query
        .replace('\\', '\\\\')
        .replace('%', '\\%')
        .replace('_', '\\_')
    )

    files = FileMetadata.query.filter(
        FileMetadata.user_id == user_id,
        FileMetadata.is_deleted == False,  # noqa: E712
        FileMetadata.original_filename.ilike(f'%{safe_query}%', escape='\\'),
    ).order_by(FileMetadata.created_at.desc()).all()

    results = [{
        'id': f.id,
        'filename': f.original_filename,
        'file_size': f.file_size,
        'mime_type': f.mime_type,
        'folder_path': f.folder_path,
        'is_chunked': f.is_chunked,
        'is_favorite': f.is_favorite,
        'sha256': f.sha256_hash,
        'created_at': f.created_at.isoformat() if f.created_at else None,
    } for f in files]

    return jsonify({
        'query': query,
        'results': results,
        'total': len(results),
    }), 200

@storage_bp.route('/folders/<int:folder_id>', methods=['DELETE'])
@jwt_required()
def delete_folder(folder_id):
    # Hapus folder virtual jika kosong.
    user_id = int(get_jwt_identity())
    
    folder = Folder.query.filter_by(id=folder_id, user_id=user_id).first()
    if not folder:
        return jsonify({'error': 'Folder tidak ditemukan'}), 404

    full_path = f'{folder.parent_path}{folder.name}/' if folder.parent_path == '/' else f'{folder.parent_path}/{folder.name}/'

    has_files = FileMetadata.query.filter(
        FileMetadata.user_id == user_id,
        FileMetadata.is_deleted == False,
        FileMetadata.folder_path.startswith(full_path)
    ).first()
    
    has_folders = Folder.query.filter(
        Folder.user_id == user_id,
        Folder.parent_path.startswith(full_path)
    ).first()

    if has_files or has_folders:
        return jsonify({'error': 'Folder tidak kosong, pindahkan atau hapus isinya terlebih dahulu'}), 400

    try:
        db.session.delete(folder)
        db.session.commit()
        return jsonify({'message': f'Folder "{folder.name}" berhasil dihapus'}), 200
    except Exception as e:
        db.session.rollback()
        logger.error('Gagal hapus folder: %s', e)
        return jsonify({'error': f'Gagal menghapus folder: {str(e)}'}), 500


@storage_bp.route('/<int:file_id>/move', methods=['PUT'])
@jwt_required()
def move_file(file_id):
    # Pindahkan file ke folder lain.
    user_id = int(get_jwt_identity())
    data = request.get_json(silent=True)
    if not data:
        return jsonify({'error': 'Request body JSON wajib ada'}), 400

    new_folder_path = data.get('folder_path', '/').strip()
    
    if not new_folder_path.startswith('/'):
        new_folder_path = '/' + new_folder_path
        
    import posixpath
    new_folder_path = posixpath.normpath(new_folder_path)
    if new_folder_path != '/' and not new_folder_path.endswith('/'):
        new_folder_path += '/'
        
    if new_folder_path != '/':
        parts = new_folder_path.strip('/').split('/')
        if len(parts) > 0:
            target_name = parts[-1]
            parent_path = '/' + '/'.join(parts[:-1]) + '/' if len(parts) > 1 else '/'
            target_folder = Folder.query.filter_by(
                user_id=user_id,
                name=target_name,
                parent_path=parent_path
            ).first()
            if not target_folder:
                return jsonify({'error': 'Folder tujuan tidak valid atau tidak ditemukan'}), 404

    file_record = FileMetadata.query.filter_by(id=file_id, user_id=user_id, is_deleted=False).first()
    if not file_record:
        return jsonify({'error': 'File tidak ditemukan'}), 404

    if file_record.folder_path == new_folder_path:
        return jsonify({'message': 'File sudah berada di folder tersebut'}), 200

    try:
        file_record.folder_path = new_folder_path
        db.session.commit()
        return jsonify({'message': 'File berhasil dipindahkan'}), 200
    except Exception as e:
        db.session.rollback()
        logger.error('Gagal memindahkan file: %s', e)
        return jsonify({'error': f'Gagal memindahkan file: {str(e)}'}), 500
