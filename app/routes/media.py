import os
import subprocess
from flask import Blueprint, request, jsonify, current_app
from werkzeug.utils import secure_filename
from app import db
from app.models.media import MediaFile
from app.models.folder import Folder
from datetime import datetime
from app.utils import get_tz_aware_now

media_bp = Blueprint('media', __name__)


def get_video_duration(filepath):
    """Use ffprobe to get video duration in seconds."""
    try:
        result = subprocess.run(
            ['ffprobe', '-v', 'quiet', '-print_format', 'json', '-show_format', filepath],
            capture_output=True, text=True, timeout=30
        )
        if result.returncode == 0:
            import json
            info = json.loads(result.stdout)
            duration = float(info.get('format', {}).get('duration', 0))
            return duration
    except Exception as e:
        print(f'ffprobe error for {filepath}: {e}')
    return 0.0


def get_folder_structure():
    """Build a hierarchical folder structure from media files."""
    files = MediaFile.query.all()
    structure = {}
    
    for f in files:
        folder = f.folder or 'Uncategorized'
        if folder not in structure:
            structure[folder] = []
        structure[folder].append(f.to_dict())
    
    return structure


@media_bp.route('', methods=['GET'])
def get_media():
    files = MediaFile.query.order_by(MediaFile.uploaded_at.desc()).all()
    return jsonify([f.to_dict() for f in files])


@media_bp.route('/structure', methods=['GET'])
def get_media_structure():
    """Returns media organized by folder."""
    return jsonify(get_folder_structure())


@media_bp.route('/<int:media_id>', methods=['GET'])
def get_media_file(media_id):
    mf = MediaFile.query.get_or_404(media_id)
    return jsonify(mf.to_dict())


@media_bp.route('/folders', methods=['GET'])
def get_folders():
    """Get all folders."""
    folders = Folder.query.order_by(Folder.created_at.desc()).all()
    return jsonify([f.to_dict() for f in folders])


@media_bp.route('/folders', methods=['POST'])
def create_folder():
    """Create a folder (supports nested paths like 'Training/Videos')."""
    data = request.get_json()
    folder_name = data.get('folder_name', '').strip()
    
    if not folder_name:
        return jsonify({'error': 'Folder name is required'}), 400
    
    # Validate folder name (no backslashes or empty parts)
    if '\\' in folder_name:
        return jsonify({'error': 'Invalid folder name'}), 400
    
    # Validate path structure
    parts = folder_name.split('/')
    if any(not part.strip() for part in parts):
        return jsonify({'error': 'Invalid folder path'}), 400
    
    # Check if folder already exists
    existing = Folder.query.filter_by(name=folder_name).first()
    if existing:
        return jsonify({'error': 'Folder already exists'}), 409
    
    # Create parent folders if they don't exist
    for i in range(len(parts)):
        parent_path = '/'.join(parts[:i+1])
        if not Folder.query.filter_by(name=parent_path).first():
            parent = Folder(name=parent_path)
            db.session.add(parent)
    
    db.session.commit()
    
    # Return the final folder
    folder = Folder.query.filter_by(name=folder_name).first()
    return jsonify(folder.to_dict()), 201


@media_bp.route('/folders/<int:folder_id>', methods=['DELETE'])
def delete_folder(folder_id):
    """Delete a folder (only if empty - no files in this folder or subfolders)."""
    folder = Folder.query.get_or_404(folder_id)
    folder_name = folder.name
    
    # Check if folder has any files directly in it
    files_direct = MediaFile.query.filter_by(folder=folder_name).first()
    if files_direct:
        return jsonify({'error': 'Cannot delete folder with files. Move or delete files first.'}), 409
    
    # Check if folder has any subfolders
    subfolders = Folder.query.filter(Folder.name.like(folder_name + '/%')).first()
    if subfolders:
        return jsonify({'error': 'Cannot delete folder with subfolders. Delete subfolders first.'}), 409
    
    db.session.delete(folder)
    db.session.commit()
    
    return jsonify({'message': f'Folder "{folder_name}" deleted'})


@media_bp.route('/upload', methods=['POST'])
def upload_media():
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400

    file = request.files['file']
    if not file.filename:
        return jsonify({'error': 'No file selected'}), 400

    if not file.filename.lower().endswith('.mp4'):
        return jsonify({'error': 'Only MP4 files are accepted'}), 400

    filename = secure_filename(file.filename)
    folder = request.form.get('folder', '') or ''  # Optional folder assignment
    media_path = current_app.config['MEDIA_PATH']
    filepath = os.path.join(media_path, filename)

    # Handle duplicate filenames
    base, ext = os.path.splitext(filename)
    counter = 1
    while os.path.exists(filepath):
        filename = f"{base}_{counter}{ext}"
        filepath = os.path.join(media_path, filename)
        counter += 1

    file.save(filepath)
    filesize = os.path.getsize(filepath)
    duration = get_video_duration(filepath)

    media_file = MediaFile(
        filename=filename,
        folder=folder,
        filepath=filepath,
        filesize=filesize,
        duration=duration,
        uploaded_at=get_tz_aware_now()
    )
    db.session.add(media_file)
    db.session.commit()

    return jsonify(media_file.to_dict()), 201


@media_bp.route('/<int:media_id>/rename', methods=['PUT'])
def rename_media(media_id):
    """Rename a media file."""
    mf = MediaFile.query.get_or_404(media_id)
    data = request.get_json()
    new_filename = data.get('filename', '').strip()
    
    if not new_filename:
        return jsonify({'error': 'New filename is required'}), 400
    
    if not new_filename.lower().endswith('.mp4'):
        new_filename += '.mp4'
    
    new_filename = secure_filename(new_filename)
    media_path = current_app.config['MEDIA_PATH']
    new_filepath = os.path.join(media_path, new_filename)
    
    # Check if file already exists
    if os.path.exists(new_filepath) and new_filepath != mf.filepath:
        return jsonify({'error': 'A file with that name already exists'}), 409
    
    # Rename physical file
    try:
        if os.path.exists(mf.filepath):
            os.rename(mf.filepath, new_filepath)
    except Exception as e:
        return jsonify({'error': f'Could not rename file: {str(e)}'}), 500
    
    # Update database
    mf.filename = new_filename
    mf.filepath = new_filepath
    db.session.commit()
    
    return jsonify(mf.to_dict())


@media_bp.route('/<int:media_id>/move', methods=['PUT'])
def move_media(media_id):
    """Move a media file to a folder."""
    mf = MediaFile.query.get_or_404(media_id)
    data = request.get_json()
    folder = data.get('folder', '').strip()
    
    mf.folder = folder
    db.session.commit()
    
    return jsonify(mf.to_dict())


@media_bp.route('/<int:media_id>', methods=['DELETE'])
def delete_media(media_id):
    mf = MediaFile.query.get_or_404(media_id)

    # Delete physical file
    if os.path.exists(mf.filepath):
        os.remove(mf.filepath)

    db.session.delete(mf)
    db.session.commit()
    return jsonify({'message': f'{mf.filename} deleted'})
