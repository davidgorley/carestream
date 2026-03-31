import threading
from flask import Blueprint, request, jsonify
from app import db, socketio
from app.models.room import Room
from app.models.media import MediaFile
from app.models.playlist import Playlist, PushLog
from app.services.push_service import execute_push
from datetime import datetime

push_bp = Blueprint('push', __name__)


@push_bp.route('', methods=['POST'])
def push_content():
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400

    room_id = data.get('room_id')
    media_ids = data.get('media_ids', [])
    playlist_ids = data.get('playlist_ids', [])

    if not room_id:
        return jsonify({'error': 'room_id is required'}), 400
    if not media_ids and not playlist_ids:
        return jsonify({'error': 'Select at least one media file or playlist'}), 400

    room = Room.query.get(room_id)
    if not room:
        return jsonify({'error': 'Room not found'}), 404

    # Build ordered list of media files
    ordered_files = []

    # Add individual media files
    for mid in media_ids:
        mf = MediaFile.query.get(mid)
        if mf:
            ordered_files.append(mf)

    # Add playlist media files (in order)
    for pid in playlist_ids:
        pl = Playlist.query.get(pid)
        if pl:
            for item in pl.items:
                if item.media_file:
                    ordered_files.append(item.media_file)

    if not ordered_files:
        return jsonify({'error': 'No valid media files found'}), 400

    # Build media ref string
    refs = []
    if media_ids:
        refs.extend([f.filename for f in ordered_files[:len(media_ids)]])
    for pid in playlist_ids:
        pl = Playlist.query.get(pid)
        if pl:
            refs.append(f'Playlist: {pl.name}')
    media_ref = ', '.join(refs) if refs else ordered_files[0].filename

    # Create push log entry
    push_log = PushLog(
        room_id=room.id,
        media_ref=media_ref,
        started_at=datetime.utcnow(),
        status='pending'
    )
    db.session.add(push_log)

    # Update room status
    room.push_status = 'pushing'
    db.session.commit()

    # Emit immediate status update
    socketio.emit('room_update', room.to_dict())

    # Execute push in background thread
    from flask import current_app
    app = current_app._get_current_object()
    thread = threading.Thread(target=execute_push, args=(app, room.id, push_log.id,
                                                          [f.id for f in ordered_files]))
    thread.daemon = True
    thread.start()

    return jsonify({
        'message': f'Push initiated for {room.room_number}',
        'push_log_id': push_log.id,
        'files_count': len(ordered_files)
    })


@push_bp.route('/log', methods=['GET'])
def get_push_logs():
    room_id = request.args.get('room_id', type=int)
    query = PushLog.query.order_by(PushLog.started_at.desc())
    if room_id:
        query = query.filter_by(room_id=room_id)
    logs = query.limit(100).all()
    return jsonify([l.to_dict() for l in logs])


@push_bp.route('/status/<int:room_id>', methods=['GET'])
def get_push_status(room_id):
    room = Room.query.get_or_404(room_id)
    return jsonify({
        'room_id': room.id,
        'push_status': room.push_status,
        'last_push_file': room.last_push_file,
        'last_push_time': room.last_push_time.isoformat() if room.last_push_time else None
    })
