from app import db
from datetime import datetime


class Room(db.Model):
    __tablename__ = 'rooms'

    id = db.Column(db.Integer, primary_key=True)
    room_number = db.Column(db.String(50), unique=True, nullable=False)
    unit = db.Column(db.String(100), nullable=False)
    ip_address = db.Column(db.String(45), nullable=False)
    status = db.Column(db.String(20), default='unknown')  # online/offline/unknown
    last_checked = db.Column(db.DateTime, nullable=True)
    last_push_file = db.Column(db.String(255), nullable=True)
    last_push_time = db.Column(db.DateTime, nullable=True)
    push_status = db.Column(db.String(20), default='idle')  # idle/pushing/complete/error

    def to_dict(self):
        return {
            'id': self.id,
            'room_number': self.room_number,
            'unit': self.unit,
            'ip_address': self.ip_address,
            'status': self.status,
            'last_checked': self.last_checked.isoformat() if self.last_checked else None,
            'last_push_file': self.last_push_file,
            'last_push_time': self.last_push_time.isoformat() if self.last_push_time else None,
            'push_status': self.push_status,
        }
