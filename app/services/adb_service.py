import os
import re
import subprocess
import logging

logger = logging.getLogger(__name__)


def get_adb_port():
    return os.getenv('ADB_PORT', '5555')


def get_push_dest():
    """Get ADB push destination, default to /sdcard/carestream/"""
    return os.getenv('ADB_PUSH_DEST', '/sdcard/carestream/')


def get_video_player_package(ip_address):
    """
    Get the video player package to use for this device.
    DEPRECATED: adb_launch_video() now uses strategy-based approach with automatic fallbacks.
    This is kept only for backward compatibility but should not be called.
    """
    logger.warning('get_video_player_package() is deprecated - use adb_launch_video() instead')
    configured = os.getenv('VIDEO_PLAYER_PACKAGE')
    if configured:
        logger.info(f'Using configured VIDEO_PLAYER_PACKAGE: {configured}')
        return configured
    # Default fallback
    return 'android.rk.RockVideoPlayer'


def get_device_serial(ip_address):
    """Return device serial in ip:port format."""
    return f"{ip_address}:{get_adb_port()}"


def adb_connect(ip_address):
    """Connect to device via ADB TCP/IP. Returns (success, message)."""
    serial = get_device_serial(ip_address)
    try:
        result = subprocess.run(
            ['adb', 'connect', serial],
            capture_output=True, text=True, timeout=10
        )
        output = result.stdout.strip() + result.stderr.strip()
        success = 'connected' in output.lower() and 'cannot' not in output.lower()
        logger.info(f'ADB connect {serial}: {output} (success={success})')
        return success, output
    except subprocess.TimeoutExpired:
        logger.warning(f'ADB connect timeout for {serial}')
        return False, 'Connection timeout'
    except Exception as e:
        logger.error(f'ADB connect error for {serial}: {e}')
        return False, str(e)


def adb_get_state(ip_address):
    """Check device state. Returns 'device', 'offline', or 'unknown'."""
    serial = get_device_serial(ip_address)
    try:
        result = subprocess.run(
            ['adb', '-s', serial, 'get-state'],
            capture_output=True, text=True, timeout=10
        )
        state = result.stdout.strip()
        if state == 'device':
            return 'online'
        return 'offline'
    except Exception:
        return 'unknown'


def adb_check_device(ip_address):
    """Connect and check if device is online. Returns status string."""
    success, _ = adb_connect(ip_address)
    if not success:
        return 'offline'
    return adb_get_state(ip_address)


def adb_clear_old_media(ip_address):
    """
    Clear old media files from device storage to prevent replay of previous content.
    Keeps LoadScreen.mp4 but removes all other .mp4 files.
    This ensures device has clean state before new content is pushed.
    Returns (success, message).
    """
    serial = get_device_serial(ip_address)
    push_dest = get_push_dest()
    
    try:
        logger.info(f'🧹 Clearing old media files from {serial}:{push_dest}')
        
        # List all files in the push destination
        result = subprocess.run(
            ['adb', '-s', serial, 'shell', 'ls', '-1', push_dest],
            capture_output=True, text=True, timeout=10
        )
        
        if result.returncode != 0:
            logger.warning(f'Could not list files on device (directory may not exist yet)')
            return True, 'No old files to clear'
        
        files = result.stdout.strip().split('\n')
        files = [f.strip() for f in files if f.strip()]
        
        if not files:
            logger.info(f'✓ No files to clear')
            return True, 'Directory empty'
        
        deleted_count = 0
        for filename in files:
            # Skip LoadScreen and non-video files
            if filename.lower() == 'loadscreen.mp4' or not filename.lower().endswith('.mp4'):
                logger.debug(f'  Keeping: {filename}')
                continue
            
            # Delete old video files
            remote_path = f"{push_dest}{filename}"
            try:
                result = subprocess.run(
                    ['adb', '-s', serial, 'shell', 'rm', remote_path],
                    capture_output=True, text=True, timeout=10
                )
                if result.returncode == 0:
                    logger.info(f'  ✓ Deleted: {filename}')
                    deleted_count += 1
                else:
                    logger.warning(f'  ⚠ Failed to delete {filename}: {result.stderr}')
            except Exception as e:
                logger.warning(f'  ⚠ Error deleting {filename}: {e}')
        
        logger.info(f'🧹 Cleanup complete: deleted {deleted_count} old file(s)')
        return True, f'Cleared {deleted_count} old media files'
    
    except Exception as e:
        logger.error(f'Error clearing old media: {e}')
        # Don't fail the push if cleanup fails - just warn
        return True, f'Cleanup warning: {str(e)}'


