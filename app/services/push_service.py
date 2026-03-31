import time
import logging
import threading
import os
import sys
from datetime import datetime
from app import db, socketio
from app.models.room import Room
from app.models.media import MediaFile
from app.models.playlist import PushLog
from app.services.adb_service import (
    adb_connect, adb_push_file, adb_launch_video, adb_return_to_vizabli,
    adb_clear_old_media, adb_force_stop_video_player
)

logger = logging.getLogger(__name__)

def log_and_print(msg, level='info'):
    """Log to both logger and print with flush for immediate output."""
    print(f"[CareStream] {msg}", flush=True)
    if level == 'info':
        logger.info(msg)
    elif level == 'warning':
        logger.warning(msg)
    elif level == 'error':
        logger.error(msg)

PLAYBACK_BUFFER_SECONDS = 0.05
VIDEO_START_DELAY = 0.5  # Time to wait after launching before considering it started
LOADING_SCREEN_FILENAME = 'LoadScreen.mp4'
LOADING_SCREEN_DURATION = 4.0  # Duration of loading screen (4 seconds - matches your custom video)
ADB_COMMAND_DELAY = 0.15  # Small delay between rapid ADB commands to prevent connection storms
RECONNECT_WAIT_TIME = 1.0  # Time to wait after device disconnects before attempting reconnect
RECONNECT_MAX_ATTEMPTS = 3  # Maximum reconnection attempts before giving up

# Room-level locks to prevent concurrent pushes to same device
room_push_locks = {}
room_push_lock = threading.Lock()

def get_room_lock(room_id):
    """Get or create a lock for a specific room."""
    global room_push_locks
    with room_push_lock:
        if room_id not in room_push_locks:
            room_push_locks[room_id] = threading.Lock()
        return room_push_locks[room_id]


def ensure_adb_connection(ip_address, max_attempts=RECONNECT_MAX_ATTEMPTS, wait_time=RECONNECT_WAIT_TIME):
    """
    Ensure ADB connection is alive, reconnecting if needed.
    Viewsonic devices disconnect ADB daemon during video playback.
    This handles that gracefully by attempting to reconnect.
    """
    for attempt in range(max_attempts):
        success, msg = adb_connect(ip_address)
        if success:
            if attempt > 0:
                log_and_print(f'✓ Reconnected to device after {attempt} attempt(s)', 'info')
            return True
        
        if attempt < max_attempts - 1:
            log_and_print(f'⚠ Reconnection attempt {attempt + 1}/{max_attempts} failed, retrying in {wait_time}s... (Device disconnected?)', 'warning')
            time.sleep(wait_time)
    
    log_and_print(f'✗ Failed to reconnect after {max_attempts} attempts', 'error')
    return False


def emit_progress(room_id, status, progress, message, **kwargs):
    """Emit progress update via websocket."""
    socketio.emit('push_progress', {
        'room_id': room_id,
        'status': status,
        'progress': progress,
        'message': message,
        **kwargs
    })


