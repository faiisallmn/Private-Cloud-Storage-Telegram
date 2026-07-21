import re
import base64
from flask import request, jsonify
from flask_jwt_extended import (
    create_access_token,
    jwt_required,
    get_jwt_identity,
    get_jwt,
)

from app import db
from database.models import User, RevokedToken
from auth import auth_bp
from crypto.aes import derive_user_key, encrypt_string


def is_token_revoked(jwt_header, jwt_payload):
    # Callback untuk flask-jwt-extended token_in_blocklist_loader.
    #
    # Query DB bukan in-memory set agar revokasi tetap valid setelah server restart.
    jti = jwt_payload['jti']
    return RevokedToken.query.filter_by(jti=jti).first() is not None


@auth_bp.route('/register', methods=['POST'])
def register():
    # Registrasi user baru. Body: {username, email, password}.
    data = request.get_json(silent=True)
    if not data:
        return jsonify({'error': 'Request body harus berupa JSON'}), 400

    username = data.get('username', '').strip()
    email = data.get('email', '').strip().lower()
    password = data.get('password', '')

    if not username or not email or not password:
        return jsonify({'error': 'Username, email, dan password wajib diisi'}), 400

    if len(username) < 3:
        return jsonify({'error': 'Username minimal 3 karakter'}), 400

    email_regex = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    if not re.match(email_regex, email):
        return jsonify({'error': 'Format email tidak valid'}), 400

    if len(password) < 8:
        return jsonify({'error': 'Password minimal 8 karakter'}), 400

    if User.query.filter_by(username=username).first():
        return jsonify({'error': 'Username sudah terdaftar'}), 409

    if User.query.filter_by(email=email).first():
        return jsonify({'error': 'Email sudah terdaftar'}), 409

    tg_api_id = data.get('api_id', '').strip()
    tg_api_hash = data.get('api_hash', '').strip()
    tg_chat_id = data.get('chat_id', '').strip()

    if not tg_api_id or not tg_api_hash or not tg_chat_id:
        return jsonify({'error': 'API ID, API Hash, dan Chat ID wajib diisi'}), 400

    user = User(username=username, email=email)
    user.set_password(password)
    
    # Derive encryption key from password and username
    derived_key = derive_user_key(password, username)
    
    user.tg_api_id_enc = encrypt_string(tg_api_id, derived_key)
    user.tg_api_hash_enc = encrypt_string(tg_api_hash, derived_key)
    user.tg_chat_id_enc = encrypt_string(tg_chat_id, derived_key)

    try:
        db.session.add(user)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Gagal menyimpan data: {str(e)}'}), 500

    return jsonify({
        'message': 'Registrasi berhasil',
        'user_id': user.id
    }), 201


@auth_bp.route('/login', methods=['POST'])
def login():
    # Login dan dapatkan JWT access token. Body: {username, password}.
    data = request.get_json(silent=True)
    if not data:
        return jsonify({'error': 'Request body harus berupa JSON'}), 400

    identifier = data.get('username', '').strip()
    password = data.get('password', '')

    if not identifier or not password:
        return jsonify({'error': 'Username/email dan password wajib diisi'}), 400

    user = User.query.filter(
        (User.username == identifier) | (User.email == identifier.lower())
    ).first()

    if not user or not user.check_password(password):
        return jsonify({'error': 'Username/email atau password salah'}), 401

    # Derive key and inject into JWT
    derived_key = derive_user_key(password, user.username)
    derived_key_b64 = base64.b64encode(derived_key).decode('utf-8')
    
    access_token = create_access_token(
        identity=str(user.id),
        additional_claims={'user_key': derived_key_b64}
    )

    return jsonify({
        'access_token': access_token,
        'user': {
            'id': user.id,
            'username': user.username,
            'email': user.email,
        }
    }), 200


@auth_bp.route('/logout', methods=['POST'])
@jwt_required()
def logout():
    # Logout dengan menyimpan JTI token ke tabel revoked_tokens.
    jti = get_jwt()['jti']

    try:
        revoked = RevokedToken(jti=jti)
        db.session.add(revoked)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Gagal logout: {str(e)}'}), 500

    return jsonify({'message': 'Logout berhasil'}), 200