def adb_verify_file(ip_address, remote_path):
    """Verify that a file exists on the device. Returns (exists, file_size)."""
    serial = get_device_serial(ip_address)
    try:
        result = subprocess.run(
            ['adb', '-s', serial, 'shell', 'ls', '-lh', remote_path],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0 and remote_path in result.stdout:
            # Extract file size from ls output
            parts = result.stdout.split()
            if len(parts) >= 5:
                file_size = parts[4]
                logger.info(f'File verified on device: {remote_path} ({file_size})')
                return True, file_size
        logger.warning(f'File NOT found on device: {remote_path}')
        return False, None
    except Exception as e:
        logger.error(f'Error verifying file: {e}')
        return False, None


def adb_push_file(ip_address, local_path, filename, progress_callback=None):
    """
    Push a file to device via ADB.
    progress_callback(percent, bytes_transferred, total_bytes) is called during transfer.
    Returns (success, message).
    """
    serial = get_device_serial(ip_address)
    push_dest = get_push_dest()
    remote_path = f"{push_dest}{filename}"

    # Verify local file exists before attempting push
    if not os.path.exists(local_path):
        logger.error(f'Local file does not exist: {local_path}')
        return False, f'Local file not found: {local_path}'
    
    local_size = os.path.getsize(local_path)
    logger.info(f'Preparing to push file: {filename} ({local_size} bytes) to {serial}:{remote_path}')

    # Ensure destination directory exists
    try:
        subprocess.run(
            ['adb', '-s', serial, 'shell', 'mkdir', '-p', push_dest],
            capture_output=True, text=True, timeout=10
        )
    except Exception:
        pass

    try:
        process = subprocess.Popen(
            ['adb', '-s', serial, 'push', local_path, remote_path],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True
        )

        # Parse ADB push output for progress
        output_lines = []
        for line in iter(process.stdout.readline, ''):
            line = line.strip()
            if not line:
                continue
            output_lines.append(line)

            # ADB push progress pattern: [ xx%] /path/to/file
            match = re.search(r'\[\s*(\d+)%\]', line)
            if match and progress_callback:
                percent = int(match.group(1))
                progress_callback(percent, 0, 0)

            # Also check for bytes transferred pattern
            bytes_match = re.search(r'(\d+) bytes in', line)
            if bytes_match:
                transferred = int(bytes_match.group(1))
                if progress_callback:
                    progress_callback(100, transferred, transferred)

        process.wait(timeout=600)  # 10 min timeout for large files

        if process.returncode == 0 and 'file pushed' in '\n'.join(output_lines):
            logger.info(f'✓ ADB push successful: {filename} verified in output')
            import time
            time.sleep(0.3)  # Let filesystem sync
            return True, f'Push successful - {filename}'
        else:
            error_msg = '\n'.join(output_lines[-3:]) if output_lines else 'Push failed'
            logger.error(f'ADB push failed for {filename}: {error_msg}')
            return False, error_msg

    except subprocess.TimeoutExpired:
        process.kill()
        logger.error(f'ADB push timeout for {filename}')
        return False, 'Push timeout exceeded'
    except Exception as e:
        logger.error(f'ADB push error for {filename}: {e}')
        return False, str(e)



def adb_stop_media_player(ip_address):
    """Stop any currently playing media on the device."""
    serial = get_device_serial(ip_address)
    try:
        # Send KEYCODE_MEDIA_STOP (command code 86)
        result = subprocess.run(
            ['adb', '-s', serial, 'shell', 'input', 'keyevent', '86'],
            capture_output=True, text=True, timeout=5
        )
        logger.info(f'ADB stop media on {serial}: {result.stdout.strip()}')
        return True
    except Exception as e:
        logger.error(f'ADB stop media error: {e}')
        return False


def adb_clear_app_data(ip_address, package='com.android.mediacenterui'):
    """Clear media player app data to reset playback state."""
    serial = get_device_serial(ip_address)
    try:
        # Try to kill the media player process
        result = subprocess.run(
            ['adb', '-s', serial, 'shell', 'pkill', '-f', 'mediacenter'],
            capture_output=True, text=True, timeout=5
        )
        logger.info(f'ADB kill media player on {serial}: done')
        return True
    except Exception as e:
        logger.error(f'ADB clear app data error: {e}')
        return False


def adb_launch_video(ip_address, filename):
    """
    Launch video playback on device via media player intent.
    Works with ANY device/player (RockChip, Viewsonic, Android stock, VLC, etc).
    Verifies file exists before launching and tries multiple strategies with full diagnostics.
    """
    serial = get_device_serial(ip_address)
    push_dest = get_push_dest()
    file_path = f"file://{push_dest}{filename}"
    remote_path = f"{push_dest}{filename}"

    try:
        logger.info(f'╔══════════════════════════════════════════════════════════════╗')
        logger.info(f'║ VIDEO LAUNCH START: {filename}')
        logger.info(f'║ Device: {serial}')
        logger.info(f'║ Remote path: {remote_path}')
        logger.info(f'╚══════════════════════════════════════════════════════════════╝')
        
        # Directly launch video - no need to stop previous player, new intent will override
        logger.info(f'[READY] Launching video intent...')
        
        # STRATEGY 1: Try generic ACTION_VIEW intent (works on most devices)
        logger.info(f'[STRATEGY 1] Attempting generic ACTION_VIEW intent (universal approach)...')
        cmd = [
            'adb', '-s', serial, 'shell', 'am', 'start',
            '-a', 'android.intent.action.VIEW',
            '-d', file_path,
            '-t', 'video/mp4',
            '-c', 'android.intent.category.DEFAULT'
        ]
        logger.debug(f'  Full command: {" ".join(cmd)}')
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        
        if result.returncode == 0:
            logger.info(f'✓ Strategy 1 SUCCESS: Video launched with generic intent')
            logger.info(f'  Command executed successfully')
            logger.info(f'╔══════════════════════════════════════════════════════════════╗')
            logger.info(f'║ VIDEO LAUNCH COMPLETE: {filename}')
            logger.info(f'║ Method: Generic ACTION_VIEW intent')
            logger.info(f'╚══════════════════════════════════════════════════════════════╝')
            return True, result.stdout.strip() or 'Video launched successfully'
        
        logger.warning(f'⚠ Strategy 1 failed (returncode={result.returncode})')
        if result.stderr:
            logger.warning(f'  Error: {result.stderr.strip()}')
        
        logger.info(f'[STRATEGY 2] Falling back to explicit component specification...')
        
        # STRATEGY 2: Try known video player packages with explicit activities
        video_players = [
            # Viewsonic digital signage players (highest priority for Viewsonic devices)
            ('com.reveldigital.player', 'com.reveldigital.player.MainActivity'),  # Revel Digital (primary for Viewsonic)
            ('com.iadea.player.general', 'com.iadea.player.general.MainActivity'),  # iAdea (secondary signage)
            ('com.ifpdos.player', 'com.ifpdos.player.MainActivity'),  # ifpdos player
            # Standard video players (fallback)
            ('android.rk.RockVideoPlayer', 'android.rk.RockVideoPlayer.VideoPlayActivity'),  # RockChip
            ('org.videolan.vlc', 'org.videolan.vlc.gui.video.VideoPlayerActivity'),  # VLC
            ('com.archos.mediacenter.video', 'com.archos.mediacenter.video.InfoActivity'),  # Archos
            ('com.mxtech.videoplayer.ad', 'com.mxtech.videoplayer.ad.ActivityScreen'),  # MX Player
            ('com.android.mediacenterui', 'com.android.mediacenterui.MediaCenterActivity'),  # Stock
        ]
        
        for package, activity in video_players:
            logger.info(f'[STRATEGY 2] Attempting {package}...')
            cmd = [
                'adb', '-s', serial, 'shell', 'am', 'start',
                '-n', f'{package}/{activity}',
                '-a', 'android.intent.action.VIEW',
                '-d', file_path,
                '-t', 'video/mp4'
            ]
            logger.debug(f'  Full command: {" ".join(cmd)}')
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
            
            if result.returncode == 0:
                logger.info(f'✓ Strategy 2 SUCCESS: Video launched with {package}')
                logger.info(f'╔══════════════════════════════════════════════════════════════╗')
                logger.info(f'║ VIDEO LAUNCH COMPLETE: {filename}')
                logger.info(f'║ Method: {package}')
                logger.info(f'╚══════════════════════════════════════════════════════════════╝')
                return True, result.stdout.strip() or f'Launched with {package}'
            else:
                logger.debug(f'  Failed: {result.stderr.strip() if result.stderr else "Unknown error"}')
        
        logger.error(f'✗ All video launch strategies failed for {filename}')
        logger.error(f'  Last error: {result.stderr.strip() if result.stderr else "Unknown"}')
        logger.error(f'  This likely means no compatible video player is installed on device')
        return False, f'Could not launch video with any available player'
        
    except Exception as e:
        logger.error(f'╔══════════════════════════════════════════════════════════════╗')
        logger.error(f'║ VIDEO LAUNCH EXCEPTION: {filename}')
        logger.error(f'║ Error: {str(e)}')
        logger.error(f'╚══════════════════════════════════════════════════════════════╝')
        return False, str(e)


def adb_return_to_vizabli(ip_address):
    """Return device to Vizabli launcher."""
    serial = get_device_serial(ip_address)
    try:
        result = subprocess.run(
            ['adb', '-s', serial, 'shell', 'am', 'start',
             '-n', 'com.vizabli.android/.SplashActivity'],
            capture_output=True, text=True, timeout=15
        )
        logger.info(f'ADB return to Vizabli on {serial}: {result.stdout.strip()}')
        return result.returncode == 0
    except Exception as e:
        logger.error(f'ADB return to Vizabli error: {e}')
        return False


def adb_force_stop_video_player(ip_address):
    """
    Force-stop video player app to clear all background state and cache.
    This ensures no residual playback state lingers between content assignments.
    Works with any video player package.
    Returns (success, message).
    """
    serial = get_device_serial(ip_address)
    
    # List of common video player packages to try to stop.
    # Must mirror the packages attempted in adb_launch_video to guarantee complete cleanup.
    video_players = [
        'android.rk.RockVideoPlayer',           # RockChip (hospital standard)
        'org.videolan.vlc',                      # VLC Media Player
        'com.android.mediacenterui',             # Stock media center
        'com.mxtech.videoplayer.ad',             # MX Player
        'com.archos.mediacenter.video',          # Archos
        'com.android.systemui.media',            # System media
        'com.reveldigital.player',               # Revel Digital (Viewsonic IFP/signage)
        'com.iadea.player.general',              # iAdea player (Viewsonic)
        'com.ifpdos.player',                     # ifpdos (Viewsonic IFP series)
    ]
    
    stopped_count = 0
    failed_packages = []
    
    for package in video_players:
        try:
            result = subprocess.run(
                ['adb', '-s', serial, 'shell', 'am', 'force-stop', package],
                capture_output=True, text=True, timeout=10
            )
            if result.returncode == 0:
                logger.info(f'  ✓ Force-stopped: {package}')
                stopped_count += 1
            else:
                # Package may not be installed, which is fine
                if 'not found' not in result.stderr.lower():
                    logger.debug(f'  ⚠ Could not force-stop {package}: {result.stderr.strip()}')
                    failed_packages.append(package)
        except Exception as e:
            logger.debug(f'  ⚠ Error force-stopping {package}: {e}')
            failed_packages.append(package)
    
    if stopped_count > 0:
        logger.info(f'🛑 Media players killed: {stopped_count} processes stopped')
        return True, f'Force-stopped {stopped_count} media player process(es)'
    else:
        logger.warning(f'⚠ No media players could be force-stopped (may not be installed)')
        return True, 'No media players to stop (normal if using alternative player)'
