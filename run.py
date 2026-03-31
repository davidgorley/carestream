import os
from dotenv import load_dotenv

load_dotenv()

from app import create_app, socketio

app = create_app()

if __name__ == '__main__':
    # For local development only
    port = int(os.getenv('CARESTREAM_PORT', 8000))
    socketio.run(app, host='0.0.0.0', port=port, debug=False, allow_unsafe_werkzeug=True)
