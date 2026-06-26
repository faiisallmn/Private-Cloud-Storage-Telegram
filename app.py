import os
from app import create_app

app = create_app()

if __name__ == '__main__':
    # Default False agar production aman walau FLASK_DEBUG tidak diset di .env
    debug = os.environ.get('FLASK_DEBUG', 'true').lower() == 'true'
    app.run(host='0.0.0.0', port=5000, debug=debug)