def execute_push(app, room_id, push_log_id, media_file_ids):
    """
    Execute the complete push + playback flow for a room.
    Runs in a background thread/greenlet.
    Uses room-level locking to prevent concurrent pushes.
    """
    # Acquire room lock to prevent concurrent pushes to same device
    room_lock = get_room_lock(room_id)
    if not room_lock.acquire(blocking=False):
        logger.warning(f'Push already in progress for room {room_id}, queueing this request')
        # Could queue for later, but for now just return
        with app.app_context():
            push_log = PushLog.query.get(push_log_id)
            if push_log:
                push_log.status = 'cancelled'
                push_log.completed_at = datetime.utcnow()
                db.session.commit()
        return

    try:
        with app.app_context():
            room = Room.query.get(room_id)
            push_log = PushLog.query.get(push_log_id)
            media_files = [MediaFile.query.get(mid) for mid in media_file_ids]
            media_files = [f for f in media_files if f is not None]
            
            # Safety check: filter out LoadScreen.mp4 if it somehow got into the media list
            media_files = [f for f in media_files if f.filename.lower() != LOADING_SCREEN_FILENAME.lower()]

            if not room or not push_log or not media_files:
                logger.error(f'Push failed: invalid room/log/files')
                return

            total_files = len(media_files)
            logger.info(f'Starting playback push for {total_files} media files to room {room_id} ({room.ip_address})')

            try:
                # Step 1: Connect to device
                emit_progress(room_id, 'connecting', 0, 'Connecting to device...')
                success, msg = adb_connect(room.ip_address)
                if not success:
                    raise Exception(f'Failed to connect to device: {msg}')

                # Step 1b: Clear old media files to prevent replay of previous content
                emit_progress(room_id, 'preparing', 5, 'Clearing old media files...')
                success, msg = adb_clear_old_media(room.ip_address)
                log_and_print(f'[CLEANUP] {msg}')

                # ═══════════════════════════════════════════════════════════════════════════════
                # PHASE 1: PUSH STAGE - Push ALL files in one connection (optimized pre-staging)
                # ═══════════════════════════════════════════════════════════════════════════════
                # Key benefit: Single connection, all files transferred without reconnection
                # Device may disconnect after playback - that's expected and OK, files are staged
                
                log_and_print(f'╔{"═"*70}╗')
                log_and_print(f'║ PHASE 1: PUSH STAGE - Staging all files to device (one session)')
                log_and_print(f'╚{"═"*70}╝')
                
                loading_screen_available = False
                loading_screen_local = os.path.join(os.getenv('MEDIA_PATH', '/carestream/media'), LOADING_SCREEN_FILENAME)
                files_to_push = []  # Queue of (file_type, local_path, remote_name)
                
                # Check if LoadScreen exists
                logger.info(f'🔍 Looking for LoadScreen.mp4 at: {loading_screen_local}')
                if os.path.exists(loading_screen_local):
                    logger.info(f'✓ LoadScreen.mp4 FOUND - will be included in push')
                    loading_screen_available = True
                    files_to_push.append(('LoadScreen', loading_screen_local, LOADING_SCREEN_FILENAME))
                else:
                    logger.warning(f'⚠ LoadScreen.mp4 NOT FOUND at {loading_screen_local}')
                    logger.warning(f'  - Loading screens will NOT be displayed between videos')
                
                # Add all media files to push queue
                for mf in media_files:
                    files_to_push.append(('Media', mf.filepath, mf.filename))
                
                total_to_push = len(files_to_push)
                log_and_print(f'📤 Staging {total_to_push} file(s) to device in single connection')
                
                # Push all files in ONE continuous connection (no reconnection per file)
                for idx, (file_type, local_path, remote_name) in enumerate(files_to_push):
                    file_num = idx + 1
                    
                    emit_progress(room_id, 'pushing', 0,
                                  f'Staging {file_type} {file_num}/{total_to_push}: {remote_name}',
                                  current_file=file_num, total_files=total_to_push)

                    logger.info(f'📤 [{file_type}] File {file_num}/{total_to_push}: {remote_name}')

                    def progress_cb(percent, transferred, total, _room_id=room_id,
                                    _type=file_type, _file_num=file_num, _total=total_to_push, _fn=remote_name):
                        overall = int(((_file_num - 1) / _total * 100) + (percent / _total))
                        emit_progress(_room_id, 'pushing', percent,
                                      f'{_type} {_file_num}/{_total}: {_fn} ({percent}%)',
                                      current_file=_file_num, total_files=_total,
                                      overall_progress=int(overall * 0.5))

                    success, msg = adb_push_file(room.ip_address, local_path, remote_name, progress_cb)
                    if not success:
                        logger.error(f'✗ Failed to push {remote_name}: {msg}')
                        raise Exception(f'Failed to push {remote_name}: {msg}')
                    
                    # Delay between files but stay connected
                    if idx < total_to_push - 1:
                        time.sleep(ADB_COMMAND_DELAY)
                    
                    logger.info(f'✓ [{file_type}] Staged: {remote_name}')
                    emit_progress(room_id, 'pushing', 100,
                                  f'{file_type} {file_num}/{total_to_push}: {remote_name}',
                                  current_file=file_num, total_files=total_to_push,
                                  overall_progress=int((file_num / total_to_push) * 50))
                
                log_and_print(f'✓ PHASE 1 COMPLETE: All {total_to_push} file(s) staged on device')

                # ═══════════════════════════════════════════════════════════════════════════════
                # PHASE 2: PLAYBACK STAGE - Sequential video playback (files already staged)
                # ═══════════════════════════════════════════════════════════════════════════════
                # Key benefit: No uploading, just launching (minimal network overhead)
                # Device disconnects are expected and handled gracefully
                
                log_and_print(f'╔{"═"*70}╗')
                log_and_print(f'║ PHASE 2: PLAYBACK STAGE - Sequential video playback')
                log_and_print(f'║ Files available: {total_files} video(s), LoadScreen: {loading_screen_available}')
                log_and_print(f'╚{"═"*70}╝')
                
                for idx, mf in enumerate(media_files):
                    file_num = idx + 1
                    is_last_video = (idx == total_files - 1)
                    is_only_video = (total_files == 1)
                    overall = 50 + int(file_num / total_files * 45)
                    
                    emit_progress(room_id, 'playing', overall,
                                  f'Playing file {file_num}/{total_files}: {mf.filename}',
                                  current_file=file_num, total_files=total_files,
                                  overall_progress=overall)

                    # Launch video playback
                    log_and_print(f'╔{"─"*70}╗')
                    log_and_print(f'║ [VIDEO {file_num}/{total_files}] Launching: {mf.filename}')
                    log_and_print(f'║ Duration: {mf.duration}s')
                    log_and_print(f'╚{"─"*70}╝')
                    
                    # Ensure connection before launch attempt
                    # Note: Device may reconnect, or may not - that's OK, launch will try and reconnect if needed
                    if idx > 0:
                        ensure_adb_connection(room.ip_address)  # Attempt to reconnect, don't fail if it can't
                    
                    success, msg = adb_launch_video(room.ip_address, mf.filename)
                    
                    if not success:
                        log_and_print(f'✗ [VIDEO {file_num}/{total_files}] FAILED to launch: {msg}', 'error')
                        emit_progress(room_id, 'error', overall,
                                      f'Failed to launch {mf.filename}: {msg}',
                                      current_file=file_num, total_files=total_files)
                        # Skip to next video on failure
                        continue
                    
                    # Wait for video to start rendering
                    log_and_print(f'[VIDEO {file_num}/{total_files}] Video launched, waiting {VIDEO_START_DELAY}s for render...')
                    time.sleep(VIDEO_START_DELAY)

                    # CRITICAL: Let video play to FULL COMPLETION without interruption
                    # Then immediately queue next content (zero buffer to prevent timeout)
                    if mf.duration and mf.duration > 0:
                        wait_time = mf.duration
                    else:
                        wait_time = 5  # Default wait if no duration
                    
                    log_and_print(f'[VIDEO {file_num}/{total_files}] ⏳ Playing full video ({wait_time:.1f}s)...')
                    time.sleep(wait_time)
                    log_and_print(f'[VIDEO {file_num}/{total_files}] ✓ Video playback complete')
                    
                    # Immediately launch next content (no sleep = no timeout)
                    if not is_last_video and loading_screen_available:
                        # Queue LoadScreen immediately after video ends
                        log_and_print(f'[VIDEO {file_num}/{total_files}] → Launching LoadScreen')
                        time.sleep(ADB_COMMAND_DELAY)  # Protect against ADB connection storms
                        
                        # Attempt reconnection before LoadScreen launch
                        ensure_adb_connection(room.ip_address)  # Soft reconnect, don't fail
                        
                        try:
                            success, msg = adb_launch_video(room.ip_address, LOADING_SCREEN_FILENAME)
                            if success:
                                log_and_print(f'[VIDEO {file_num}/{total_files}] ✓ LoadScreen launched')
                                # Let LoadScreen play for its duration
                                time.sleep(LOADING_SCREEN_DURATION)
                            else:
                                log_and_print(f'[VIDEO {file_num}/{total_files}] Could not launch LoadScreen: {msg}', 'error')
                        except Exception as e:
                            log_and_print(f'[VIDEO {file_num}/{total_files}] LoadScreen error: {e}', 'error')
                    else:
                        # Last video or no LoadScreen - wait full duration
                        if mf.duration and mf.duration > 0:
                            wait_time = mf.duration + PLAYBACK_BUFFER_SECONDS
                        else:
                            wait_time = 20
                            log_and_print(f'[VIDEO {file_num}/{total_files}] ⚠ Duration not set - using fallback: {wait_time}s', 'warning')
                        
                        log_and_print(f'[VIDEO {file_num}/{total_files}] ⏳ Playing video ({wait_time}s total)')
                        time.sleep(wait_time)
                    
                    log_and_print(f'[VIDEO {file_num}/{total_files}] ✓ Video playback complete')
                
                logger.info(f'╔{"═"*70}╗')
                logger.info(f'║ PLAYBACK COMPLETE: All {total_files} video(s) finished')
                logger.info(f'║ Cleanup phase starting...')
                logger.info(f'╚{"═"*70}╝')

                # Step 4: Stop playback and return to Vizabli
                emit_progress(room_id, 'completing', 95, 'Cleanup: Returning device to Vizabli...')
                
                # Attempt reconnection for cleanup (soft attempt)
                ensure_adb_connection(room.ip_address)
                
                logger.info(f'[RETURN] 🚀 Launching Vizabli...')
                success = adb_return_to_vizabli(room.ip_address)
                if success:
                    logger.info(f'[RETURN] ✓ Vizabli launched - device returning to home')
                else:
                    logger.warning(f'[RETURN] ⚠ Could not launch Vizabli (device offline?)')
                
                # Force-stop video player to clean up
                logger.info(f'[CLEANUP] 🛑 Force-stopping video player...')
                time.sleep(ADB_COMMAND_DELAY)
                success, msg = adb_force_stop_video_player(room.ip_address)
                logger.info(f'[CLEANUP] {msg}')
                
                # Mark success in database
                room.push_status = 'complete'
                room.last_push_file = push_log.media_ref
                room.last_push_time = datetime.utcnow()
                push_log.status = 'success'
                push_log.completed_at = datetime.utcnow()
                db.session.commit()
                
                log_and_print(f'╋{"═"*70}╖')
                log_and_print(f'║ ✓ PUSH AND PLAYBACK COMPLETE AND SUCCESSFUL')
                log_and_print(f'╚{"═"*70}╝')
                
                emit_progress(room_id, 'complete', 100, 'Push and playback complete')
                socketio.emit('room_update', room.to_dict())

            except Exception as e:
                logger.error(f'Push failed for room {room_id}: {e}')
                room.push_status = 'error'
                push_log.status = 'error'
                push_log.error_message = str(e)
                push_log.completed_at = datetime.utcnow()
                db.session.commit()
                emit_progress(room_id, 'error', 0, f'Push failed: {str(e)}')
                socketio.emit('room_update', room.to_dict())
    finally:
        # Always release the lock when done
        room_lock.release()
        logger.info(f'Push completed for room {room_id}, lock released')
