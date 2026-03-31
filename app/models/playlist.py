from app import db
from datetime import datetime


class Playlist(db.Model):
    __tablename__ = 'playlists'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), unique=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    items = db.relationship('PlaylistItem', backref='playlist', lazy=True,
                            cascade='all, delete-orphan', order_by='PlaylistItem.order_index')

    def to_dict(self, include_items=False):
        data = {
            'id': self.id,
            'name': self.name,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'item_count': len(self.items),
            'total_duration': sum(item.media_file.duration for item in self.items if item.media_file),
        }
        if include_items:
            data['items'] = [item.to_dict() for item in self.items]
        return data


class PlaylistItem(db.Model):
    __tablename__ = 'playlist_items'

    id = db.Column(db.Integer, primary_key=True)
    playlist_id = db.Column(db.Integer, db.ForeignKey('playlists.id'), nullable=False)
    media_file_id = db.Column(db.Integer, db.ForeignKey('media_files.id'), nullable=False)
    order_index = db.Column(db.Integer, nullable=False)
    media_file = db.relationship('MediaFile', lazy=True)

    def to_dict(self):
        return {
            'id': self.id,
            'playlist_id': self.playlist_id,
            'media_file_id': self.media_file_id,
            'order_index': self.order_index,
            'media_file': self.media_file.to_dict() if self.media_file else None,
        }


class PushLog(db.Model):
    __tablename__ = 'push_log'

    id = db.Column(db.Integer, primary_key=True)
    room_id = db.Column(db.Integer, db.ForeignKey('rooms.id'), nullable=False)
    media_ref = db.Column(db.String(255), nullable=False)
    started_at = db.Column(db.DateTime, default=datetime.utcnow)
    completed_at = db.Column(db.DateTime, nullable=True)
    status = db.Column(db.String(20), default='pending')  # pending/success/error
    error_message = db.Column(db.Text, nullable=True)
    room = db.relationship('Room', lazy=True)

    def to_dict(self):
        return {
            'id': self.id,
            'room_id': self.room_id,
            'media_ref': self.media_ref,
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'status': self.status,
            'error_message': self.error_message,
        }
