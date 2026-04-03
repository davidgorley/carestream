import os
from flask import Flask, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from flask_socketio import SocketIO
from dotenv import load_dotenv

load_dotenv()

db = SQLAlchemy()
socketio = SocketIO(cors_allowed_origins="*", async_mode='threading')


def create_app():
    app = Flask(__name__, static_folder='static', static_url_path='')

    db_path = os.getenv('DB_PATH', '/carestream/data/carestream.db')
    os.makedirs(os.path.dirname(db_path), exist_ok=True)

    app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'carestream-secret')
    app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{db_path}'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['MAX_CONTENT_LENGTH'] = 2 * 1024 * 1024 * 1024  # 2GB max upload

    media_path = os.getenv('MEDIA_PATH', '/carestream/media')
    os.makedirs(media_path, exist_ok=True)
    app.config['MEDIA_PATH'] = media_path

    db.init_app(app)
    socketio.init_app(app)

    # Import and register blueprints
    from app.routes.rooms import rooms_bp
    from app.routes.media import media_bp
    from app.routes.playlists import playlists_bp
    from app.routes.push import push_bp
    from app.routes.settings import settings_bp

    app.register_blueprint(rooms_bp, url_prefix='/api/rooms')
    app.register_blueprint(media_bp, url_prefix='/api/media')
    app.register_blueprint(playlists_bp, url_prefix='/api/playlists')
    app.register_blueprint(push_bp, url_prefix='/api/push')
    app.register_blueprint(settings_bp, url_prefix='/api/settings')

    # Serve React frontend
    @app.route('/', defaults={'path': ''})
    @app.route('/<path:path>')
    def serve_frontend(path):
        # Check if file exists in static folder
        static_file = os.path.join(app.static_folder, path)
        if path and os.path.isfile(static_file):
            return send_from_directory(app.static_folder, path)
        return send_from_directory(app.static_folder, 'index.html')

    with app.app_context():
        from app.models import room, media, playlist  # noqa
        from app.models.settings import Settings
        db.create_all()

        # Initialize default timezone if not set
        if not Settings.get('timezone'):
            Settings.set('timezone', os.getenv('TZ', 'America/New_York'))

        # Start heartbeat service
        from app.services.heartbeat_service import start_heartbeat
        start_heartbeat(app)

    return app
