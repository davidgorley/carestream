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

                # Step 2: Push all files (including loading screen if it exists)
                loading_screen_available = False
                loading_screen_local = os.path.join(os.getenv('MEDIA_PATH', '/carestream/media'), LOADING_SCREEN_FILENAME)
                
                logger.info(f'🔍 Looking for LoadScreen.mp4 at: {loading_screen_local}')
                
                if os.path.exists(loading_screen_local):
                    logger.info(f'✓ LoadScreen.mp4 FOUND - attempting to push')
                    emit_progress(room_id, 'pushing', 0,
                                  f'Pushing loading screen...',
                                  current_file=1, total_files=total_files+1)
                    
                    try:
                        success, msg = adb_push_file(room.ip_address, loading_screen_local, LOADING_SCREEN_FILENAME)
                        if success:
                            logger.info(f'✓ Loading screen pushed successfully: {msg}')
                            loading_screen_available = True
                        else:
                            logger.error(f'✗ Failed to push loading screen: {msg}')
                    except Exception as e:
                        logger.error(f'✗ Exception pushing loading screen: {e}')
                else:
                    logger.warning(f'⚠ LoadScreen.mp4 NOT FOUND at {loading_screen_local}')
                    logger.warning(f'  - Loading screens will NOT be displayed between videos')
                    logger.warning(f'  - Check that LoadScreen.mp4 exists in /carestream/media/ directory')
                    logger.warning(f'  - Or rebuild Docker container: docker compose up -d --build')
                
                # Then push all media files
                for idx, mf in enumerate(media_files):
                    file_num = idx + 2 if loading_screen_available else idx + 1
                    total_with_loading = total_files + 1 if loading_screen_available else total_files
                    
                    # Reconnect before each push (device may have disconnected)
                    if idx > 0 or loading_screen_available:  # Reconnect needed after first push/loadscreen
                        if not ensure_adb_connection(room.ip_address):
                            raise Exception(f'Lost connection to device and could not reconnect before pushing {mf.filename}')
                    
                    emit_progress(room_id, 'pushing', 0,
                                  f'Pushing file {file_num}/{total_with_loading}: {mf.filename}',
                                  current_file=file_num, total_files=total_with_loading)

                    logger.info(f'📤 Pushing media file [{file_num}/{total_with_loading}]: {mf.filename}')

                    def progress_cb(percent, transferred, total, _room_id=room_id,
                                    _file_num=file_num, _total=total_with_loading, _fn=mf.filename):
                        overall = int(((_file_num - 1) / _total * 100) + (percent / _total))
                        emit_progress(_room_id, 'pushing', percent,
                                      f'Pushing file {_file_num}/{_total}: {_fn} ({percent}%)',
                                      current_file=_file_num, total_files=_total,
                                      overall_progress=overall)

                    success, msg = adb_push_file(room.ip_address, mf.filepath, mf.filename, progress_cb)
                    if not success:
                        logger.error(f'✗ Failed to push {mf.filename}: {msg}')
                        raise Exception(f'Failed to push {mf.filename}: {msg}')
                    
                    # Small delay between pushes to prevent connection storms
                    if idx < total_files - 1:  # Don't delay after last file
                        time.sleep(ADB_COMMAND_DELAY)
                    
                    logger.info(f'✓ Media file pushed successfully: {mf.filename}')

                    emit_progress(room_id, 'pushing', 100,
                                  f'File {file_num}/{total_with_loading} pushed: {mf.filename}',
                                  current_file=file_num, total_files=total_with_loading,
                                  overall_progress=int(file_num / total_with_loading * 50))

                # Step 3: Sequential playback with loading screen between videos
                log_and_print(f'╔{"═"*70}╗')
                log_and_print(f'║ STARTING PLAYBACK PHASE: {total_files} video(s) total')
                log_and_print(f'║ LoadScreen available: {loading_screen_available}')
                log_and_print(f'║ LoadScreen will show between videos: {loading_screen_available and total_files > 1}')
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
                    
                    # Ensure connection before launch (previous video may have disconnected it)
                    if idx > 0:
                        if not ensure_adb_connection(room.ip_address):
                            log_and_print(f'✗ [VIDEO {file_num}/{total_files}] Could not reconnect to launch video', 'error')
                            continue
                    
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
                        
                        # Reconnect before launching next content (video playback may have disconnected)
                        if not ensure_adb_connection(room.ip_address):
                            log_and_print(f'[VIDEO {file_num}/{total_files}] Could not reconnect to launch LoadScreen', 'error')
                        else:
                            try:
                                success, msg = adb_launch_video(room.ip_address, LOADING_SCREEN_FILENAME)
                                if success:
                                    log_and_print(f'[VIDEO {file_num}/{total_files}] ✓ LoadScreen launched')
                                    # Let LoadScreen play
                                    time.sleep(LOADING_SCREEN_DURATION)
                                else:
                                    log_and_print(f'[VIDEO {file_num}/{total_files}] Could not launch LoadScreen: {msg}', 'error')
                            except Exception as e:
                                log_and_print(f'[VIDEO {file_num}/{total_files}] LoadScreen error: {e}', 'error')
                                # Fallback: wait for full duration
                                time.sleep(mf.duration * 0.2 + 1)
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
                logger.info(f'╚{"═"*70}╝')

                # Step 4: Stop playback and return to Vizabli
                logger.info(f'╔{"═"*70}╗')
                logger.info(f'║ STEP 4: CLEANUP AND RETURN TO VIZABLI')
                logger.info(f'╚{"═"*70}╝')
                
                emit_progress(room_id, 'completing', 98, 'Stopping playback and returning to Vizabli...')
                
                # Reconnect before returning to Vizabli (video playback disconnected device)
                if not ensure_adb_connection(room.ip_address):
                    log_and_print(f'⚠ Could not reconnect to device for cleanup - it may still be in playback', 'warning')
                    # Don't fail completely, attempt to continue
                
                logger.info(f'[RETURN] 🚀 Launching Vizabli launcher on device...')
                success = adb_return_to_vizabli(room.ip_address)
                
                if success:
                    logger.info(f'[RETURN] ✓ Vizabli launched successfully - device returning to home screen')
                else:
                    logger.error(f'[RETURN] ✗ Failed to launch Vizabli - device may still show playback screen')
                
                # Force-stop video player app to clear all background state and cache
                # This prevents the app from appearing in recents and removes any lingering cached content
                logger.info(f'[CLEANUP] 🛑 Force-stopping video player app(s)...')
                time.sleep(ADB_COMMAND_DELAY)  # Protect against ADB command storms
                success, msg = adb_force_stop_video_player(room.ip_address)
                logger.info(f'[CLEANUP] {msg}')

                # Mark success
                room.push_status = 'complete'
                room.last_push_file = push_log.media_ref
                room.last_push_time = datetime.utcnow()
                push_log.status = 'success'
                push_log.completed_at = datetime.utcnow()
                db.session.commit()

                logger.info(f'╔{"═"*70}╗')
                logger.info(f'║ ✓ PUSH COMPLETE AND SUCCESSFUL')
                logger.info(f'╚{"═"*70}╝')
                
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
