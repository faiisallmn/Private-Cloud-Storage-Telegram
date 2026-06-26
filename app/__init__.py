import os
from flask import Flask, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_jwt_extended import JWTManager
from flask_cors import CORS
from dotenv import load_dotenv

db = SQLAlchemy()
jwt = JWTManager()
cors = CORS()


def create_app():
    # Factory function untuk membuat instance aplikasi Flask.

    load_dotenv()
    # Path template folder berada di root folder (sejajar dengan folder app/)
    app = Flask(__name__, template_folder='../templates', static_folder='../static')
    app.config.from_object('app.config.Config')

    upload_folder = app.config.get('UPLOAD_FOLDER', 'uploads')
    os.makedirs(upload_folder, exist_ok=True)

    db.init_app(app)
    jwt.init_app(app)

    # Daftarkan callback blocklist agar logout benar-benar me-revoke token
    from auth.routes import is_token_revoked
    jwt.token_in_blocklist_loader(is_token_revoked)

    # CORS dibatasi ke domain tertentu — wildcard * berbahaya di production
    allowed_origins = os.environ.get('CORS_ORIGINS', 'http://localhost:5000').split(',')
    cors.init_app(app, resources={r"/api/*": {"origins": allowed_origins}})

    @jwt.expired_token_loader
    def expired_token_callback(jwt_header, jwt_payload):
        return jsonify({'error': 'Token sudah expired, silakan login ulang'}), 401

    @jwt.invalid_token_loader
    def invalid_token_callback(error):
        return jsonify({'error': 'Token tidak valid'}), 401

    @jwt.revoked_token_loader
    def revoked_token_callback(jwt_header, jwt_payload):
        return jsonify({'error': 'Token sudah di-revoke (logout)'}), 401

    @jwt.unauthorized_loader
    def missing_token_callback(error):
        return jsonify({'error': 'Token autentikasi diperlukan'}), 401

    from auth.routes import auth_bp
    from storage.routes import storage_bp
    from flask import render_template
    from storage.telegram import TelegramStorage


    import werkzeug.serving
    if not app.debug or werkzeug.serving.is_running_from_reloader():
        app.telegram_storage = TelegramStorage(
            bot_token=app.config['BOT_TOKEN'],
            storage_chat_id=app.config.get('STORAGE_CHAT_ID', ''),
            api_id=app.config.get('TELEGRAM_API_ID', 0),
            api_hash=app.config.get('TELEGRAM_API_HASH', ''),
        )
    else:
        app.telegram_storage = None

    app.register_blueprint(auth_bp, url_prefix='/api/auth')
    app.register_blueprint(storage_bp, url_prefix='/api/files')

    # Frontend Routes
    @app.route('/')
    def index():
        return render_template('login.html')

    @app.route('/dashboard')
    def dashboard():
        return render_template('dashboard.html')

    with app.app_context():
        from database import models  # noqa: F401
        db.create_all()

    return app
