from app import db
from datetime import datetime


class MediaFile(db.Model):
    __tablename__ = 'media_files'

    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(255), nullable=False)
    folder = db.Column(db.String(255), default='', nullable=False)  # folder path like "Training/Basic"
    filepath = db.Column(db.String(512), nullable=False)
    filesize = db.Column(db.Integer, default=0)  # bytes
    duration = db.Column(db.Float, default=0.0)  # seconds
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'filename': self.filename,
            'folder': self.folder,
            'filepath': self.filepath,
            'filesize': self.filesize,
            'duration': self.duration,
            'uploaded_at': self.uploaded_at.isoformat() if self.uploaded_at else None,
        }
