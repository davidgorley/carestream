# CareStream — Deployment Guide

This guide walks you through deploying CareStream on a hospital Ubuntu server using Docker.

---

### Prerequisites

| Requirement | Minimum Version | Check Command |
|---|---|---|
| **Ubuntu Server** | 20.04 LTS or later | `lsb_release -a` |
| **Docker Engine** | 20.10+ | `docker --version` |
| **Docker Compose** | v2.0+ (plugin) or 1.29+ (standalone) | `docker compose version` |
| **Network Access** | Same VLAN/subnet as Android devices | `ip addr show` |

#### Installing Docker (if not already installed)

```bash
# Install Docker
curl -fsSL https://get.docker.com | sudo sh

# Add your user to the docker group (avoids needing sudo)
sudo usermod -aG docker $USER
newgrp docker

# Verify
docker --version
docker compose version
```

---

### Port & Network Requirements

| Port | Protocol | Purpose |
|---|---|---|
| **8000** (default, configurable) | TCP | CareStream web UI & API |
| **5555** | TCP | ADB over TCP to Android devices |

> **Important:** The Docker container runs with `network_mode: host`, meaning it shares the host's network stack directly. This is required so the container can reach Android devices on the local network via ADB TCP. No Docker port mapping is needed in this mode — the application binds directly to the host's interfaces.

#### Firewall

If `ufw` is active, allow the CareStream port:

```bash
sudo ufw allow 8000/tcp   # or whichever port you configure
sudo ufw allow 5555/tcp   # ADB communication
```

---

### Step-by-Step Deployment

#### 1. Transfer & Extract the Archive

Copy `medcast-deployment.tar.gz` to the target server (via SCP, USB, or shared drive):

```bash
# Example: SCP from your workstation
scp medcast-deployment.tar.gz user@hospital-server:/home/user/

# On the server, extract
cd /home/user
tar -xzf medcast-deployment.tar.gz
cd medcast
```

#### 2. Configure the Environment

Copy the example environment file and edit it:

```bash
cp .env.example .env
nano .env
```

