from flask import Blueprint, request, jsonify
from app import db
from app.models.playlist import Playlist, PlaylistItem
from app.models.media import MediaFile
from app.utils import get_tz_aware_now

playlists_bp = Blueprint('playlists', __name__)


@playlists_bp.route('', methods=['GET'])
def get_playlists():
    playlists = Playlist.query.order_by(Playlist.created_at.desc()).all()
    return jsonify([p.to_dict() for p in playlists])


@playlists_bp.route('/<int:playlist_id>', methods=['GET'])
def get_playlist(playlist_id):
    playlist = Playlist.query.get_or_404(playlist_id)
    return jsonify(playlist.to_dict(include_items=True))


@playlists_bp.route('', methods=['POST'])
def create_playlist():
    data = request.get_json()
    if not data or 'name' not in data:
        return jsonify({'error': 'Playlist name is required'}), 400

    existing = Playlist.query.filter_by(name=data['name']).first()
    if existing:
        return jsonify({'error': f'Playlist "{data["name"]}" already exists'}), 409

    playlist = Playlist(name=data['name'], created_at=get_tz_aware_now())
    db.session.add(playlist)
    db.session.flush()

    media_ids = data.get('media_ids', [])
    for idx, media_id in enumerate(media_ids):
        media = MediaFile.query.get(media_id)
        if media:
            item = PlaylistItem(
                playlist_id=playlist.id,
                media_file_id=media.id,
                order_index=idx
            )
            db.session.add(item)

    db.session.commit()
    return jsonify(playlist.to_dict(include_items=True)), 201


@playlists_bp.route('/<int:playlist_id>', methods=['PUT'])
def update_playlist(playlist_id):
    playlist = Playlist.query.get_or_404(playlist_id)
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400

    if 'name' in data:
        existing = Playlist.query.filter(Playlist.name == data['name'], Playlist.id != playlist_id).first()
        if existing:
            return jsonify({'error': f'Playlist "{data["name"]}" already exists'}), 409
        playlist.name = data['name']

    if 'media_ids' in data:
        # Replace all items
        PlaylistItem.query.filter_by(playlist_id=playlist.id).delete()
        for idx, media_id in enumerate(data['media_ids']):
            media = MediaFile.query.get(media_id)
            if media:
                item = PlaylistItem(
                    playlist_id=playlist.id,
                    media_file_id=media.id,
                    order_index=idx
                )
                db.session.add(item)

    db.session.commit()
    return jsonify(playlist.to_dict(include_items=True))


@playlists_bp.route('/<int:playlist_id>', methods=['DELETE'])
def delete_playlist(playlist_id):
    playlist = Playlist.query.get_or_404(playlist_id)
    db.session.delete(playlist)
    db.session.commit()
    return jsonify({'message': f'Playlist "{playlist.name}" deleted'})
