import os
import socket
from flask import Blueprint, request, jsonify, current_app
from dotenv import dotenv_values
from app import db
from app.models.settings import Settings

settings_bp = Blueprint('settings', __name__)

# Valid timezones
VALID_TIMEZONES = [
    'America/New_York',
    'America/Chicago',
    'America/Denver',
    'America/Los_Angeles',
    'America/Anchorage',
    'Pacific/Honolulu',
    'UTC',
    'Europe/London',
    'Europe/Paris',
    'Europe/Berlin',
    'Asia/Tokyo',
    'Asia/Shanghai',
    'Asia/Hong_Kong',
    'Asia/Bangkok',
    'Asia/Singapore',
    'Australia/Sydney',
    'Australia/Brisbane',
    'Australia/Melbourne'
]

def get_env_file_path_for_reading():
    """Find existing .env file for reading."""
    possible_paths = [
        '/app/.env',  # Docker container path
        os.path.join(os.path.expanduser('~'), '.carestream', '.env'),  # Home directory
        '.env',  # Current directory
    ]
    
    for path in possible_paths:
        if os.path.exists(path) and os.path.isfile(path):
            return path
    return None

def get_env_file_path_for_writing():
    """Find or create writable .env file."""
    # Priority: use existing file location, then try to find writable location
    existing = get_env_file_path_for_reading()
    if existing:
        return existing
    
    # Try to write to current directory
    try:
        test_path = '.env'
        if os.access(os.path.dirname(test_path) or '.', os.W_OK):
            return test_path
    except Exception:
        pass
    
    # Try home directory
    try:
        home_dir = os.path.expanduser('~')
        carestream_dir = os.path.join(home_dir, '.carestream')
        os.makedirs(carestream_dir, exist_ok=True)
        return os.path.join(carestream_dir, '.env')
    except Exception:
        pass
    
    # Last resort: /app/.env (Docker)
    try:
        os.makedirs('/app', exist_ok=True)
        return '/app/.env'
    except Exception:
        pass
    
    # Fallback
    return '.env'

def get_server_ip():
    """Get the actual server IP address."""
    try:
        # Try to get from environment first
        env_ip = os.environ.get('SERVER_IP')
        if env_ip and env_ip != '0.0.0.0':
            return env_ip
        
        # Try to get actual network IP
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            # Connect to a public DNS server (doesn't actually send data)
            s.connect(('8.8.8.8', 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except Exception:
            s.close()
            return socket.gethostbyname(socket.gethostname())
    except Exception:
        return '127.0.0.1'

@settings_bp.route('', methods=['GET'])
def get_settings():
    """Get current settings from environment and .env file."""
    env_file = get_env_file_path_for_reading()
    config = {}
    if env_file and os.path.exists(env_file):
        config = dotenv_values(env_file)
    
    return jsonify({
        'SERVER_IP': config.get('SERVER_IP') or os.environ.get('SERVER_IP') or get_server_ip(),
        'ADB_PORT': config.get('ADB_PORT') or os.environ.get('ADB_PORT', '5555'),
        'MEDIA_PATH': config.get('MEDIA_PATH') or os.environ.get('MEDIA_PATH', '/carestream/media'),
        'HEARTBEAT_INTERVAL': config.get('HEARTBEAT_INTERVAL') or os.environ.get('HEARTBEAT_INTERVAL', '300'),
        'CARESTREAM_PORT': config.get('CARESTREAM_PORT') or os.environ.get('CARESTREAM_PORT', '8000'),
        'ADB_PUSH_DEST': config.get('ADB_PUSH_DEST') or os.environ.get('ADB_PUSH_DEST', '/sdcard/carestream/'),
        'VIDEO_PLAYER_PACKAGE': config.get('VIDEO_PLAYER_PACKAGE') or os.environ.get('VIDEO_PLAYER_PACKAGE', ''),
    })


@settings_bp.route('', methods=['PUT'])
def update_settings():
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400

    allowed_keys = ['SERVER_IP', 'ADB_PORT', 'MEDIA_PATH', 'HEARTBEAT_INTERVAL',
                    'CARESTREAM_PORT', 'ADB_PUSH_DEST', 'SECRET_KEY', 'VIDEO_PLAYER_PACKAGE']

    # Get the best .env file path for writing
    env_file = get_env_file_path_for_writing()
    
    # Read existing config
    config = {}
    if os.path.exists(env_file):
        config = dotenv_values(env_file)

    # Update only allowed keys
    for key in allowed_keys:
        if key in data:
            config[key] = str(data[key])

    # Write back to .env file
    try:
        # Ensure directory exists
        env_dir = os.path.dirname(env_file)
        if env_dir:
            os.makedirs(env_dir, exist_ok=True)
        
        # Write the file
        with open(env_file, 'w') as f:
            f.write('# CareStream Environment Configuration\n')
            for key, value in config.items():
                f.write(f'{key}={value}\n')

        # Update runtime environment variables
        for key in allowed_keys:
            if key in data:
                os.environ[key] = str(data[key])

        return jsonify({'message': f'Settings saved successfully to {env_file}', 'note': 'Port changes require container restart'})
    except Exception as e:
        return jsonify({'error': f'Failed to save settings: {str(e)}'}), 500


@settings_bp.route('/timezone', methods=['GET'])
def get_timezone():
    """Get the current timezone setting."""
    current_tz = Settings.get('timezone', 'America/New_York')
    return jsonify({
        'timezone': current_tz,
        'available_timezones': VALID_TIMEZONES
    })


@settings_bp.route('/timezone', methods=['POST'])
def set_timezone():
    """Set the timezone setting."""
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400

    timezone = data.get('timezone')
    if not timezone:
        return jsonify({'error': 'Timezone is required'}), 400

    # Validate timezone
    if timezone not in VALID_TIMEZONES:
        return jsonify({'error': f'Invalid timezone: {timezone}. Must be one of: {", ".join(VALID_TIMEZONES)}'}), 400

    # Save to database
    Settings.set('timezone', timezone)

    return jsonify({
        'success': True,
        'timezone': timezone,
        'message': f'Timezone updated to {timezone}. All timestamps will now use this timezone.'
    })
