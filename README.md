# CareStream — Patient Room Media Manager

CareStream is a self-hosted, Dockerized web application that runs on a hospital Ubuntu server alongside the Vizabli platform. It allows nursing staff to push MP4 media content to Android patient room devices via ADB over TCP/IP.

## Features

- **Dashboard** — Room cards grid with search/filter/sort, online/offline status, real-time push progress
- **Media Manager** — MP4 upload (drag-and-drop), file management, playlist builder with drag-and-drop reordering
- **Settings** — Room management with CSV import/export, server configuration editor
- **ADB Integration** — Push files, sequential playback, automatic return to Vizabli launcher
- **Real-time Updates** — WebSocket-based progress tracking and device status monitoring
- **Heartbeat Monitoring** — Automatic device status checks every 5 minutes

## Quick Start

### Prerequisites
- Docker & Docker Compose installed on Ubuntu server
- Android devices connected to the same network with ADB over TCP/IP enabled (port 5555)

### Deployment

```bash
# 1. Clone the repo
git clone <repo-url> && cd carestream

# 2. Copy and configure environment
cp .env.example .env
nano .env   # Set SERVER_IP, CARESTREAM_PORT, etc.

# 3. Build and start
docker-compose up -d --build

# 4. Access the UI
# Open http://{SERVER_IP}:8000 in any browser on the hospital network
```

### Running without Docker (Development)

```bash
# Install Python dependencies
pip install -r requirements.txt

# Ensure adb and ffprobe are installed
sudo apt install android-tools-adb ffmpeg

# Create directories
mkdir -p media data

# Start the application
python run.py
```

## Configuration

All configuration is via the `.env` file:

| Variable | Default | Description |
|---|---|---|
| `CARESTREAM_PORT` | `8000` | Web UI port |
| `SERVER_IP` | `0.0.0.0` | Server bind address |
| `ADB_PORT` | `5555` | ADB TCP/IP port on devices |
| `MEDIA_PATH` | `/carestream/media` | Media file storage path |
| `DB_PATH` | `/carestream/data/carestream.db` | SQLite database path |
| `HEARTBEAT_INTERVAL` | `300` | Device check interval (seconds) |
| `ADB_PUSH_DEST` | `/sdcard/carestream/` | Destination path on devices |
| `SECRET_KEY` | `change-me` | Flask secret key |
| `TZ` | `America/New_York` | Default timezone for timestamps (Python timezone name) |

### Timezone Configuration

CareStream displays all timestamps in the timezone you select via the Settings UI. This applies to all timestamps across the application:
- Room check times (Dashboard)
- Push start/completion times (push logs)
- Media upload times (Media Manager)
- Playlist creation times (Media Manager)

**To change timezone:**

1. Open Settings → Timezone
2. Select your timezone from the dropdown (18 common timezones available: EST, CST, PST, UTC, GMT, CET, IST, JST, AEST, etc.)
3. Click "Save Timezone"
4. All timestamps across the application instantly update

**Timezone selection priority:**
1. **User-selected timezone** (saved in database via Settings UI) — takes highest priority
2. **TZ environment variable** — used if no user selection exists
3. **Default timezone** (America/New_York) — used if neither of above available

**Supported timezones:** EST, CST, PST, MST, UTC/GMT, London (GMT), Paris (CET), Dubai (GST), Delhi (IST), Bangkok (ICT), Tokyo (JST), Sydney (AEDT), and others.

## Architecture

- **Backend:** Python Flask + Flask-SocketIO (WebSocket)
- **Frontend:** React SPA (pre-built, served by Flask)
- **Database:** SQLite
- **Device Communication:** ADB over TCP/IP
- **Background Tasks:** APScheduler for heartbeat, eventlet for concurrent pushes

## Push Flow

1. User clicks a room card on the Dashboard
2. Selects media files and/or playlists to push
3. Backend connects to device via ADB TCP/IP
4. Files are pushed to `/sdcard/medcast/` with real-time progress
5. Videos play sequentially via Android media player intent
6. After completion, device returns to Vizabli home launcher

## CSV Import Format

```csv
room,unit,ip
Room 224,ICU,192.168.1.101
Room 225,Pediatrics,192.168.1.102
```

A template with sample data can be downloaded from Settings → Room Management → Download Template.

## License

Internal hospital use only.