See the [Configuration Guide](#configuration-guide) below for each variable.

#### 3. Build & Start the Application

```bash
docker compose up -d --build
```

This will:
- Build the Docker image (installs Python, ADB, ffmpeg)
- Start the CareStream container in the background
- Create `./media/` and `./data/` directories for persistent storage

#### 4. Verify It's Running

```bash
# Check container status
docker compose ps

# Check logs
docker compose logs -f carestream

# Test the web UI
curl -s http://localhost:6000 | head -5
```

Open a browser and navigate to `http://<server-ip>:6000`.

#### 5. Stopping & Restarting

```bash
# Stop
docker compose down

# Restart (after config changes)
docker compose up -d --build

# View logs
docker compose logs -f
```

---

### Configuration Guide

Edit the `.env` file to match your environment. All variables are documented below:

| Variable | Default | Description |
|---|---|---|
| `CARESTREAM_PORT` | `8000` | Port the web UI listens on. Change if 8000 is in use. **Requires container restart.** |
| `SERVER_IP` | `0.0.0.0` | Bind address. `0.0.0.0` = all interfaces. Set to a specific IP if needed. |
| `ADB_PORT` | `5555` | TCP port for ADB connections to Android devices. Must match device config. |
| `MEDIA_PATH` | `/carestream/media` | Path inside the container where MP4 files are stored. Mapped to `./media/` on host. |
| `DB_PATH` | `/carestream/data/carestream.db` | SQLite database path inside the container. Mapped to `./data/` on host. |
| `HEARTBEAT_INTERVAL` | `300` | Seconds between device status checks (heartbeat). Lower = more frequent checks. |
| `ADB_PUSH_DEST` | `/sdcard/carestream/` | Destination path on the Android device for pushed files. |
| `SECRET_KEY` | *(change me)* | Flask secret key. **Set to a long random string in production.** |

#### Generating a Secret Key

```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
```

---

### ADB Setup — Connecting to Android Devices

CareStream uses ADB over TCP/IP to push content and control playback on Android devices (tablets/TVs in patient rooms).

#### On Each Android Device

1. **Enable Developer Options:**
   - Go to **Settings → About → Build Number** and tap it 7 times.

2. **Enable USB Debugging:**
   - Go to **Settings → Developer Options → USB Debugging** → Enable.

3. **Enable ADB over TCP/IP** (two methods):

   **Method A — Via USB first (one-time):**
   ```bash
   # Connect device via USB to any computer with ADB
   adb tcpip 5555
   # Disconnect USB. The device now listens on port 5555.
   ```

   **Method B — Device setting (if available):**
   - Some Android devices have **Settings → Developer Options → ADB over network**. Enable it and note the IP.

4. **Verify connectivity from the server:**
   ```bash
   # From the CareStream server (with ADB installed, or exec into container)
   docker exec carestream adb connect <device-ip>:5555
   docker exec carestream adb devices
   ```

#### Adding Devices in CareStream

1. Open the CareStream web UI → **Settings** tab → **Room Management**.
2. Add each room with its **room number**, **unit name**, and **IP address**.
3. Or import rooms in bulk via CSV. Download the template from Settings.

#### Network Considerations

- All Android devices must be on the **same network/VLAN** as the CareStream server.
- Ensure no firewall blocks TCP port **5555** between the server and devices.
- Static IP addresses (or DHCP reservations) are strongly recommended for devices.

---

### Troubleshooting

#### Container won't start

```bash
# Check logs for errors
docker compose logs carestream

# Common fixes:
# - Port already in use: change CARESTREAM_PORT in .env
# - Permission denied: ensure your user is in the docker group
sudo usermod -aG docker $USER && newgrp docker
```

#### Web UI not loading

- Verify the container is running: `docker compose ps`
- Check the port: `curl http://localhost:8000`
- Verify firewall allows the port: `sudo ufw status`
- If using `network_mode: host`, the port binds directly — no Docker port mapping issues.

#### ADB cannot connect to devices

```bash
# Test connectivity
docker exec carestream adb connect <device-ip>:5555
docker exec carestream adb devices

# If "offline" or "unauthorized":
# - On the device, accept the RSA key prompt
# - Restart ADB: docker exec carestream adb kill-server && docker exec carestream adb devices

# If "connection refused":
# - Ensure the device has ADB over TCP enabled (port 5555)
# - Check network: docker exec carestream ping -c 3 <device-ip>
```

#### Devices show "offline" on dashboard

- The heartbeat service checks devices every `HEARTBEAT_INTERVAL` seconds.
- Force an immediate check by restarting the container.
- Verify device IPs are correct in Settings → Room Management.
- Check that ADB over TCP is still enabled on each device (it can reset after reboot).

#### Push fails or hangs

- Check push logs in the CareStream UI or via `GET /api/push/log`.
- Ensure the MP4 file is valid and not corrupted.
- Verify the device has enough storage: `docker exec carestream adb -s <ip>:5555 shell df`
- Check ADB connection: `docker exec carestream adb -s <ip>:5555 get-state`

#### Database issues

```bash
# The SQLite database is at ./data/medcast.db on the host
# To reset completely:
docker compose down
rm -f ./data/medcast.db
docker compose up -d
```

#### Updating CareStream

```bash
# Replace files with the new version, then rebuild
docker compose down
# Extract new archive over existing directory
tar -xzf medcast-deployment-new.tar.gz
cd carestream
docker compose up -d --build
```

---

### Data Persistence

The following host directories are mounted as Docker volumes:

| Host Path | Container Path | Contents |
|---|---|---|
| `./media/` | `/carestream/media` | Uploaded MP4 files |
| `./data/` | `/carestream/data` | SQLite database (`carestream.db`) |

**Back up these directories regularly.** They persist across container restarts and rebuilds.

---

### Architecture Summary

```
┌─────────────────────────────────────────────┐
│  Hospital Server (Ubuntu + Docker)          │
│                                             │
│  ┌──────────────────────────────────────┐   │
│  │  CareStream Container                │   │
│  │  • Flask + SocketIO (Python)         │   │
│  │  • React SPA (static files)          │   │
│  │  • ADB client                        │   │
│  │  • ffmpeg / ffprobe                  │   │
│  │  • SQLite database                   │   │
│  └──────────┬───────────────────────────┘   │
│             │ network_mode: host            │
│             │                               │
├─────────────┼───────────────────────────────┤
│  Hospital LAN                               │
│  ┌──────┐  ┌──────┐  ┌──────┐              │
│  │ TV 1 │  │ TV 2 │  │ TV 3 │  ...         │
│  │:5555 │  │:5555 │  │:5555 │              │
│  └──────┘  └──────┘  └──────┘              │
└─────────────────────────────────────────────┘
```

---

### License

CareStream — Internal hospital media distribution system.
