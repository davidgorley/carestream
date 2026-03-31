import csv
import io
from flask import Blueprint, request, jsonify, Response
from app import db
from app.models.room import Room

rooms_bp = Blueprint('rooms', __name__)


@rooms_bp.route('', methods=['GET'])
def get_rooms():
    rooms = Room.query.order_by(Room.room_number).all()
    return jsonify([r.to_dict() for r in rooms])


@rooms_bp.route('/<int:room_id>', methods=['GET'])
def get_room(room_id):
    room = Room.query.get_or_404(room_id)
    return jsonify(room.to_dict())


@rooms_bp.route('', methods=['POST'])
def create_room():
    data = request.get_json()
    if not data or not all(k in data for k in ('room_number', 'unit', 'ip_address')):
        return jsonify({'error': 'Missing required fields: room_number, unit, ip_address'}), 400

    existing = Room.query.filter_by(room_number=data['room_number']).first()
    if existing:
        return jsonify({'error': f'Room {data["room_number"]} already exists'}), 409

    room = Room(
        room_number=data['room_number'],
        unit=data['unit'],
        ip_address=data['ip_address']
    )
    db.session.add(room)
    db.session.commit()
    return jsonify(room.to_dict()), 201


@rooms_bp.route('/<int:room_id>', methods=['PUT'])
def update_room(room_id):
    room = Room.query.get_or_404(room_id)
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400

    if 'room_number' in data:
        existing = Room.query.filter(Room.room_number == data['room_number'], Room.id != room_id).first()
        if existing:
            return jsonify({'error': f'Room {data["room_number"]} already exists'}), 409
        room.room_number = data['room_number']
    if 'unit' in data:
        room.unit = data['unit']
    if 'ip_address' in data:
        room.ip_address = data['ip_address']

    db.session.commit()
    return jsonify(room.to_dict())


@rooms_bp.route('/<int:room_id>', methods=['DELETE'])
def delete_room(room_id):
    room = Room.query.get_or_404(room_id)
    db.session.delete(room)
    db.session.commit()
    return jsonify({'message': f'Room {room.room_number} deleted'})


@rooms_bp.route('/csv-template', methods=['GET'])
def csv_template():
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['room', 'unit', 'ip'])
    writer.writerow(['Room 224', 'ICU', '192.168.1.101'])
    writer.writerow(['Room 225', 'Pediatrics', '192.168.1.102'])
    writer.writerow(['Room 226', 'Oncology', '192.168.1.103'])
    writer.writerow(['Room 301', 'Cardiology', '192.168.1.104'])
    writer.writerow(['Room 302', 'Neurology', '192.168.1.105'])
    content = output.getvalue()
    return Response(
        content,
        mimetype='text/csv',
        headers={'Content-Disposition': 'attachment; filename=rooms_template.csv'}
    )


@rooms_bp.route('/csv-preview', methods=['POST'])
def csv_preview():
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400

    file = request.files['file']
    if not file.filename.endswith('.csv'):
        return jsonify({'error': 'File must be a CSV'}), 400

    try:
        content = file.read().decode('utf-8')
        reader = csv.DictReader(io.StringIO(content))
        rows = []
        for row in reader:
            room_num = row.get('room', '').strip()
            unit = row.get('unit', '').strip()
            ip = row.get('ip', '').strip()
            if room_num and unit and ip:
                existing = Room.query.filter_by(room_number=room_num).first()
                rows.append({
                    'room': room_num,
                    'unit': unit,
                    'ip': ip,
                    'action': 'update' if existing else 'insert'
                })
        return jsonify({'rows': rows})
    except Exception as e:
        return jsonify({'error': str(e)}), 400


@rooms_bp.route('/csv-import', methods=['POST'])
def csv_import():
    data = request.get_json()
    if not data or 'rows' not in data:
        return jsonify({'error': 'No rows provided'}), 400

    imported = 0
    updated = 0
    for row in data['rows']:
        room_num = row.get('room', '').strip()
        unit = row.get('unit', '').strip()
        ip = row.get('ip', '').strip()
        if not all([room_num, unit, ip]):
            continue

        existing = Room.query.filter_by(room_number=room_num).first()
        if existing:
            existing.unit = unit
            existing.ip_address = ip
            updated += 1
        else:
            room = Room(room_number=room_num, unit=unit, ip_address=ip)
            db.session.add(room)
            imported += 1

    db.session.commit()
    return jsonify({'message': f'Imported {imported} new rooms, updated {updated} existing rooms'})
